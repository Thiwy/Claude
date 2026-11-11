"""Exécuteur MetaTrader 5 pour la règle du range du matin (heure de Paris).

Règle (la même que morning_scan.py, range_du_matin.pine et les bots TradingView) :
  1. Range : plus haut / plus bas des bougies entre range_debut et range_fin (09:00-09:15).
  2. Signal : première bougie CLÔTURÉE avant fin_signaux (17:30) qui clôture au-dessus du
     haut (ACHAT) ou en dessous du bas (VENTE).
  3. Stop : milieu du range, jamais à plus de stop_max_pct % de l'entrée.
  4. TP1 = 1R, TP2 = 2R.

Tous les réglages sont dans config.json. Modes :
  blanc       rien n'est jamais envoyé : l'ordre est calculé et noté dans journal.csv
  validation  l'ordre n'est envoyé que si on relance avec --envoyer
  auto        l'ordre est envoyé dès que tous les contrôles passent

Utilisation (Windows, MetaTrader 5 ouvert et connecté) :
  py -I executeur_mt5.py                      # tous les symboles de config.json, une fois
  py -I executeur_mt5.py --symbole EURUSD     # un seul symbole
  py -I executeur_mt5.py --symbole EURUSD --envoyer   # mode validation : envoie l'ordre
  py -I executeur_mt5.py --boucle             # repasse chaque minute jusqu'à 17:35
  py -I executeur_mt5.py --etat               # compte, positions, perte du jour
  py -I executeur_mt5.py --fermer-tout        # ferme toutes les positions ouvertes par l'exécuteur
  py -I executeur_mt5.py --rapport            # bilan de la journée (trades, gains / pertes, marchés)
  py -I executeur_mt5.py --symbole EURUSD --analyse   # lecture seule : n'envoie JAMAIS rien

Arrêt d'urgence : créer un fichier nommé STOP dans ce dossier. Plus aucun ordre ne part.
"""
import argparse, csv, json, math, os, sys, time
from datetime import datetime, timedelta, timezone

ICI = os.path.dirname(os.path.abspath(__file__))
FICHIER_STOP = os.path.join(ICI, "STOP")
JOURNAL = os.path.join(ICI, "journal.csv")
MAGIC = 915900  # identifie les ordres passés par cet exécuteur
FICHIER_NOTIF = os.path.join(ICI, "notification.txt")          # sujet ntfy (secret, jamais sur GitHub)
DEJA_NOTIFIE = os.path.join(ICI, "notifications_envoyees.json")
BATTEMENT = os.path.join(ICI, "boucle_en_cours.txt")              # écrit à chaque passage de la boucle automatique
UTC = timezone.utc


# ---------------------------------------------------------------- heure de Paris
def _dernier_dimanche(annee, mois):
    d = datetime(annee, mois, 31)
    return d - timedelta(days=(d.weekday() + 1) % 7)


def paris(t_utc):
    """datetime UTC (aware) -> heure de Paris (naive). Règle UE, sans dépendre de tzdata."""
    y = t_utc.year
    debut = _dernier_dimanche(y, 3).replace(hour=1, tzinfo=UTC)
    fin = _dernier_dimanche(y, 10).replace(hour=1, tzinfo=UTC)
    return (t_utc + timedelta(hours=2 if debut <= t_utc < fin else 1)).replace(tzinfo=None)


def hm(texte):
    h, m = texte.split(":")
    return int(h), int(m)


