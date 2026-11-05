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
                             k.get("deja", False), k.get("n", 0), k.get("perte", 0), 10000, k.get("reel", False))
assert ok() == [], ok()
assert any("RÉEL" in x for x in ok(reel=True))
assert ok(reel=True, c={"compte_reel_autorise": True}) == []
assert any("déjà un trade" in x for x in ok(deja=True))
assert any("trades_max_jour" in x for x in ok(n=2))
assert any("perte max" in x for x in ok(perte=200))
assert any("trop ancien" in x for x in ok(now=p(9, 40)))
assert any("trop éloigné" in x for x in ok(prix=1.1030))
assert any("spread" in x for x in ok(spread=0.0006))
assert any("trop serré" in x for x in ok(c={"stop_min_pips": 25}))
open(ex.FICHIER_STOP, "w").close()
try:
    assert any("arrêt d'urgence" in x for x in ok())
finally:
    os.remove(ex.FICHIER_STOP)

# 10. heure de Paris (heure d'été / d'hiver)
from datetime import timezone
assert ex.paris(datetime(2026, 7, 1, 7, 0, tzinfo=timezone.utc)).hour == 9
assert ex.paris(datetime(2026, 11, 5, 8, 0, tzinfo=timezone.utc)).hour == 9
print("Tous les tests passent.")
