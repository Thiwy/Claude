"""Tests de la logique, sans MetaTrader 5 : py -I test_executeur.py"""
import json, os, sys
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import executeur_mt5 as ex

cfg = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"), encoding="utf-8"))
jour = datetime(2026, 11, 5)
p = lambda h, m: jour.replace(hour=h, minute=m)
# range 09:00-09:15 : haut 1.1010, bas 1.0990, milieu 1.1000
bougies = [(p(9, 0), 1.1010, 1.0995, 1.1000), (p(9, 5), 1.1005, 1.0990, 1.1002), (p(9, 10), 1.1008, 1.0996, 1.1004),
           (p(9, 15), 1.1009, 1.1000, 1.1006),   # reste dans le range
           (p(9, 20), 1.1022, 1.1005, 1.1020),   # clôture 1.1020 > 1.1010 : ACHAT à 09:25
           (p(9, 25), 1.1031, 1.1015, 1.1028),   # touche TP1 (1.1040) ? non
           (p(9, 30), 1.1045, 1.1025, 1.1042)]   # touche TP1 1.1040

# 1. range pas fini
assert ex.calculer_signal(bougies, 5, jour, p(9, 10), cfg)["statut"].startswith("range pas fini")
# 2. signal ACHAT, stop au milieu du range, TP1 = 1R, TP2 = 2R
r = ex.calculer_signal(bougies, 5, jour, p(9, 25), cfg)
s = r["signal"]
assert r["haut"] == 1.1010 and r["bas"] == 1.0990
assert s["sens"] == 1 and s["heure"] == p(9, 25) and s["entree"] == 1.1020
assert abs(s["stop"] - 1.1000) < 1e-9 and abs(s["tp1"] - 1.1040) < 1e-9 and abs(s["tp2"] - 1.1060) < 1e-9
# la bougie de 09:25 n'est pas clôturée à 09:28 : pas de suivi
assert not s["tp1_touche"]
# 3. suivi : TP1 touché à 09:30
s = ex.calculer_signal(bougies, 5, jour, p(9, 40), cfg)["signal"]
assert s["tp1_touche"] and s["resultat"] is None
# 4. stop et TP1 dans la même bougie : on compte le stop
pire = bougies[:5] + [(p(9, 25), 1.1045, 1.0995, 1.1010)]
s = ex.calculer_signal(pire, 5, jour, p(9, 40), cfg)["signal"]
assert s["resultat"] == "stop" and not s["tp1_touche"]
# 5. stop plafonné à 1 %
large = [(p(9, 0), 1.20, 1.00, 1.1), (p(9, 5), 1.1, 1.1, 1.1), (p(9, 10), 1.1, 1.1, 1.1), (p(9, 15), 1.25, 1.2, 1.21)]
s = ex.calculer_signal(large, 5, jour, p(9, 30), cfg)["signal"]
assert s["plafonne"] and abs(s["r"] - 1.21 * 0.01) < 1e-9
# 6. range incomplet (bougie manquante)
assert "incomplet" in ex.calculer_signal(bougies[1:], 5, jour, p(9, 30), cfg)["statut"]
# 7. aucune cassure après 17:30
calme = bougies[:4] + [(p(17, 30), 1.1050, 1.1000, 1.1040)]
assert ex.calculer_signal(calme, 5, jour, p(17, 45), cfg)["statut"] == "aucune cassure"

# 8. taille de position : EURUSD, 1 lot = 10 USD par pip (tick 0.00001 = 1 USD), stop 20 pips, risque 50 -> 0.25 lot
assert ex.taille_position(50, 0.0020, 0.00001, 1.0, 0.01, 0.01, 100) == 0.25
assert ex.taille_position(1, 0.0020, 0.00001, 1.0, 0.01, 0.01, 100) == 0.0      # trop petit
assert ex.taille_position(10**9, 0.0020, 0.00001, 1.0, 0.01, 0.01, 100) == 100   # plafonné au maximum
assert ex.taille_position(37, 0.0020, 0.00001, 1.0, 0.01, 0.01, 100) == 0.18    # arrondi vers le bas

# 9. contrôles
s = ex.calculer_signal(bougies, 5, jour, p(9, 26), cfg)["signal"]
pip = 0.0001
ok = lambda **k: ex.controles(s, k.get("prix", 1.1021), k.get("spread", 0.00002), pip, k.get("now", p(9, 26)), dict(cfg, **k.get("c", {})),
                             k.get("deja", False), k.get("n", 0), k.get("perte", 0), k.get("reel", False))
