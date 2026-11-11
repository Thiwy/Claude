"""Génère le calendrier .ics du plan trail 40 km (version 3, séances détaillées).

Chaque séance indique : durée, distance estimée, D+, déroulé étape par étape
avec l'allure et la distance de chaque partie, repères d'effort et explication.

Usage : python3 generer_ics.py  -> écrit plan-40km-31-janvier.ics à côté du script.
Les distances sont des estimations (allure moyenne de chaque zone).
"""
import datetime as dt
import os

D = dt.date

# Allures (min/km) : (texte, valeur moyenne utilisée pour estimer la distance)
Z = {
    "Z1": ("7'00–7'40/km", 7.33),
    "Z2": ("6'30–7'00/km", 6.75),
    "Z3": ("5'55–6'15/km", 6.08),
    "Z4": ("5'10–5'25/km", 5.28),
    "TROT": ("7'30–8'00/km", 7.75),
}
NOM = {"Z1": "Z1 récup", "Z2": "Z2 endurance", "Z3": "Z3 allure course", "Z4": "Z4 seuil", "TROT": "trot très lent"}
SL_KMEFFORT_H = 8.0  # vitesse facile en sortie longue trail (km-effort/h), allure Z2 + marche en montée

ALLURES = ("TES ALLURES (sur le plat) : Z1 récup 7'00–7'40/km · Z2 endurance 6'30–7'00 · Z3 allure course 5'55–6'15 · "
           "Z4 seuil 5'10–5'25 · Z5 VMA 4'35–4'50. En trail, pilote au souffle et à la sensation, pas à l'allure.")
CARDIO = "⚠️ Séance dure : à faire après le feu vert du cardiologue. En attendant, remplace-la par le même temps en Z2."


def km(x):
    return f"{x:.1f}".replace(".", ",")


def m(x):
    return f"{round(x * 100) * 10:.0f} m"


def hm(minutes):
    h, mn = divmod(int(round(minutes)), 60)
    return f"{h} h {mn:02d}" if h and mn else (f"{h} h" if h else f"{mn} min")


class Seance:
    def __init__(self):
        self.lignes, self.minutes, self.dist, self.dplus = [], 0.0, 0.0, 0

    def bloc(self, label, mins, zone):
        d = mins / Z[zone][1]
        self.lignes.append(f"{label} : {mins} min en {NOM[zone]} à {Z[zone][0]} (≈ {km(d)} km)")
        self.minutes += mins
        self.dist += d

    def series(self, n, eff_min, eff_zone, rec_min, rec_zone):
        de = eff_min / Z[eff_zone][1]
        dr = rec_min / Z[rec_zone][1]
        self.lignes.append(
            f"{n} × [ {eff_min} min en {NOM[eff_zone]} à {Z[eff_zone][0]} (≈ {m(de)}) + {rec_min} min de récup en "
            f"{NOM[rec_zone]} à {Z[rec_zone][0]} (≈ {m(dr)}) ] → {n * (eff_min + rec_min)} min, ≈ {km(n * (de + dr))} km")
        self.minutes += n * (eff_min + rec_min)
        self.dist += n * (de + dr)

    def escaliers(self, n, eff_min, desc_min):
        dplus = 25 * eff_min
        self.lignes.append(
            f"{n} × [ {eff_min} min de montée d'escaliers en courant, effort 8–9/10 (≈ {dplus} m de D+, environ {8 * eff_min} étages) "
            f"+ redescente en MARCHANT, contrôlée (≈ {hm(desc_min) if desc_min == int(desc_min) else str(int(desc_min)) + ' min 30'}) ] → {round(n * (eff_min + desc_min))} min, ≈ {n * dplus} m de D+")
        self.minutes += n * (eff_min + desc_min)
        self.dplus += n * dplus

    def note(self, txt):
        self.lignes.append(txt)

    def entete(self):
        dp = f"≈ {self.dplus} m" if self.dplus else "aucun (plat)"
        return f"⏱ DURÉE : {hm(self.minutes)}   📏 DISTANCE : ≈ {km(self.dist)} km   ⛰️ D+ : {dp}"

    def texte(self, pourquoi, reperes="", extra=""):
        etapes = "\n".join(f"{i}. {l}" for i, l in enumerate(self.lignes, 1))
        out = f"{self.entete()}\n\nDÉROULÉ :\n{etapes}\n"
        if reperes:
            out += f"\nREPÈRES : {reperes}\n"
        out += f"\nPOURQUOI : {pourquoi}\n"
        if extra:
            out += f"\n{extra}\n"
        return out + f"\n{ALLURES}"


