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

Arrêt d'urgence : créer un fichier nommé STOP dans ce dossier. Plus aucun ordre ne part.
"""
import argparse, csv, json, math, os, sys, time
from datetime import datetime, timedelta, timezone

ICI = os.path.dirname(os.path.abspath(__file__))
FICHIER_STOP = os.path.join(ICI, "STOP")
JOURNAL = os.path.join(ICI, "journal.csv")
MAGIC = 915900  # identifie les ordres passés par cet exécuteur
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
def calculer_signal(bougies, pas, jour, maintenant, cfg):
    """bougies : [(ouverture heure de Paris, haut, bas, clôture)] du jour, pas en minutes.
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
    out = {"statut": "aucune cassure", "haut": haut, "bas": bas, "signal": None}
    for t, h, l, c in sorted(bougies):
        if t < t1 or t + timedelta(minutes=pas) > coupe:
            continue  # avant la fin du range, ou bougie pas encore clôturée
        s = out["signal"]
        if s is None:
            sens = 1 if c > haut else -1 if c < bas else 0
            if sens:
                milieu = (haut + bas) / 2
                r = min(abs(c - milieu), c * cfg["stop_max_pct"] / 100)
                out["signal"] = {"sens": sens, "heure": t + timedelta(minutes=pas), "entree": c, "r": r,
                                 "stop": c - sens * r, "tp1": c + sens * r, "tp2": c + 2 * sens * r,
                                 "plafonne": r < abs(c - milieu), "tp1_touche": False, "resultat": None}
                out["statut"] = "signal"
            continue
        if s["resultat"]:
            continue
        # stop et objectif dans la même bougie : on compte le stop (cas prudent)
        if (l <= s["stop"]) if s["sens"] > 0 else (h >= s["stop"]):
            s["resultat"] = "stop"
            continue
        if (h >= s["tp1"]) if s["sens"] > 0 else (l <= s["tp1"]):
            s["tp1_touche"] = True
        if (h >= s["tp2"]) if s["sens"] > 0 else (l <= s["tp2"]):
            s["resultat"] = "tp2"
    return out


def taille_position(risque_argent, distance, tick_size, tick_value, vol_min, vol_pas, vol_max):
    """Volume (lots) pour perdre au plus risque_argent si le stop est touché. 0 si impossible."""
    if distance <= 0 or tick_size <= 0 or tick_value <= 0:
        return 0.0
    perte_par_lot = distance / tick_size * tick_value
    vol = math.floor(risque_argent / perte_par_lot / vol_pas + 1e-9) * vol_pas
    vol = min(vol, vol_max)
    return round(vol, 8) if vol >= vol_min else 0.0