# ---------------------------------------------------------------- logique pure (testée)
def calculer_signal(bougies, pas, jour, maintenant, cfg, pip=None):
    """bougies : [(ouverture heure de Paris, haut, bas, clôture)] du jour, pas en minutes.
    pip : taille d'un pip (0.0001, ou 0.01 pour le yen), pour le plafond stop_max_pips.
    Renvoie un dict avec statut, range et éventuellement le signal et son suivi."""
    t0 = jour.replace(hour=hm(cfg["range_debut"])[0], minute=hm(cfg["range_debut"])[1], second=0, microsecond=0)
    t1 = jour.replace(hour=hm(cfg["range_fin"])[0], minute=hm(cfg["range_fin"])[1], second=0, microsecond=0)
    fin = jour.replace(hour=hm(cfg["fin_signaux"])[0], minute=hm(cfg["fin_signaux"])[1], second=0, microsecond=0)
    if maintenant < t1:
        return {"statut": "range pas fini (jusqu'à %s)" % t1.strftime("%H:%M")}
    rng = [b for b in bougies if t0 <= b[0] < t1]
    attendu = int((t1 - t0).total_seconds() // 60) // pas
    if len(rng) != attendu:
        return {"statut": "range incomplet (%d bougies sur %d)" % (len(rng), attendu)}
    haut, bas = max(b[1] for b in rng), min(b[2] for b in rng)
    coupe = min(maintenant, fin)
    out = {"statut": "aucune cassure", "haut": haut, "bas": bas, "signal": None, "signaux": []}
    final = "tp1" if cfg.get("objectif") == "TP1" else "tp2"
    max_signaux = cfg.get("trades_max_par_marche", 1)
    arme = True  # prêt pour une cassure ; après un trade, il faut d'abord un retour dans le range
    for t, h, l, c in sorted(bougies):
        if t < t1 or t + timedelta(minutes=pas) > coupe:
            continue  # avant la fin du range, ou bougie pas encore clôturée
        s = out["signal"]
        if s is not None and not s["resultat"]:
            # suivi du trade en cours ; stop et objectif dans la même bougie : on compte le stop (cas prudent)
            if (l <= s["stop"]) if s["sens"] > 0 else (h >= s["stop"]):
                s["resultat"] = "stop"
                continue
            if (h >= s["tp1"]) if s["sens"] > 0 else (l <= s["tp1"]):
                s["tp1_touche"] = True
            if (h >= s["tp2"]) if s["sens"] > 0 else (l <= s["tp2"]):
                s["resultat"] = "tp2"
            elif final == "tp1" and s["tp1_touche"]:
                s["resultat"] = "tp1"
            continue
        if not arme:
            if bas <= c <= haut:
                arme = True  # le prix est revenu dans le range : une nouvelle cassure comptera
            continue
        if len(out["signaux"]) >= max_signaux:
            continue
        sens = 1 if c > haut else -1 if c < bas else 0
        if sens:
            milieu = (haut + bas) / 2
            r = min(abs(c - milieu), c * cfg["stop_max_pct"] / 100)
            if cfg.get("stop_max_pips") and pip:
                r = min(r, cfg["stop_max_pips"] * pip)  # stop rapproché pour rester dans le budget
            sig = {"sens": sens, "heure": t + timedelta(minutes=pas), "entree": c, "r": r,
                   "stop": c - sens * r, "tp1": c + sens * r, "tp2": c + 2 * sens * r,
                   "plafonne": r < abs(c - milieu), "tp1_touche": False, "resultat": None}
            out["signal"] = sig
            out["signaux"].append(sig)
            out["statut"] = "signal"
            arme = False
    return out


def resultat_r(sig, dernier, objectif):
    """Résultat d'un trade, en R (1R = la perte au stop), si on l'avait pris.
    dernier = dernier prix, pour un trade encore ouvert à la fin de la journée."""
    m = (dernier - sig["entree"]) * sig["sens"] / sig["r"]
    res = sig["resultat"]
    jambe1 = 1.0 if sig["tp1_touche"] else (-1.0 if res == "stop" else m)
    jambe2 = 2.0 if res == "tp2" else (-1.0 if res == "stop" else m)
    return {"TP1": jambe1, "TP2": jambe2, "TP1+TP2": (jambe1 + jambe2) / 2}[objectif]


def risque_autorise(solde, cfg, perte_realisee, risque_ouvert, perte_agent=0.0, risque_agent=0.0):
    """Euros qu'on peut risquer sur le prochain trade : le plus petit entre
    - le % du solde et le maximum par trade de l'agent,
    - ce qui reste du stop de la journée du COMPTE (limite - pertes du jour - pertes possibles des positions ouvertes),
    - ce qui reste du stop de la journée de l'AGENT, s'il en a un (mêmes calculs, sur son marché seulement)."""
    infini = float("inf")
    reste_compte = cfg["perte_max_jour_euros"] - perte_realisee - risque_ouvert
    lim_agent = cfg.get("perte_max_jour_agent_euros")
    reste_agent = lim_agent - perte_agent - risque_agent if lim_agent is not None else infini
    plafond = cfg.get("risque_max_par_trade_euros")
    r = min(solde * cfg["risque_par_trade_pct"] / 100, plafond if plafond is not None else infini, reste_compte, reste_agent)
    return max(r, 0.0)


def taille_position(risque_argent, distance, tick_size, tick_value, vol_min, vol_pas, vol_max):
    """Volume (lots) pour perdre au plus risque_argent si le stop est touché. 0 si impossible."""
    if distance <= 0 or tick_size <= 0 or tick_value <= 0:
        return 0.0
    perte_par_lot = distance / tick_size * tick_value
    vol = math.floor(risque_argent / perte_par_lot / vol_pas + 1e-9) * vol_pas
    vol = min(vol, vol_max)
    return round(vol, 8) if vol >= vol_min else 0.0


def controles(sig, prix, spread, pip, maintenant, cfg, deja_trade, trades_jour, perte_jour, compte_reel, perte_agent=0.0):
    """Renvoie la liste des raisons de NE PAS envoyer (vide = feu vert)."""
    raisons = []
    if os.path.exists(FICHIER_STOP):
        raisons.append("arrêt d'urgence : le fichier STOP existe")
    if compte_reel and not cfg["compte_reel_autorise"]:
        raisons.append("compte RÉEL et compte_reel_autorise = false dans config.json")
    if deja_trade:
        raisons.append("déjà une position ouverte sur ce marché, ou ce signal a déjà été pris")
    if trades_jour >= cfg["trades_max_jour"]:
        raisons.append("trades_max_jour atteint (%d)" % cfg["trades_max_jour"])
    if perte_jour >= cfg["perte_max_jour_euros"]:
        raisons.append("stop de la journée : %.2f € perdus (limite %s €)" % (perte_jour, cfg["perte_max_jour_euros"]))
    lim_agent = cfg.get("perte_max_jour_agent_euros")
    if lim_agent is not None and perte_agent >= lim_agent:
        raisons.append("stop de la journée de cet agent : %.2f € perdus (limite %s €)" % (perte_agent, lim_agent))
    if sig["resultat"]:
        raisons.append("le trade est déjà fini sur le graphique (%s)" % sig["resultat"])
    age = (maintenant - sig["heure"]).total_seconds() / 60
    if age > cfg["signal_age_max_minutes"]:
        raisons.append("signal trop ancien (%d min > %d)" % (age, cfg["signal_age_max_minutes"]))
    if abs(prix - sig["entree"]) > cfg["ecart_entree_max_R"] * sig["r"]:
        raisons.append("le prix s'est trop éloigné de l'entrée (%.1fR > %.1fR)"
                       % (abs(prix - sig["entree"]) / sig["r"], cfg["ecart_entree_max_R"]))
    if (prix - sig["stop"]) * sig["sens"] <= 0:
        raisons.append("le prix est déjà au-delà du stop")
    if sig["r"] < cfg["stop_min_pips"] * pip:
        raisons.append("stop trop serré (%.1f pips < %s)" % (sig["r"] / pip, cfg["stop_min_pips"]))
    if spread > sig["r"] * cfg["spread_max_pct_du_stop"] / 100:
        raisons.append("spread trop large (%.0f %% du stop > %s %%)" % (100 * spread / sig["r"], cfg["spread_max_pct_du_stop"]))
    return raisons


# ---------------------------------------------------------------- notifications (app ntfy)
def notifier(titre, message, priorite=3, envoi=None):
    """Notification sur le téléphone via ntfy.sh. Ne fait rien sans notification.txt.
    Ne lève jamais d'erreur : une notification ratée ne doit pas gêner le trading."""
    try:
        with open(FICHIER_NOTIF, encoding="utf-8-sig") as f:
            sujet = f.read().strip()
    except OSError:
        return False
    if not sujet:
        return False
    corps = json.dumps({"topic": sujet, "title": titre, "message": message, "priority": priorite}).encode("utf-8")
    try:
        if envoi:
            return envoi(corps)
        import urllib.request
        req = urllib.request.Request("https://ntfy.sh/", data=corps, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5).read()
        return True
    except Exception as e:  # pas d'internet, ntfy indisponible...
        print("  (notification non envoyée : %s)" % e)
        return False


def deja_notifies(jour):
    try:
        with open(DEJA_NOTIFIE, encoding="utf-8") as f:
            d = json.load(f)
        return d if d.get("jour") == jour else {"jour": jour, "cles": []}
    except (OSError, ValueError):
        return {"jour": jour, "cles": []}


def marquer_notifie(etat_notif, cle):
    etat_notif["cles"].append(cle)
    with open(DEJA_NOTIFIE, "w", encoding="utf-8") as f:
        json.dump(etat_notif, f)


# ---------------------------------------------------------------- journal
def noter(**champs):
    nouveau = not os.path.exists(JOURNAL)
    cols = ["heure_paris", "symbole", "mode", "action", "sens", "volume", "entree", "stop", "tp", "detail"]
    with open(JOURNAL, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter=";")
        if nouveau:
            w.writeheader()
        if isinstance(champs.get("heure_paris"), datetime):
            champs["heure_paris"] = champs["heure_paris"].strftime("%Y-%m-%d %H:%M:%S")
        w.writerow({k: champs.get(k, "") for k in cols})


def charger_config():
    with open(os.path.join(ICI, "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    if cfg["mode"] not in ("blanc", "validation", "auto"):
        sys.exit("config.json : mode doit valoir blanc, validation ou auto")
    return cfg


# ---------------------------------------------------------------- MetaTrader 5
class MT5:
    def __init__(self):
        try:
            import MetaTrader5 as mt5
        except ImportError:
            sys.exit("Module MetaTrader5 absent. Lance : py -m pip install MetaTrader5")
        self.mt5 = mt5
        if not mt5.initialize():
            sys.exit("Impossible de joindre MetaTrader 5 (%s). Ouvre MT5 et connecte-toi à ton compte OANDA." % (mt5.last_error(),))
        self.compte = mt5.account_info()
        if self.compte is None:
            sys.exit("MT5 est ouvert mais aucun compte n'est connecté.")
        self.reel = self.compte.trade_mode == mt5.ACCOUNT_TRADE_MODE_REAL

    def decalage_serveur(self, symbole):
        """Heures entre l'heure du serveur MT5 et UTC, déduit du dernier tick. None si cotation figée."""
        tick = self.mt5.symbol_info_tick(symbole)
        if tick is None:
            return None
        d = (tick.time - time.time()) / 3600
        return round(d) if abs(d - round(d)) < 0.1 else None

    def bougies(self, symbole, pas, decalage):
        tf = {1: self.mt5.TIMEFRAME_M1, 5: self.mt5.TIMEFRAME_M5, 15: self.mt5.TIMEFRAME_M15}[pas]
        rates = self.mt5.copy_rates_from_pos(symbole, tf, 0, 400)
        if rates is None:
            return []
        return [(paris(datetime.fromtimestamp(int(r["time"]) - decalage * 3600, UTC)),
                 float(r["high"]), float(r["low"]), float(r["close"])) for r in rates]

    def positions(self):
        return [p for p in (self.mt5.positions_get() or []) if p.magic == MAGIC]

    def deals_du_jour(self, decalage):
        """[(heure de Paris, deal)] d'aujourd'hui pour les positions ouvertes par l'exécuteur.
        Les sorties par stop ou TP n'ont pas toujours le magic : on les retrouve par leur position.
        Les heures de l'historique MT5 sont à l'heure du serveur : on les ramène à l'heure de Paris."""
        mt5 = self.mt5
        maintenant = datetime.now(UTC)
        aujourdhui = paris(maintenant).date()
        brut = mt5.history_deals_get(maintenant - timedelta(days=7), maintenant + timedelta(days=2)) or []
        ids = {d.position_id for d in brut if d.magic == MAGIC and d.entry == mt5.DEAL_ENTRY_IN}
        ids |= {p.ticket for p in self.positions()}
        heure = lambda d: paris(datetime.fromtimestamp(d.time - decalage * 3600, UTC))
        return [(heure(d), d) for d in brut
                if (d.magic == MAGIC or (d.position_id and d.position_id in ids)) and heure(d).date() == aujourdhui]

    def jours(self, symbole, n):
        """n dernières bougies journalières (la dernière = aujourd'hui)."""
        return self.mt5.copy_rates_from_pos(symbole, self.mt5.TIMEFRAME_D1, 0, n)

    def resume_jour(self, decalage):
        """Bilan du jour des ordres de l'exécuteur (pertes en positif)."""
        mt5 = self.mt5
        avec_heure = self.deals_du_jour(decalage)
        deals = [d for _, d in avec_heure]
        entrees = [d for d in deals if d.entry == mt5.DEAL_ENTRY_IN]
        heures = {}
        for h, d in avec_heure:  # un trade TP1+TP2 = 2 entrées à la même minute = 1 trade
            if d.entry == mt5.DEAL_ENTRY_IN:
                heures.setdefault(d.symbol, set()).add(h.replace(second=0, microsecond=0))
        trades = {(d.symbol, d.time // 60) for d in entrees}  # un trade TP1+TP2 = 2 positions mais 1 seul trade
        perte_realisee = -sum(d.profit + d.commission + d.swap for d in deals)
        perte_sym, risque_sym = {}, {}
        for d in deals:
            perte_sym[d.symbol] = perte_sym.get(d.symbol, 0.0) - (d.profit + d.commission + d.swap)
        for p in self.positions():
            risque_sym[p.symbol] = risque_sym.get(p.symbol, 0.0) + self.perte_au_stop(p)
        return {"symboles": {d.symbol for d in entrees}, "trades": len(trades), "perte_realisee": perte_realisee,
                "entrees": {k: sorted(v) for k, v in heures.items()},
                "perte_par_symbole": perte_sym, "risque_par_symbole": risque_sym,
                "risque_ouvert": sum(self.perte_au_stop(p) for p in self.positions()),
                "latent": sum(p.profit + p.swap for p in self.positions())}

    def perte_au_stop(self, pos):
        """Ce que la position perdrait si son stop était touché (énorme si elle n'a pas de stop)."""
        if not pos.sl:
            return float("inf")
        info = self.mt5.symbol_info(pos.symbol)
        perte = (pos.price_open - pos.sl) * (1 if pos.type == self.mt5.POSITION_TYPE_BUY else -1)
        return max(perte, 0) / info.trade_tick_size * info.trade_tick_value * pos.volume

    def trading_autorise(self):
        """None si MT5 laisse un programme passer des ordres, sinon la raison."""
        term = self.mt5.terminal_info() if hasattr(self.mt5, "terminal_info") else None
        compte = self.mt5.account_info() or self.compte
        if term is not None and not term.trade_allowed:
            return "Algo Trading désactivé dans MT5 (clique sur le bouton « Algo Trading » pour qu'il soit vert)"
        if not getattr(compte, "trade_allowed", True):
            return "OANDA n'autorise pas le trading sur ce compte"
        return None

    def volume_max_marge(self, symbole, sens, prix, info):
        """Plus gros volume que la marge libre permet d'ouvrir (en gardant 10 % de côté)."""
        mt5 = self.mt5
        compte = mt5.account_info() or self.compte
        par_lot = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY if sens > 0 else mt5.ORDER_TYPE_SELL, symbole, 1.0, prix)
        if not par_lot:
            return info.volume_max
        return math.floor(compte.margin_free * 0.9 / par_lot / info.volume_step + 1e-9) * info.volume_step

    def remplissage(self, info):
        mt5 = self.mt5
        if info.filling_mode & 1:
            return mt5.ORDER_FILLING_FOK
        if info.filling_mode & 2:
            return mt5.ORDER_FILLING_IOC
        return mt5.ORDER_FILLING_RETURN

    def envoyer(self, symbole, sens, volume, stop, tp, commentaire, cfg):
        mt5 = self.mt5
        info, tick = mt5.symbol_info(symbole), mt5.symbol_info_tick(symbole)
        req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": symbole, "volume": volume,
               "type": mt5.ORDER_TYPE_BUY if sens > 0 else mt5.ORDER_TYPE_SELL,
               "price": tick.ask if sens > 0 else tick.bid,
               "sl": round(stop, info.digits), "tp": round(tp, info.digits),
               "deviation": cfg["glissement_max_points"], "magic": MAGIC, "comment": commentaire,
               "type_time": mt5.ORDER_TIME_GTC, "type_filling": self.remplissage(info)}
        verif = mt5.order_check(req)
        if verif is None or verif.retcode != 0:
            return False, "refusé par la vérification MT5 : %s" % (verif.comment if verif else mt5.last_error(),)
        res = mt5.order_send(req)
        if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
            return False, "refusé par le serveur : %s" % (res.comment if res else mt5.last_error(),)
        return True, "exécuté à %s, ticket %s" % (res.price, res.order)

    def fermer(self, pos, cfg):
        mt5 = self.mt5
        info, tick = mt5.symbol_info(pos.symbol), mt5.symbol_info_tick(pos.symbol)
        achat = pos.type == mt5.POSITION_TYPE_BUY
        req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": pos.symbol, "volume": pos.volume, "position": pos.ticket,
               "type": mt5.ORDER_TYPE_SELL if achat else mt5.ORDER_TYPE_BUY, "price": tick.bid if achat else tick.ask,
               "deviation": cfg["glissement_max_points"], "magic": MAGIC, "comment": "fermeture",
               "type_time": mt5.ORDER_TIME_GTC, "type_filling": self.remplissage(info)}
        res = mt5.order_send(req)
        ok = res is not None and res.retcode == mt5.TRADE_RETCODE_DONE
        return ok, ("fermée" if ok else "échec : %s" % (res.comment if res else mt5.last_error(),))


def fmt(x, chiffres):
    return ("%." + str(chiffres) + "f") % x


# Règles qui concernent tout le compte : un agent ne peut pas les changer pour lui seul.
REGLES_COMPTE = ("mode", "compte_reel_autorise", "perte_max_jour_euros", "trades_max_jour", "symboles")


def config_symbole(cfg, symbole):
    """Règles générales, remplacées par celles écrites pour ce symbole dans config.json
    (sauf les règles du compte, qui restent communes)."""
    propres = cfg["symboles"][symbole]
    interdites = [k for k in propres if k in REGLES_COMPTE]
    if interdites:
        sys.exit("config.json, %s : %s ne peut pas être réglé par agent (règle du compte)." % (symbole, ", ".join(interdites)))
    return {**cfg, **propres}


def traiter(m, symbole, cfg, envoyer, analyse=False):
    mt5 = m.mt5
    cfg = config_symbole(cfg, symbole)
    pas = cfg["unite_minutes"]
    if not mt5.symbol_select(symbole, True):
        print("%s : symbole introuvable dans MT5." % symbole)
        return
    info = mt5.symbol_info(symbole)
    dg = info.digits
    pip = info.point * (10 if dg in (3, 5) else 1)
    maintenant = paris(datetime.now(UTC))
    dec = m.decalage_serveur(symbole)
    if dec is None:
        print("%s : pas de cotation récente (marché fermé ?). Rien à faire." % symbole)
        return
    jour = maintenant.replace(hour=0, minute=0, second=0, microsecond=0)
    bougies = [b for b in m.bougies(symbole, pas, dec) if b[0].date() == jour.date()]
    res = calculer_signal(bougies, pas, jour, maintenant, cfg, pip)
    print("\n%s (%d min) — %s" % (symbole, pas, maintenant.strftime("%d/%m %H:%M")))
    if "haut" in res:
        print("  Range %s-%s : bas %s / haut %s" % (cfg["range_debut"], cfg["range_fin"], fmt(res["bas"], dg), fmt(res["haut"], dg)))
    for ancien in res.get("signaux", [])[:-1]:
        print("  Trade précédent : %s à %s, fini (%s)" % ("ACHAT" if ancien["sens"] > 0 else "VENTE",
                                                       ancien["heure"].strftime("%H:%M"), ancien["resultat"]))
    sig = res.get("signal")
    if not sig:
        print("  Statut : %s" % res["statut"])
        return
    if sig["resultat"]:
        print("  Dernier signal (%s à %s) fini : %s. En attente d'un retour dans le range puis d'une nouvelle cassure."
              % ("ACHAT" if sig["sens"] > 0 else "VENTE", sig["heure"].strftime("%H:%M"), sig["resultat"]))
        return
    nom = "ACHAT" if sig["sens"] > 0 else "VENTE"
    print("  Signal %s à %s : entrée %s | stop %s%s | TP1 %s | TP2 %s"
          % (nom, sig["heure"].strftime("%H:%M"), fmt(sig["entree"], dg), fmt(sig["stop"], dg),
             " (plafonné)" if sig["plafonne"] else "", fmt(sig["tp1"], dg), fmt(sig["tp2"], dg)))

    tick = mt5.symbol_info_tick(symbole)
    prix = tick.ask if sig["sens"] > 0 else tick.bid
    jr = m.resume_jour(dec)
    entrees_sym = jr["entrees"].get(symbole, [])
    deja = any(p.symbol == symbole for p in m.positions()) or \
        any(t >= sig["heure"] - timedelta(minutes=pas) for t in entrees_sym)
    raisons = controles(sig, prix, tick.ask - tick.bid, pip, maintenant, cfg, deja, jr["trades"],
                        jr["perte_realisee"], m.reel, jr["perte_par_symbole"].get(symbole, 0.0))
    if len(entrees_sym) >= cfg["trades_max_par_marche"]:
        raisons.append("trades_max_par_marche atteint (%d)" % cfg["trades_max_par_marche"])
    if m.trading_autorise():
        raisons.append(m.trading_autorise())
    if m.compte.currency != "EUR":
        raisons.append("le compte est en %s, pas en EUR : les limites en euros ne seraient pas justes" % m.compte.currency)
    distance = abs(prix - sig["stop"])
    risque = risque_autorise(m.compte.balance, cfg, jr["perte_realisee"], jr["risque_ouvert"],
                             jr["perte_par_symbole"].get(symbole, 0.0), jr["risque_par_symbole"].get(symbole, 0.0))
    objectifs = {"TP1": [("TP1", sig["tp1"])], "TP2": [("TP2", sig["tp2"])],
                 "TP1+TP2": [("TP1", sig["tp1"]), ("TP2", sig["tp2"])]}[cfg["objectif"]]
    vol_marge = m.volume_max_marge(symbole, sig["sens"], prix, info)
    vol_max = min(info.volume_max, vol_marge)
    vol_total = taille_position(risque, distance, info.trade_tick_size, info.trade_tick_value,
                                info.volume_min, info.volume_step, vol_max)
    vol_part = taille_position(risque / len(objectifs), distance, info.trade_tick_size, info.trade_tick_value,
                               info.volume_min, info.volume_step, vol_max / len(objectifs))
    if len(objectifs) == 2 and vol_part == 0:
        objectifs, vol_part = [("TP2", sig["tp2"])], vol_total  # trop petit pour couper en deux
    if vol_marge < info.volume_min:
        raisons.append("marge libre insuffisante (%.2f %s) pour le volume minimum" % (m.compte.margin_free, m.compte.currency))
    if vol_part == 0:
        raisons.append("risque de %.2f %s trop petit pour le volume minimum" % (risque, m.compte.currency))
    ordres = [(etiquette, tp, vol_part) for etiquette, tp in objectifs]
    for etiquette, tp, vol in (ordres if vol_part else []):
        print("  Ordre prévu : %s %s lots, stop %s, %s %s (risque max %.2f %s)"
              % (nom, vol, fmt(sig["stop"], dg), etiquette, fmt(tp, dg), risque / len(ordres), m.compte.currency))

    if analyse:  # question posée à un agent : on regarde, on n'envoie jamais rien
        print("  ➜ ANALYSE SEULE, rien n'est envoyé. " + ("L'exécuteur refuserait : " + " ; ".join(raisons) if raisons
              else "En mode %s, l'exécuteur %s." % (cfg["mode"], {"auto": "l'enverrait", "validation": "te demanderait de le valider",
                                                                  "blanc": "le noterait sans l'envoyer"}[cfg["mode"]])))
        return
    if raisons:
        print("  ➜ PAS D'ENVOI : " + " ; ".join(raisons))
        noter(heure_paris=maintenant, symbole=symbole, mode=cfg["mode"], action="refusé", sens=nom,
              entree=prix, stop=sig["stop"], detail=" ; ".join(raisons))
        return
    if cfg["mode"] == "blanc" or (cfg["mode"] == "validation" and not envoyer):
        quoi = "mode à blanc : rien n'est envoyé" if cfg["mode"] == "blanc" else \
               "mode validation : relance avec --symbole %s --envoyer pour l'envoyer" % symbole
        print("  ➜ " + quoi)
        for etiquette, tp, vol in ordres:
            noter(heure_paris=maintenant, symbole=symbole, mode=cfg["mode"], action="prévu", sens=nom, volume=vol,
                  entree=prix, stop=sig["stop"], tp=tp, detail=etiquette)
        return
    for etiquette, tp, vol in ordres:
        ok, detail = m.envoyer(symbole, sig["sens"], vol, sig["stop"], tp, "range9h " + etiquette, cfg)
        print("  ➜ %s %s : %s" % ("ENVOYÉ" if ok else "ÉCHEC", etiquette, detail))
        noter(heure_paris=maintenant, symbole=symbole, mode=cfg["mode"], action="envoyé" if ok else "échec",
              sens=nom, volume=vol, entree=prix, stop=sig["stop"], tp=tp, detail=detail)
        if ok:
            notifier("%s %s ouvert" % (nom, symbole),
                     "%s lot, %s\nStop %s | %s %s\nRisque max %.2f €"
                     % (vol, detail, fmt(sig["stop"], dg), etiquette, fmt(tp, dg), risque / len(ordres)), 4)
        else:
            notifier("Ordre %s refusé" % symbole, detail, 4)


def fermer_tout(m, cfg, raison):
    pos = m.positions()
    if not pos:
        print("Aucune position ouverte par l'exécuteur.")
    for p in pos:
        if cfg["mode"] == "blanc":
            print("%s ticket %s : serait fermée (%s) — mode à blanc" % (p.symbol, p.ticket, raison))
            continue
        ok, detail = m.fermer(p, cfg)
        print("%s ticket %s : %s" % (p.symbol, p.ticket, detail))
        if not ok:
            notifier("Fermeture %s ratée" % p.symbol, "%s — ferme la position à la main dans MetaTrader 5." % detail, 5)
        noter(heure_paris=paris(datetime.now(UTC)), symbole=p.symbol, mode=cfg["mode"], action="fermeture",
              volume=p.volume, detail="%s ; %s" % (raison, detail))


def etat(m, cfg):
    c = m.compte
    dec = next((d for d in (m.decalage_serveur(s) for s in cfg["symboles"]) if d is not None), cfg["decalage_serveur_secours"])
    jr = m.resume_jour(dec)
    print("Compte %s (%s) — %s" % (c.login, "RÉEL" if m.reel else "DÉMO", c.server))
    b = boucle_active()
    print("Boucle automatique : %s" % ("ACTIVE (dernier passage %s)" % b.strftime("%H:%M") if b else "arrêtée"))
    print("Envoi d'ordres : %s" % (m.trading_autorise() or ("PRÊT" if cfg["mode"] != "blanc" and (cfg["compte_reel_autorise"] or not m.reel)
                                                          else "non (mode %s%s)" % (cfg["mode"], ", compte réel pas autorisé" if m.reel and not cfg["compte_reel_autorise"] else ""))))
    print("Solde %.2f %s | Fonds propres %.2f | Mode : %s%s"
          % (c.balance, c.currency, c.equity, cfg["mode"], " | ARRÊT D'URGENCE ACTIF" if os.path.exists(FICHIER_STOP) else ""))
    lim = cfg["perte_max_jour_euros"]
    print("Aujourd'hui : %d trade(s) %s | perdu %.2f € | positions ouvertes : %.2f € en cours, %.2f € au pire (stops)"
          % (jr["trades"], sorted(jr["symboles"]) or "", max(jr["perte_realisee"], 0), jr["latent"], jr["risque_ouvert"]))
    print("Stop de la journée : %s € | encore risquable aujourd'hui : %.2f €%s"
          % (lim, max(lim - jr["perte_realisee"] - jr["risque_ouvert"], 0),
             " | STOP ATTEINT, plus de trade aujourd'hui" if jr["perte_realisee"] >= lim else ""))
    for sym in cfg["symboles"]:
        cs = config_symbole(cfg, sym)
        la = cs.get("perte_max_jour_agent_euros")
        pa = jr["perte_par_symbole"].get(sym, 0.0)
        print("  Agent %s : perdu %.2f €%s | risque max par trade %s € | objectif %s"
              % (sym, max(pa, 0), " / stop agent %s €%s" % (la, " ATTEINT" if pa >= la else "") if la is not None else "",
                 cs.get("risque_max_par_trade_euros"), cs["objectif"]))
    for p in m.positions():
        print("  %s %s %s lots | entrée %s | stop %s | TP %s | %+.2f"
              % (p.symbol, "ACHAT" if p.type == 0 else "VENTE", p.volume, p.price_open, p.sl, p.tp, p.profit))


RAISONS_SORTIE = {4: "stop loss", 5: "take profit", 6: "stop out (marge)"}


def journal_du_jour(jour):
    if not os.path.exists(JOURNAL):
        return []
    with open(JOURNAL, encoding="utf-8") as f:
        return [l for l in csv.DictReader(f, delimiter=";") if l["heure_paris"].startswith(jour.strftime("%Y-%m-%d"))]


def rapport(m, cfg):
    """Tout ce qu'il faut pour le rapport de fin de journée : trades, gains / pertes, données de marché."""
    mt5, c = m.mt5, m.compte
    maintenant = paris(datetime.now(UTC))
    jour = maintenant.replace(hour=0, minute=0, second=0, microsecond=0)
    dec = next((d for d in (m.decalage_serveur(s) for s in cfg["symboles"]) if d is not None), cfg["decalage_serveur_secours"])
    print("RAPPORT DU %s (données à %s, heure de Paris)" % (jour.strftime("%d/%m/%Y"), maintenant.strftime("%H:%M")))
    print("Compte %s (%s) | mode %s | solde %.2f %s | fonds propres %.2f"
          % (c.login, "RÉEL" if m.reel else "DÉMO", cfg["mode"], c.balance, c.currency, c.equity))

    # --- trades réels
    par_pos = {}
    for h, d in m.deals_du_jour(dec):
        par_pos.setdefault(d.position_id, []).append((h, d))
    print("\n== TRADES RÉELS DU JOUR")
    total = 0.0
    if not par_pos:
        print("Aucun trade réel aujourd'hui.")
    for pid, ds in sorted(par_pos.items(), key=lambda x: x[1][0][0]):
        entree = next((x for x in ds if x[1].entry == mt5.DEAL_ENTRY_IN), None)
        sorties = [x for x in ds if x[1].entry != mt5.DEAL_ENTRY_IN]
        res = sum(d.profit + d.commission + d.swap for _, d in ds)
        total += res
        if entree:
            h, d = entree
            ligne = "%s %s %s lots | entrée %s à %s" % (d.symbol, "ACHAT" if d.type == 0 else "VENTE", d.volume, d.price, h.strftime("%H:%M"))
        else:
            ligne = "%s (entrée un autre jour)" % ds[0][1].symbol
        for h, d in sorties:
            ligne += " | sortie %s à %s (%s)" % (d.price, h.strftime("%H:%M"), RAISONS_SORTIE.get(d.reason, "fermeture"))
        if not sorties:
            ligne += " | encore ouverte"
        print("  %s | résultat %+.2f €" % (ligne, res))
    ouvertes = m.positions()
    latent = sum(p.profit + p.swap for p in ouvertes)
    for p in ouvertes:
        print("  Position ouverte : %s %s %s lots | entrée %s | stop %s | TP %s | en cours %+.2f €"
              % (p.symbol, "ACHAT" if p.type == 0 else "VENTE", p.volume, p.price_open, p.sl, p.tp, p.profit + p.swap))
    jr = m.resume_jour(dec)
    lim = cfg["perte_max_jour_euros"]
    print("Résultat réel du jour : %+.2f € (dont %+.2f € encore en cours) | stop de la journée %s € %s"
          % (total + latent, latent, lim, "ATTEINT" if jr["perte_realisee"] >= lim else "non atteint"))

    # --- marchés et trades virtuels
    for sym in cfg["symboles"]:
        cs = config_symbole(cfg, sym)
        mt5.symbol_select(sym, True)
        info = mt5.symbol_info(sym)
        if info is None:
            print("\n== %s : symbole introuvable" % sym)
            continue
        dg, pip = info.digits, info.point * (10 if info.digits in (3, 5) else 1)
        print("\n== MARCHÉ %s (bougies de %d min)" % (sym, cs["unite_minutes"]))
        jours = m.jours(sym, 21)
        if jours is not None and len(jours) >= 2:
            a = jours[-1]
            amp = [(float(x["high"]) - float(x["low"])) / pip for x in jours[:-1]]
            print("  Journée : ouverture %s | plus haut %s | plus bas %s | dernier %s | variation %+.2f %%"
                  % (fmt(a["open"], dg), fmt(a["high"], dg), fmt(a["low"], dg), fmt(a["close"], dg),
                     100 * (float(a["close"]) - float(a["open"])) / float(a["open"])))
            print("  Amplitude du jour %.1f pips | moyenne des %d jours précédents %.1f pips"
                  % ((float(a["high"]) - float(a["low"])) / pip, len(amp), sum(amp) / len(amp)))
        bougies = [b for b in m.bougies(sym, cs["unite_minutes"], dec) if b[0].date() == jour.date()]
        r = calculer_signal(bougies, cs["unite_minutes"], jour, maintenant, cs, pip)
        if "haut" not in r:
            print("  Règle : %s" % r["statut"])
            continue
        print("  Range %s-%s : bas %s / haut %s (%.1f pips)"
              % (cs["range_debut"], cs["range_fin"], fmt(r["bas"], dg), fmt(r["haut"], dg), (r["haut"] - r["bas"]) / pip))
        if not r["signaux"]:
            print("  Règle : aucune cassure du range, pas de trade.")
            continue
        dernier = bougies[-1][3] if bougies else r["signaux"][-1]["entree"]
        risque = risque_autorise(c.balance, cs, 0, 0)
        total_r = 0.0
        for n, sig in enumerate(r["signaux"], 1):
            rr = resultat_r(sig, dernier, cs["objectif"])
            total_r += rr
            print("  Signal %d : %s à %s | entrée %s | stop %s (%.1f pips) | TP1 %s | TP2 %s"
                  % (n, "ACHAT" if sig["sens"] > 0 else "VENTE", sig["heure"].strftime("%H:%M"), fmt(sig["entree"], dg),
                     fmt(sig["stop"], dg), sig["r"] / pip, fmt(sig["tp1"], dg), fmt(sig["tp2"], dg)))
            issue = {"stop": "TP1 touché puis stop" if sig["tp1_touche"] else "stop touché", "tp2": "TP2 touché",
                     "tp1": "TP1 touché"}.get(sig["resultat"], "TP1 touché, TP2 pas atteint" if sig["tp1_touche"] else "ni stop ni TP1")
            print("    Ce que la règle a donné : %s | %+.2fR, soit environ %+.2f € avec %.2f € de risque (objectif %s)"
                  % (issue, rr, rr * risque, risque, cs["objectif"]))
        if len(r["signaux"]) > 1:
            print("  Total de la règle sur %d signaux : %+.2fR, environ %+.2f €" % (len(r["signaux"]), total_r, total_r * risque))

    # --- journal
    lignes = journal_du_jour(jour)
    print("\n== DÉCISIONS DE L'EXÉCUTEUR AUJOURD'HUI (journal.csv)")
    if not lignes:
        print("Aucune.")
    vus = set()
    for l in lignes:
        cle = (l["symbole"], l["action"], l["detail"])
        if cle not in vus:
            vus.add(cle)
            print("  %s %s %s %s : %s" % (l["heure_paris"][11:16], l["symbole"], l["action"], l["sens"], l["detail"]))


def suivre_fermetures(m, cfg):
    """Notifie une seule fois chaque position fermée aujourd'hui (stop, TP, 17h30) et le stop de la journée."""
    mt5 = m.mt5
    dec = next((d for d in (m.decalage_serveur(s) for s in cfg["symboles"]) if d is not None), cfg["decalage_serveur_secours"])
    jour = paris(datetime.now(UTC)).strftime("%Y-%m-%d")
    etat_notif = deja_notifies(jour)
    par_pos = {}
    for h, d in m.deals_du_jour(dec):
        par_pos.setdefault(d.position_id, []).append(d)
    for pid, ds in par_pos.items():
        sorties = [d for d in ds if d.entry != mt5.DEAL_ENTRY_IN]
        if not sorties or ("fermee-%s" % pid) in etat_notif["cles"]:
            continue
        res = sum(d.profit + d.commission + d.swap for d in ds)
        raison = RAISONS_SORTIE.get(sorties[-1].reason, "fermeture")
        notifier("%s fermé (%s) : %+.2f €" % (sorties[-1].symbol, raison, res),
                 "Sortie à %s. Résultat du trade : %+.2f €." % (sorties[-1].price, res), 4)
        marquer_notifie(etat_notif, "fermee-%s" % pid)
    jr = m.resume_jour(dec)
    if jr["perte_realisee"] >= cfg["perte_max_jour_euros"] and "stop-jour" not in etat_notif["cles"]:
        notifier("Stop de la journée atteint", "%.2f € perdus aujourd'hui : plus aucun trade jusqu'à demain."
                 % jr["perte_realisee"], 5)
        marquer_notifie(etat_notif, "stop-jour")


def cycle(m, cfg, symboles, envoyer):
    m.compte = m.mt5.account_info() or m.compte  # solde à jour pour le calcul du risque
    maintenant = paris(datetime.now(UTC))
    fin = maintenant.replace(hour=hm(cfg["fin_signaux"])[0], minute=hm(cfg["fin_signaux"])[1], second=0)
    if cfg["fermer_a_fin_signaux"] and maintenant >= fin and m.positions():
        fermer_tout(m, cfg, "fermeture de fin de journée")
    if cfg["mode"] != "blanc":
        suivre_fermetures(m, cfg)
    for s in symboles:
        traiter(m, s, cfg, envoyer)


def boucle(m, cfg, symboles):
    """Repasse chaque minute jusqu'à fin_signaux + 5 min. Survit aux coupures de MT5 ou d'internet."""
    notifier("Agents de trading démarrés", "Compte %s, mode %s. Je repasse chaque minute jusqu'à %s."
             % ("RÉEL" if m.reel else "DÉMO", cfg["mode"], cfg["fin_signaux"]), 2)
    derniere_alerte = 0.0
    try:
        while True:
            p = paris(datetime.now(UTC))
            print("\n===== %s" % p.strftime("%d/%m %H:%M:%S"))
            try:
                cfg = charger_config()  # un changement de config.json est pris en compte sans relancer
                cycle(m, cfg, symboles, False)
                with open(BATTEMENT, "w", encoding="utf-8") as f:
                    f.write(p.strftime("%Y-%m-%d %H:%M:%S"))
            except Exception as e:
                print("ERREUR : %r — nouvelle tentative dans 1 minute" % (e,))
                if time.time() - derniere_alerte > 1800:
                    notifier("Problème avec les agents de trading",
                             "%s. Je réessaie chaque minute. Vérifie MetaTrader 5 et internet." % e, 4)
                    derniere_alerte = time.time()
                m.mt5.shutdown()
                if m.mt5.initialize():
                    m.compte = m.mt5.account_info() or m.compte
            fin = p.replace(hour=hm(cfg["fin_signaux"])[0], minute=hm(cfg["fin_signaux"])[1], second=0) + timedelta(minutes=5)
            if os.path.exists(FICHIER_STOP) or p >= fin:
                print("Fin de la boucle.")
                notifier("Agents de trading arrêtés", "Fin de journée." if p >= fin else "Fichier STOP trouvé.", 2)
                return
            time.sleep(60)
    finally:
        if os.path.exists(BATTEMENT):
            os.remove(BATTEMENT)


class Double:
    """Écrit à l'écran ET dans un fichier (journal de la boucle)."""
    def __init__(self, ecran, fichier):
        self.ecran, self.fichier = ecran, fichier

    def write(self, texte):
        for f in (self.ecran, self.fichier):
            try:
                f.write(texte)
                f.flush()
            except (OSError, ValueError):
                pass
        return len(texte)

    def flush(self):
        pass


def diagnostic(m, cfg):
    """Ce que MetaTrader 5 et OANDA autorisent vraiment, pour comprendre un refus."""
    mt5 = m.mt5
    c = mt5.account_info()
    t = mt5.terminal_info() if hasattr(mt5, "terminal_info") else None
    print("COMPTE %s — %s — %s" % (c.login, c.server, "RÉEL" if c.trade_mode == mt5.ACCOUNT_TRADE_MODE_REAL else "DÉMO"))
    print("  Trading autorisé sur le compte (trade_allowed) : %s" % getattr(c, "trade_allowed", "?"))
    print("    -> False = connecté en LECTURE SEULE (mot de passe investisseur) ou compte bloqué par OANDA")
    print("  Trading par programme autorisé (trade_expert) : %s" % getattr(c, "trade_expert", "?"))
    print("  Effet de levier : 1:%s | solde %.2f %s | marge libre %.2f" % (getattr(c, "leverage", "?"), c.balance, c.currency,
                                                                         getattr(c, "margin_free", 0)))
    if t is not None:
        print("TERMINAL : connecté %s | bouton Algo Trading %s | %s"
              % (getattr(t, "connected", "?"), "VERT" if t.trade_allowed else "ÉTEINT", getattr(t, "path", "")))
    modes = {0: "DÉSACTIVÉ", 1: "achat seulement", 2: "vente seulement", 3: "fermeture seulement", 4: "COMPLET"}
    for sym in cfg["symboles"]:
        mt5.symbol_select(sym, True)
        i, k = mt5.symbol_info(sym), mt5.symbol_info_tick(sym)
        if i is None:
            print("SYMBOLE %s : introuvable" % sym)
            continue
        pip = i.point * (10 if i.digits in (3, 5) else 1)
        marge = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, sym, i.volume_min, k.ask) if k else None
        print("SYMBOLE %s : trading %s | bid %s ask %s | spread %.1f pips | volume min %s | marge pour %s lot : %s"
              % (sym, modes.get(getattr(i, "trade_mode", None), "?"), k.bid if k else "?", k.ask if k else "?",
                 (k.ask - k.bid) / pip if k else -1, i.volume_min, i.volume_min, marge))
        autres = [x.name for x in (mt5.symbols_get("*%s*" % sym) or []) if x.name != sym]
        if autres:
            print("  Autres symboles du même nom chez OANDA : %s" % ", ".join(autres[:10]))


def symboles_tradables(m, cfg):
    """Liste les symboles où le compte peut OUVRIR des positions, avec ce que coûte le plus petit ordre."""
    mt5 = m.mt5
    c = mt5.account_info()
    tous = mt5.symbols_get() or []
    modes = {}
    for x in tous:
        modes[getattr(x, "trade_mode", None)] = modes.get(getattr(x, "trade_mode", None), 0) + 1
    noms = {0: "désactivés", 1: "achat seulement", 2: "vente seulement", 3: "fermeture seulement", 4: "tradables"}
    print("%d symboles chez OANDA sur ce compte : %s" % (len(tous), ", ".join(
        "%d %s" % (n, noms.get(k, k)) for k, n in sorted(modes.items(), key=lambda kv: str(kv[0])))))
    lignes = []
    for x in tous:
        if getattr(x, "trade_mode", None) != 4:
            continue
        mt5.symbol_select(x.name, True)
        k = mt5.symbol_info_tick(x.name)
        if not k or not k.ask or not k.bid:
            continue
        pip = x.point * (10 if x.digits in (3, 5) else 1)
        marge = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, x.name, x.volume_min, k.ask)
        valeur_pip = x.trade_tick_value * pip / x.trade_tick_size * x.volume_min if x.trade_tick_size else 0
        lignes.append((marge if marge is not None else 1e18, x.name, (k.ask - k.bid) / pip, x.volume_min, valeur_pip,
                       getattr(x, "description", "")))
    if not lignes:
        print("AUCUN symbole ne permet d'ouvrir une position : le compte entier est bloqué. Il faut voir avec OANDA.")
        return
    print("Symboles où tu peux ouvrir une position (les moins chers en marge d'abord) :")
    print("  %-14s %9s %10s %12s %14s  %s" % ("symbole", "spread", "vol. min", "marge min", "valeur 1 pip", "description"))
    for marge, nom, spread, vmin, vpip, desc in sorted(lignes)[:40]:
        print("  %-14s %7.1f p %10s %10.2f %s %12.3f %s  %s"
              % (nom, spread, vmin, marge, c.currency, vpip, c.currency, desc[:40]))
    print("Marge libre : %.2f %s. Un symbole convient si sa marge min est bien en dessous et son spread petit."
          % (c.margin_free, c.currency))