def footing(mins, zone, ld=0, txt_pourquoi=None):
    s = Seance()
    if zone == "Z2" and mins >= 30:
        s.bloc("Mise en route", 10, "Z1")
        s.bloc("Corps de séance", mins - 10, "Z2")
    else:
        s.bloc("Footing", mins, zone)
    if ld:
        s.note(f"À la fin : {ld} lignes droites de 20 s en accélérant progressivement jusqu'à ≈ 4'45/km "
               "(pas un sprint, relâché), 1 min de marche entre chaque")
    if zone == "Z2":
        rep = ("effort 3–4/10, tu parles en phrases complètes. Si la FC s'emballe, ralentis ou marche 30 s. "
               "Note ta FC moyenne : elle doit baisser de semaine en semaine à la même allure.")
        pq = txt_pourquoi or "construire le moteur aérobie : le cœur devient plus efficace, la FC baisse à allure égale."
    else:
        rep = "effort 2/10, tu pourrais chanter. Ça doit te paraître trop lent : c'est le but."
        pq = txt_pourquoi or "relâcher les jambes après la sortie longue et courir plus souvent sans te fatiguer."
    titre = f"{'Footing endurance' if zone == 'Z2' else 'Footing récup'} · {hm(s.minutes)} · ≈ {km(s.dist)} km"
    if ld:
        titre += f" + {ld} lignes droites"
    return titre, s.texte(pq, rep)


def fartlek():
    s = Seance()
    s.bloc("Échauffement", 15, "Z2")
    s.series(6, 1, "Z4", 2, "TROT")
    s.bloc("Retour au calme", 12, "Z1")
    return (f"Fractionné fartlek 6 × 1 min · {hm(s.minutes)} · ≈ {km(s.dist)} km",
            s.texte("réveiller la vitesse en douceur.", "efforts à 7/10 : tu ne peux dire que quelques mots. "
                    "Pendant la récup, tu dois retrouver ton souffle.", CARDIO))


def escaliers(n, eff):
    s = Seance()
    s.bloc("Échauffement (jusqu'aux escaliers)", 15, "Z2")
    s.escaliers(n, eff, 1.5 if eff == 1 else 2)
    s.bloc("Retour au calme", 15, "Z2")
    return (f"Fractionné escaliers {n} × {eff} min · {hm(s.minutes)} · ≈ {km(s.dist)} km · ≈ {s.dplus} m D+",
            s.texte("force et puissance en montée. La redescente contrôlée travaille les cuisses en freinant : "
                    "c'est ce qui t'a manqué au marathon.",
                    "montée en petites foulées dynamiques, buste penché en avant, effort 8–9/10. "
                    "Redescente en marchant, sans te laisser tomber sur les marches. Pas d'escaliers ? Un pont ou une rampe de parking.",
                    CARDIO))


def seuil(n):
    s = Seance()
    s.bloc("Échauffement", 15, "Z2")
    s.series(n, 3, "Z4", 2, "TROT")
    s.bloc("Retour au calme", 15, "Z2")
    return (f"Fractionné seuil {n} × 3 min · {hm(s.minutes)} · ≈ {km(s.dist)} km",
            s.texte("repousser ton seuil, l'allure que tu tiens longtemps sans exploser.",
                    "effort 7–8/10, tu ne peux dire que 2–3 mots. Sur tapis incliné à 6–8 % : ≈ 8–9 km/h au lieu de 5'10–5'25/km. "
                    "Sinon, enchaîne des montées d'escaliers ou de pont pendant les 3 min.", CARDIO))