assert ok() == [], ok()
assert any("RÉEL" in x for x in ok(reel=True, c={"compte_reel_autorise": False}))
assert ok(reel=True, c={"compte_reel_autorise": True}) == []
assert any("déjà un trade" in x for x in ok(deja=True))
assert any("trades_max_jour" in x for x in ok(n=2))
assert any("stop de la journée" in x for x in ok(perte=5))
assert ok(perte=4.99) == []
assert any("trop ancien" in x for x in ok(now=p(9, 40)))
assert any("trop éloigné" in x for x in ok(prix=1.1030))
assert any("spread" in x for x in ok(spread=0.0006))
assert any("trop serré" in x for x in ok(c={"stop_min_pips": 25}))
open(ex.FICHIER_STOP, "w").close()
try:
    assert any("arrêt d'urgence" in x for x in ok())
finally:
    os.remove(ex.FICHIER_STOP)

# 10. budget de la journée : 5 € au total, 2,5 € max par trade, 0,5 % du solde
c5 = dict(cfg, perte_max_jour_euros=5, risque_max_par_trade_euros=2.5, risque_par_trade_pct=0.5)
assert ex.risque_autorise(10000, c5, 0, 0) == 2.5          # plafonné à 2,5 € par trade
assert ex.risque_autorise(200, c5, 0, 0) == 1.0            # 0,5 % de 200 €
assert ex.risque_autorise(10000, c5, 3, 0) == 2.0          # déjà perdu 3 € : il reste 2 €
assert ex.risque_autorise(10000, c5, 2.5, 2.5) == 0.0      # 2,5 perdus + 2,5 en jeu : plus rien
assert ex.risque_autorise(10000, c5, 6, 0) == 0.0
assert ex.risque_autorise(10000, dict(c5, risque_max_par_trade_euros=None), 0, 0) == 5   # sans plafond : budget du jour
# stop de la journée par agent : 2 € pour cet agent, compte à 5 €
ca = dict(c5, perte_max_jour_agent_euros=2)
assert ex.risque_autorise(10000, ca, 0, 0) == 2.0                 # le stop de l'agent est le plus petit
assert ex.risque_autorise(10000, ca, 1, 0, 1, 0) == 1.0           # l'agent a déjà perdu 1 €
assert ex.risque_autorise(10000, ca, 4, 0, 0, 0) == 1.0           # l'autre agent a perdu 4 € : le compte limite
assert ex.risque_autorise(10000, ca, 0.5, 1.5, 0.5, 1.5) == 0.0   # agent : 0,5 perdu + 1,5 en jeu = 2
assert any("de cet agent" in x for x in ex.controles(s, 1.1021, 0.00002, pip, p(9, 26), ca, False, 0, 2, False, 2))
assert ex.controles(s, 1.1021, 0.00002, pip, p(9, 26), ca, False, 0, 1.9, False, 1.9) == []
# règles par marché
assert ex.config_symbole(cfg, "EURJPY")["stop_min_pips"] == 6 and ex.config_symbole(cfg, "EURUSD")["stop_min_pips"] == 5
try:  # une règle du compte ne peut pas être changée par un agent
    ex.config_symbole(dict(cfg, symboles={"EURUSD": {"unite_minutes": 5, "perte_max_jour_euros": 50}}), "EURUSD")
    raise AssertionError("aurait dû refuser")
except SystemExit as e:
    assert "règle du compte" in str(e)

# 11. résultat en R pour le rapport (stop -1R, TP1 +1R, TP2 +2R)
base = {"sens": 1, "entree": 1.1020, "r": 0.0020}
R = lambda res, t1, dernier, obj: ex.resultat_r(dict(base, resultat=res, tp1_touche=t1), dernier, obj)
assert R("stop", False, 1.10, "TP1+TP2") == -1 and R("stop", False, 1.10, "TP1") == -1
assert R("stop", True, 1.10, "TP1+TP2") == 0 and R("stop", True, 1.10, "TP1") == 1 and R("stop", True, 1.10, "TP2") == -1
assert R("tp2", True, 1.11, "TP1+TP2") == 1.5 and R("tp2", True, 1.11, "TP2") == 2
assert abs(R(None, False, 1.1030, "TP1+TP2") - 0.5) < 1e-9          # encore ouvert, +0,5R
assert abs(R(None, True, 1.1050, "TP1+TP2") - 1.25) < 1e-9          # moitié à TP1 (+1R), moitié à +1,5R

# 12. heure de Paris (heure d'été / d'hiver)
from datetime import timezone
assert ex.paris(datetime(2026, 7, 1, 7, 0, tzinfo=timezone.utc)).hour == 9
assert ex.paris(datetime(2026, 11, 5, 8, 0, tzinfo=timezone.utc)).hour == 9
print("Tous les tests passent.")