def boucle_active():
    """Heure du dernier passage de la boucle automatique, si elle a tourné il y a moins de 3 minutes."""
    try:
        with open(BATTEMENT, encoding="utf-8") as f:
            t = datetime.strptime(f.read().strip(), "%Y-%m-%d %H:%M:%S")
    except (OSError, ValueError):
        return None
    return t if paris(datetime.now(UTC)) - t < timedelta(minutes=3) else None


def main():
    # Sous Windows, une sortie redirigée (Claude, fichier .log) est en cp1252 : « ➜ » ferait planter Python.
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbole")
    ap.add_argument("--envoyer", action="store_true", help="mode validation : envoie l'ordre prévu")
    ap.add_argument("--analyse", action="store_true", help="lecture seule : montre le signal et l'ordre prévu, n'envoie JAMAIS rien")
    ap.add_argument("--boucle", action="store_true", help="repasse chaque minute jusqu'à la fin de journée")
    ap.add_argument("--etat", action="store_true")
    ap.add_argument("--fermer-tout", action="store_true")
    ap.add_argument("--rapport", action="store_true", help="bilan de la journée pour le rapport de fin de journée")
    ap.add_argument("--test-notification", action="store_true", help="envoie une notification d'essai sur le téléphone")
    ap.add_argument("--diagnostic", action="store_true", help="ce que MetaTrader 5 et OANDA autorisent vraiment")
    ap.add_argument("--symboles-tradables", action="store_true", help="liste les symboles où le compte peut ouvrir une position")
    ap.add_argument("--notifier", metavar="MESSAGE", help="envoie ce message en notification (utilisé par rapport.bat)")
    a = ap.parse_args()
    if a.test_notification or a.notifier:
        ok = notifier("Agents de trading", a.notifier or "Notification d'essai : tout marche !")
        print("Notification envoyée." if ok else "Pas envoyée : crée d'abord notification.txt (voir README).")
        return
    cfg = charger_config()
    symboles = [a.symbole] if a.symbole else list(cfg["symboles"])
    if a.symbole and a.symbole not in cfg["symboles"]:
        sys.exit("%s n'est pas dans config.json" % a.symbole)
    m = MT5()
    try:
        if a.etat:
            return etat(m, cfg)
        if a.rapport:
            return rapport(m, cfg)
        if a.diagnostic:
            return diagnostic(m, cfg)
        if a.symboles_tradables:
            return symboles_tradables(m, cfg)
        if a.analyse:
            print("Compte %s — ANALYSE SEULE (rien n'est envoyé)" % ("RÉEL" if m.reel else "DÉMO"))
            for s in symboles:
                traiter(m, s, cfg, False, analyse=True)
            return
        if a.fermer_tout:
            return fermer_tout(m, cfg, "demande manuelle")
        print("Compte %s — mode %s" % ("RÉEL" if m.reel else "DÉMO", cfg["mode"].upper()))
        if not a.boucle:
            return cycle(m, cfg, symboles, a.envoyer)
        os.makedirs(os.path.join(ICI, "rapports"), exist_ok=True)
        log = open(os.path.join(ICI, "rapports", "boucle.log"), "a", encoding="utf-8")
        sys.stdout, sys.stderr = Double(sys.stdout, log), Double(sys.stderr, log)
        print("Agents de trading en marche. NE FERME PAS cette fenêtre (Ctrl+C pour arrêter).")
        return boucle(m, cfg, symboles)
    finally:
        m.mt5.shutdown()


if __name__ == "__main__":
    main()