def allure_course():
    s = Seance()
    s.bloc("Échauffement", 15, "Z2")
    s.series(3, 10, "Z3", 2, "TROT")
    s.bloc("Retour au calme", 10, "Z1")
    return (f"Allure course 3 × 10 min · {hm(s.minutes)} · ≈ {km(s.dist)} km",
            s.texte("mémoriser l'effort du jour J.", "effort 5–6/10, phrases courtes. Si possible sur un parcours vallonné."))


def affutage():
    s = Seance()
    s.bloc("Échauffement", 27, "Z2")
    s.series(6, 1, "Z4", 1, "TROT")
    s.bloc("Retour au calme", 6, "Z1")
    return (f"Affûtage 6 × 1 min · {hm(s.minutes)} · ≈ {km(s.dist)} km",
            s.texte("garder du rythme pendant que le volume baisse (c'est normal).", "efforts à 7/10, pas à fond.", CARDIO))


def sortie_longue(mins, dplus, gph, bloc=False, repetition=False):
    dist = mins / 60 * SL_KMEFFORT_H - dplus / 100
    s = Seance()
    s.minutes, s.dist, s.dplus = mins, dist, dplus
    s.note(f"15 premières minutes en Z1 à {Z['Z1'][0]}, très tranquille")
    s.note(f"Puis Z2 : {Z['Z2'][0]} sur le plat (6'45–7'30/km si le terrain est cassant), effort 3–4/10")
    s.note(f"Montées raides (≈ {dplus} m de D+ au total) : en MARCHANT, d'un pas rapide, mains sur les cuisses si c'est très raide")
    s.note("Descentes : relâché, petits pas rapides, regard 3–4 m devant, sans freiner fort")
    if gph:
        tot = int(5 * round(gph * mins / 60 / 5))
        s.note(f"Manger : à partir de 45 min, ≈ {gph} g de glucides par heure, soit ≈ {tot} g au total "
               f"(≈ {max(1, round(tot / 22))} gels ou l'équivalent : compote ≈ 15–20 g, banane ≈ 25 g, pâte de fruit ≈ 12 g). Boire selon la soif.")
    else:
        s.note("Manger : pas indispensable (moins de 1 h 30). Emporte de l'eau.")
    s.note("Dernières 10 minutes : en Z1 pour finir")
    rep = ("phrases complètes tout du long. Note : FC moyenne, FC sur la dernière heure (dérive ?), état des jambes "
           "dans les 30 dernières minutes. Pas de relief ? Cherche un parcours avec des montées répétées (colline, escaliers, terril).")
    extra = ""
    if bloc:
        extra = "WEEK-END BLOC : demain, tu recours sur les jambes fatiguées. Reste bien en Z2 aujourd'hui."
    if repetition:
        extra = ("RÉPÉTITION GÉNÉRALE : fais tout comme le jour J (chaussures, sac, tenue, petit-déjeuner, ravitaillement, "
                 "allure prudente). Après la sortie, note ce qui a marché ou non.")
    titre = f"Sortie longue · {hm(mins)} · ≈ {km(dist)} km · {dplus} m D+"
    if repetition:
        titre += " · RÉPÉTITION GÉNÉRALE"
    return titre, s.texte("c'est la séance n°1 : les jambes apprennent à durer, tu travailles la descente "
                          "et ton estomac s'habitue à manger en courant.", rep, extra)


VELO = ("⏱ DURÉE : ≈ 50–60 min   📏 DISTANCE : 20 km\n\nDÉROULÉ :\n1. Vélo 20 km FACILE (Z1–Z2) : tu peux parler sans effort\n"
        "2. Ensuite, gainage léger 15 min : planche 3 × 40 s · planche latérale 3 × 30 s par côté · dead bug 3 × 10 · "
        "montées sur pointes 3 × 12 · descente lente sur 1 jambe 3 × 10 par jambe\n\n"
        "POURQUOI : récupérer de la sortie longue (le vélo fait circuler le sang sans choc) et renforcer les mollets.")