def controles(sig, prix, spread, pip, maintenant, cfg, deja_trade, trades_jour, perte_jour, solde, compte_reel):
    """Renvoie la liste des raisons de NE PAS envoyer (vide = feu vert)."""
    raisons = []
    if os.path.exists(FICHIER_STOP):
        raisons.append("arrêt d'urgence : le fichier STOP existe")
    if compte_reel and not cfg["compte_reel_autorise"]:
        raisons.append("compte RÉEL et compte_reel_autorise = false dans config.json")
    if deja_trade:
        raisons.append("déjà un trade sur ce symbole aujourd'hui")
    if trades_jour >= cfg["trades_max_jour"]:
        raisons.append("trades_max_jour atteint (%d)" % cfg["trades_max_jour"])
    if perte_jour >= solde * cfg["perte_max_jour_pct"] / 100:
        raisons.append("perte max du jour atteinte (%.2f)" % perte_jour)
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

    def resume_jour(self, decalage):
        """(symboles déjà tradés aujourd'hui, nombre de trades, perte du jour en devise du compte, >0 = perte).
        Les heures de l'historique MT5 sont à l'heure du serveur : on les ramène à l'heure de Paris."""
        mt5 = self.mt5
        maintenant = datetime.now(UTC)
        aujourdhui = paris(maintenant).date()
        brut = mt5.history_deals_get(maintenant - timedelta(days=3), maintenant + timedelta(days=2)) or []
        deals = [d for d in brut if d.magic == MAGIC
                 and paris(datetime.fromtimestamp(d.time - decalage * 3600, UTC)).date() == aujourdhui]
        entrees = [d for d in deals if d.entry == mt5.DEAL_ENTRY_IN]
        trades = {(d.symbol, d.time // 60) for d in entrees}  # un trade TP1+TP2 = 2 positions mais 1 seul trade
        realise = sum(d.profit + d.commission + d.swap for d in deals)
        latent = sum(p.profit + p.swap for p in self.positions())
        return {d.symbol for d in entrees}, len(trades), -(realise + latent)

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


def traiter(m, symbole, cfg, envoyer):
    mt5 = m.mt5
    pas = cfg["symboles"][symbole]["unite_minutes"]
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
    res = calculer_signal(bougies, pas, jour, maintenant, cfg)
    print("\n%s (%d min) — %s" % (symbole, pas, maintenant.strftime("%d/%m %H:%M")))
    if "haut" in res:
        print("  Range %s-%s : bas %s / haut %s" % (cfg["range_debut"], cfg["range_fin"], fmt(res["bas"], dg), fmt(res["haut"], dg)))
    sig = res.get("signal")
    if not sig:
        print("  Statut : %s" % res["statut"])
        return
    nom = "ACHAT" if sig["sens"] > 0 else "VENTE"
    print("  Signal %s à %s : entrée %s | stop %s%s | TP1 %s | TP2 %s"
          % (nom, sig["heure"].strftime("%H:%M"), fmt(sig["entree"], dg), fmt(sig["stop"], dg),
             " (plafonné)" if sig["plafonne"] else "", fmt(sig["tp1"], dg), fmt(sig["tp2"], dg)))

    tick = mt5.symbol_info_tick(symbole)
    prix = tick.ask if sig["sens"] > 0 else tick.bid
    deja, n_jour, perte = m.resume_jour(dec)
    raisons = controles(sig, prix, tick.ask - tick.bid, pip, maintenant, cfg, symbole in deja, n_jour, perte,
                        m.compte.balance, m.reel)
    distance = abs(prix - sig["stop"])
    risque = m.compte.balance * cfg["risque_par_trade_pct"] / 100
    objectifs = {"TP1": [("TP1", sig["tp1"])], "TP2": [("TP2", sig["tp2"])],
                 "TP1+TP2": [("TP1", sig["tp1"]), ("TP2", sig["tp2"])]}[cfg["objectif"]]
    vol_total = taille_position(risque, distance, info.trade_tick_size, info.trade_tick_value,
                                info.volume_min, info.volume_step, info.volume_max)
    vol_part = taille_position(risque / len(objectifs), distance, info.trade_tick_size, info.trade_tick_value,
                               info.volume_min, info.volume_step, info.volume_max)
    if len(objectifs) == 2 and vol_part == 0:
        objectifs, vol_part = [("TP2", sig["tp2"])], vol_total  # trop petit pour couper en deux
    if vol_part == 0:
        raisons.append("risque de %.2f %s trop petit pour le volume minimum" % (risque, m.compte.currency))
    ordres = [(etiquette, tp, vol_part) for etiquette, tp in objectifs]
    for etiquette, tp, vol in ordres:
        print("  Ordre prévu : %s %s lots, stop %s, %s %s (risque max %.2f %s)"
              % (nom, vol, fmt(sig["stop"], dg), etiquette, fmt(tp, dg), risque / len(ordres), m.compte.currency))

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
        noter(heure_paris=paris(datetime.now(UTC)), symbole=p.symbol, mode=cfg["mode"], action="fermeture",
              volume=p.volume, detail="%s ; %s" % (raison, detail))


def etat(m, cfg):
    c = m.compte
    dec = next((d for d in (m.decalage_serveur(s) for s in cfg["symboles"]) if d is not None), cfg["decalage_serveur_secours"])
    deja, n, perte = m.resume_jour(dec)
    print("Compte %s (%s) — %s" % (c.login, "RÉEL" if m.reel else "DÉMO", c.server))
    print("Solde %.2f %s | Fonds propres %.2f | Mode : %s%s"
          % (c.balance, c.currency, c.equity, cfg["mode"], " | ARRÊT D'URGENCE ACTIF" if os.path.exists(FICHIER_STOP) else ""))
    print("Aujourd'hui : %d trade(s) %s | résultat %+.2f %s (limite -%.2f)"
          % (n, sorted(deja) or "", -perte, c.currency, c.balance * cfg["perte_max_jour_pct"] / 100))
    for p in m.positions():
        print("  %s %s %s lots | entrée %s | stop %s | TP %s | %+.2f"
              % (p.symbol, "ACHAT" if p.type == 0 else "VENTE", p.volume, p.price_open, p.sl, p.tp, p.profit))


def cycle(m, cfg, symboles, envoyer):
    maintenant = paris(datetime.now(UTC))
    fin = maintenant.replace(hour=hm(cfg["fin_signaux"])[0], minute=hm(cfg["fin_signaux"])[1], second=0)
    if cfg["fermer_a_fin_signaux"] and maintenant >= fin and m.positions():
        fermer_tout(m, cfg, "fermeture de fin de journée")
    for s in symboles:
        traiter(m, s, cfg, envoyer)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbole")
    ap.add_argument("--envoyer", action="store_true", help="mode validation : envoie l'ordre prévu")
    ap.add_argument("--boucle", action="store_true", help="repasse chaque minute jusqu'à la fin de journée")
    ap.add_argument("--etat", action="store_true")
    ap.add_argument("--fermer-tout", action="store_true")
    a = ap.parse_args()
    cfg = charger_config()
    symboles = [a.symbole] if a.symbole else list(cfg["symboles"])
    if a.symbole and a.symbole not in cfg["symboles"]:
        sys.exit("%s n'est pas dans config.json" % a.symbole)
    m = MT5()
    try:
        if a.etat:
            return etat(m, cfg)
        if a.fermer_tout:
            return fermer_tout(m, cfg, "demande manuelle")
        print("Compte %s — mode %s" % ("RÉEL" if m.reel else "DÉMO", cfg["mode"].upper()))
        if not a.boucle:
            return cycle(m, cfg, symboles, a.envoyer)
        while True:
            cycle(m, cfg, symboles, a.envoyer)
            p = paris(datetime.now(UTC))
            fin = p.replace(hour=hm(cfg["fin_signaux"])[0], minute=hm(cfg["fin_signaux"])[1], second=0) + timedelta(minutes=5)
            if os.path.exists(FICHIER_STOP) or p >= fin:
                print("Fin de la boucle.")
                return
            time.sleep(60)
    finally:
        m.mt5.shutdown()


if __name__ == "__main__":
    main()