RENFO = ("⏱ DURÉE : 25–30 min (pas de course aujourd'hui)\n\nDÉROULÉ (3 séries de chaque, 1 min de pause entre les séries) :\n"
         "1. Step-down lent sur une marche : 10 par jambe, 3–4 s pour descendre\n2. Squat bulgare : 10 par jambe\n"
         "3. Fente arrière : 10 par jambe\n4. Chaise contre le mur : 40 s\n"
         "5. Montées sur pointes : 12 jambes tendues + 12 genoux fléchis\n6. Descente lente sur 1 jambe (mollet) : 10 par jambe\n"
         "7. Pont fessier sur 1 jambe : 12 par jambe\n8. Planche : 40 s\n\n"
         "POURQUOI : des cuisses et des mollets plus forts encaissent mieux les descentes et la fin de course.")
REPOS = "Repos complet. Le corps progresse pendant la récupération, pas pendant l'effort. Pense à bien dormir (7–9 h)."

# --- Programme (semaines « normales ») ---------------------------------------
P = {}


def sem(w, **jours):
    P[w] = jours


BLOC_DIM = "week-end bloc : courir sur les jambes fatiguées de la veille, comme en fin de course."
sem(1, jeu=footing(40, "Z2"), sam=sortie_longue(75, 200, 0))
sem(2, mar=fartlek(), jeu=footing(40, "Z2"), sam=sortie_longue(90, 300, 35), dim=footing(30, "Z1"))
sem(3, mar=escaliers(6, 1), jeu=footing(45, "Z2"), sam=sortie_longue(105, 400, 35), dim=footing(30, "Z1"))
sem(4, mar=footing(40, "Z2", ld=4, txt_pourquoi="semaine allégée : le corps assimile le travail. Les lignes droites gardent la foulée vive."),
    jeu=footing(40, "Z2"), sam=sortie_longue(75, 250, 0))
sem(5, mar=escaliers(8, 1), jeu=footing(45, "Z2"), sam=sortie_longue(120, 500, 40), dim=footing(35, "Z1"))
sem(6, mar=seuil(5), jeu=footing(45, "Z2"), sam=sortie_longue(135, 600, 40, bloc=True), dim=footing(45, "Z2", txt_pourquoi=BLOC_DIM))
sem(8, mar=escaliers(6, 2), jeu=footing(45, "Z2"), sam=sortie_longue(165, 700, 50), dim=footing(35, "Z1"))
sem(9, mar=seuil(6), jeu=footing(50, "Z2"), sam=sortie_longue(195, 900, 60, repetition=True), dim=footing(30, "Z1"))
sem(10, mar=allure_course(), jeu=footing(45, "Z2"), sam=sortie_longue(135, 600, 60, bloc=True), dim=footing(60, "Z2", txt_pourquoi=BLOC_DIM))
sem(11, mar=affutage(), jeu=footing(40, "Z2"), sam=sortie_longue(90, 300, 60))

ev = []
JOUR = {"mar": 1, "jeu": 3, "sam": 5, "dim": 6}
EMO = {"mar": "🏃", "jeu": "🏃", "sam": "⛰️", "dim": "🏃"}
start = D(2026, 11, 9)
for w in range(1, 13):
    lun = start + dt.timedelta(weeks=w - 1)
    ev.append((lun, "🚴 Vélo 20 km facile + gainage", VELO))
    if w in P:
        for j, (t, de) in P[w].items():
            ev.append((lun + dt.timedelta(JOUR[j]), f"{EMO[j]} {t}", de))
        if w <= 10:
            ev.append((lun + dt.timedelta(2), "💪 Renfo complet 30 min", RENFO))
        ev.append((lun + dt.timedelta(4), "😴 Repos", REPOS))

# Semaine 7 (fêtes)
t, de = footing(45, "Z2", ld=6, txt_pourquoi="semaine allégée des fêtes : on entretient sans se fatiguer.")
ev += [(D(2026, 12, 22), "🏃 " + t, de), (D(2026, 12, 23), "💪 Renfo complet 30 min", RENFO)]
t, de = footing(30, "Z1")
ev += [(D(2026, 12, 24), "🏃 " + t, de), (D(2026, 12, 25), "😴 Repos (Noël)", REPOS)]
t, de = sortie_longue(135, 500, 40)
ev.append((D(2026, 12, 26), "⛰️ " + t, de))

# Semaine 12 (course)
t, de = footing(35, "Z2", ld=4, txt_pourquoi="garder les jambes vives sans fatigue avant la course.")
ev.append((D(2027, 1, 26), "🏃 " + t, de))
t, de = footing(25, "Z1", txt_pourquoi="réveiller les jambes. Ensuite, 3 accélérations de 20 s, relâchées.")
ev.append((D(2027, 1, 28), "🏃 " + t, de))
ev.append((D(2027, 1, 29), "😴 Repos · prépare ton sac", "Repos. Prépare ton sac, tes gels et ta tenue. Repas normaux, riches en glucides."))
ev.append((D(2027, 1, 30), "😴 Repos (ou 15 min de marche)",
           "Repos. Repas riche en glucides et pauvre en fibres. Rien de nouveau (ni chaussures, ni gels, ni repas). Couche-toi tôt."))
ev.append((D(2027, 1, 31), "🏁 TRAIL 40 km · 1000 m D+",
           "⏱ OBJECTIF : 5 h–6 h (réaliste ≈ 5 h 30)   📏 40 km   ⛰️ 1000 m D+\n\n"
           "PLAN DE COURSE :\n1. Petit-déjeuner riche en glucides 2–3 h avant le départ\n"
           "2. 10 premiers km : effort 4–5/10, ça doit paraître facile\n"
           "3. Marche toutes les montées raides dès le début\n"
           "4. Mange dès 30–45 min, puis toutes les 20–30 min : ≈ 50–70 g de glucides/h, soit ≈ 300–350 g au total "
           "(≈ 12–15 gels ou l'équivalent). Bois selon la soif\n"
           "5. Descentes relâchées : c'est là que se joue la fin de course\n"
           "6. Après 30 km : si tu te sens bien, relance doucement\n\nBonne course ! 💪"))

# --- Écriture ICS ------------------------------------------------------------


def esc(s):
    return s.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def fold(line):
    b = line.encode()
    out = []
    while len(b) > 73:
        cut = 73
        while (b[cut] & 0xC0) == 0x80:
            cut -= 1
        out.append(b[:cut].decode())
        b = b[cut:]
    out.append(b.decode())
    return "\r\n ".join(out)


debut = D(2026, 11, 11)  # plan v3 démarré le 11/11/2026
L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//coach-trail//FR", "CALSCALE:GREGORIAN",
     "X-WR-CALNAME:Coach trail – 40 km du 31 janvier"]
now = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
garde = sorted(e for e in ev if e[0] >= debut)
for i, (d, t, de) in enumerate(garde):
    L += ["BEGIN:VEVENT", f"UID:coach-trail-v3b-{d.isoformat()}-{i}@coach-trail", f"DTSTAMP:{now}",
          f"DTSTART;VALUE=DATE:{d:%Y%m%d}", f"DTEND;VALUE=DATE:{d + dt.timedelta(1):%Y%m%d}",
          fold("SUMMARY:" + esc(t)), fold("DESCRIPTION:" + esc(de)), "TRANSP:TRANSPARENT", "END:VEVENT"]
L.append("END:VCALENDAR")
sortie = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plan-40km-31-janvier.ics")
with open(sortie, "w", newline="") as f:
    f.write("\r\n".join(L) + "\r\n")
print(len(garde), "événements ->", sortie)
