"""Génère le calendrier .ics du plan trail 40 km (version 3).

Usage : python3 generer_ics.py  -> écrit plan-40km-31-janvier.ics à côté du script.
"""
import datetime as dt
import os

D = dt.date
ALLURES = ("Tes allures (sur le plat) : Z1 récup 7'00–7'40/km · Z2 endurance 6'30–7'00 · "
           "Z3 allure course 5'55–6'15 · Z4 seuil 5'10–5'25 · Z5 VMA 4'35–4'50. "
           "En trail, pilote à la sensation et au souffle, pas à l'allure.")
CARDIO = "⚠️ Séance dure : à faire après le feu vert du cardiologue. Sinon, remplace-la par 45 min en Z2."

DESC = {
    "Z2": ("POURQUOI : construire le moteur aérobie. Le cœur devient plus efficace et la FC baisse à allure égale.\n"
           "COMMENT : 6'30–7'00/km sur le plat, effort 3–4/10. Tu dois pouvoir parler en phrases complètes du début à la fin. "
           "Si la FC s'emballe, marche 30 s puis repars plus lentement.\n"
           "À NOTER : ta FC moyenne (elle doit baisser de semaine en semaine)."),
    "Z1": ("POURQUOI : relâcher les jambes après la sortie longue et ajouter de la fréquence sans fatigue.\n"
           "COMMENT : 7'00–7'40/km, effort 2/10, plutôt sur du plat. Ça doit te paraître trop lent : c'est le but."),
    "FARTLEK": ("POURQUOI : réveiller la vitesse en douceur.\n"
                "COMMENT : 15 min en Z2 (6'30–7'00/km), puis 6 × (1 min à 5'10–5'25/km, effort 7/10, "
                "et 2 min de trot très lent), puis 10 min en Z1.\n" + CARDIO),
    "ESC": ("POURQUOI : force et puissance en montée. La redescente contrôlée travaille les cuisses en freinant : "
            "c'est ce qui t'a manqué au marathon.\n"
            "COMMENT : 15 min en Z2. Monte des escaliers (ou un pont, une rampe de parking) en courant, effort 8–9/10, "
            "petites foulées dynamiques, buste penché en avant. Redescends en marchant ou en trottinant, de façon contrôlée "
            "(c'est ta récup). 10 min en Z1 pour finir.\n" + CARDIO),
    "Z4": ("POURQUOI : repousser ton seuil, l'allure que tu tiens longtemps sans exploser.\n"
           "COMMENT : idéalement sur tapis incliné à 6–10 %, sinon en enchaînant des montées d'escaliers ou de pont. "
           "15 min en Z2, puis les efforts de 3 min à effort 7–8/10 (tu ne peux dire que 2–3 mots ; ≈ 5'10–5'25/km si c'est à plat), "
           "avec 2 min de trot entre chaque. 10 min en Z1.\n" + CARDIO),
    "Z3": ("POURQUOI : mémoriser l'effort du jour J.\n"
           "COMMENT : 15 min en Z2, puis 3 × 12 min à 5'55–6'15/km (effort 5–6/10, phrases courtes), 3 min lentes entre chaque, "
           "puis 10 min en Z1. Si possible, sur un parcours vallonné."),
    "LD": ("LIGNES DROITES : à la fin du footing, 15–20 s en accélérant progressivement jusqu'à ≈ 4'45/km. "
           "Ce n'est pas un sprint, reste relâché. Récupère en marchant 1 min."),
    "SL": ("POURQUOI : c'est la séance n°1. Les jambes apprennent à durer, tu travailles la descente et ton estomac s'habitue à manger en courant.\n"
           "COMMENT : Z2 du début à la fin (6'45–7'30/km sur le plat, effort 3–4/10, phrases complètes). "
           "MARCHE DANS TOUTES LES MONTÉES RAIDES dès le début. En descente : relâché, petits pas rapides, regard 3–4 m devant.\n"
           "MANGER : dès 1 h 30 de sortie. 30–40 g de glucides par heure en novembre-décembre, 50–70 g par heure en janvier "
           "(1 gel ≈ 20–25 g, 1 compote ≈ 15–20 g, 1 banane ≈ 25 g).\n"
           "À NOTER : FC moyenne, FC sur la dernière heure, état des jambes dans les 30 dernières minutes."),
    "BLOC": ("WEEK-END BLOC : tu cours sur les jambes fatiguées de la veille, comme en fin de course.\n"),
    "RENFO": ("POURQUOI : des cuisses et des mollets plus forts encaissent mieux les descentes et la fin de course.\n"
              "3 SÉRIES DE : step-down lent (3–4 s en descente) 10 par jambe · squat bulgare 10 par jambe · fente arrière 10 par jambe · "
              "chaise contre le mur 40 s · montées sur pointes jambes tendues 12 puis genoux fléchis 12 · descente lente sur 1 jambe (mollet) "
              "10 par jambe · pont fessier sur 1 jambe 12 par jambe · planche 40 s."),
    "RLEGER": ("15 min : planche 3 × 40 s · planche latérale 3 × 30 s par côté · dead bug 3 × 10 · "
               "montées sur pointes 3 × 12 · descente lente sur 1 jambe 3 × 10 par jambe."),
    "VELO": "Vélo 20 km FACILE (Z1–Z2) : de l'endurance pour le cœur sans choc pour les jambes. Ne force pas.",
    "REPOS": "Repos complet. Le corps progresse pendant la récupération, pas pendant l'effort.",
}

ev = []


def add(d, titre, desc):
    ev.append((d, titre, desc + "\n\n" + ALLURES))


# (mardi, jeudi, samedi, dimanche) ; chaque entrée = (titre, code de description) ou None
SEM = {
    1: (None, ("40 min Z2 endurance", "Z2"), ("Sortie longue 1 h 15 · 200 m D+", "SL"), None),
    2: (("45 min fartlek 6 × 1 min", "FARTLEK"), ("40 min Z2 endurance", "Z2"), ("Sortie longue 1 h 30 · 300 m D+", "SL"), ("30 min Z1 récup", "Z1")),
    3: (("50 min escaliers 6 × 1 min", "ESC"), ("45 min Z2 endurance", "Z2"), ("Sortie longue 1 h 45 · 400 m D+", "SL"), ("30 min Z1 récup", "Z1")),
    4: (("RÉCUP 40 min Z2 + 4 lignes droites", "Z2+LD"), ("40 min Z2 endurance", "Z2"), ("Sortie longue 1 h 15 · 250 m D+", "SL"), None),
    5: (("55 min escaliers 8 × 1 min", "ESC"), ("45 min Z2 endurance", "Z2"), ("Sortie longue 2 h · 500 m D+", "SL"), ("35 min Z1 récup", "Z1")),
    6: (("55 min tapis/escaliers 5 × 3 min Z4", "Z4"), ("45 min Z2 endurance", "Z2"), ("Sortie longue 2 h 15 · 600 m D+ (bloc)", "SL"), ("45 min Z2 (bloc)", "BLOC+Z2")),
    8: (("1 h escaliers 6 × 2 min", "ESC"), ("45 min Z2 endurance", "Z2"), ("Sortie longue 2 h 45 · 700 m D+", "SL"), ("35 min Z1 récup", "Z1")),
    9: (("PIC 1 h tapis/escaliers 6 × 3 min Z4", "Z4"), ("50 min Z2 endurance", "Z2"), ("Sortie longue 3 h–3 h 15 · 900 m D+ · RÉPÉTITION GÉNÉRALE", "SL"), ("30 min Z1 récup", "Z1")),
    10: (("55 min dont 3 × 12 min allure course Z3", "Z3"), ("45 min Z2 endurance", "Z2"), ("Sortie longue 2 h 15 · 600 m D+ (bloc)", "SL"), ("1 h Z2 (bloc)", "BLOC+Z2")),
    11: (("AFFÛTAGE 45 min dont 6 × 1 min Z4", "AFF"), ("40 min Z2 endurance", "Z2"), ("Sortie longue 1 h 30 · 300 m D+", "SL"), None),
}


def desc(code):
    if code == "Z2+LD":
        return DESC["Z2"] + "\n" + DESC["LD"] + "\nSemaine allégée : le corps assimile le travail."
    if code == "BLOC+Z2":
        return DESC["BLOC"] + DESC["Z2"]
    if code == "AFF":
        return ("AFFÛTAGE : le volume baisse, c'est normal. 30 min en Z2, puis 6 × 1 min à 5'10–5'25/km (effort 7/10, pas à fond), "
                "1 min de trot entre chaque, puis 5 min en Z1.")
    return DESC[code]


start = D(2026, 11, 9)
debut = D(2026, 11, 11)  # le plan v3 démarre aujourd'hui
for w in range(1, 13):
    lun = start + dt.timedelta(weeks=w - 1)
    tard = w >= 11
    add(lun, "🚴 Vélo 20 km + gainage léger", DESC["VELO"] + "\n\n" + DESC["RLEGER"])
    add(lun + dt.timedelta(1), "🚴 Vélo 20 km facile", DESC["VELO"])
    if not tard and w not in (7,):
        add(lun + dt.timedelta(2), "💪 Renfo complet 30 min", DESC["RENFO"])
    if w in SEM:
        mar, jeu, sam, dim = SEM[w]
        if mar:
            add(lun + dt.timedelta(1), "🏃 " + mar[0], desc(mar[1]))
        add(lun + dt.timedelta(3), "🏃 " + jeu[0], desc(jeu[1]))
        extra = ("\n\nRÉPÉTITION GÉNÉRALE : fais tout comme le jour J (chaussures, sac, tenue, petit-déjeuner, "
                 "ravitaillement 50–70 g/h, allure prudente)." if w == 9 else "")
        add(lun + dt.timedelta(5), "⛰️ " + sam[0], DESC["SL"] + extra)
        if dim:
            add(lun + dt.timedelta(6), "🏃 " + dim[0], desc(dim[1]))
    elif w == 7:
        add(D(2026, 12, 22), "🏃 45 min Z2 + 6 lignes droites (fêtes)", DESC["Z2"] + "\n" + DESC["LD"] + "\nSemaine allégée des fêtes.")
        add(D(2026, 12, 23), "💪 Renfo complet 30 min", DESC["RENFO"])
        add(D(2026, 12, 24), "🏃 30 min Z1 récup", DESC["Z1"])
        add(D(2026, 12, 26), "⛰️ Sortie longue 2 h 15 · 500 m D+", DESC["SL"])
    elif w == 12:
        add(D(2027, 1, 26), "🏃 35 min Z2 + 4 accélérations", DESC["Z2"] + "\n" + DESC["LD"])
        add(D(2027, 1, 28), "🏃 25 min Z1 + 3 accélérations", DESC["Z1"] + "\n" + DESC["LD"])
        add(D(2027, 1, 30), "😴 Repos ou 15 min de marche",
            "Repos. Repas riche en glucides et pauvre en fibres. Rien de nouveau (ni chaussures, ni gels, ni repas). "
            "Prépare ton sac. Couche-toi tôt.")
        add(D(2027, 1, 31), "🏁 TRAIL 40 km · 1000 m D+",
            "Objectif : finir en bon état. Estimation 5 h–6 h (réaliste ≈ 5 h 30).\n"
            "- Petit-déjeuner riche en glucides 2–3 h avant le départ.\n"
            "- Les 10 premiers km doivent paraître faciles (effort 4–5/10).\n"
            "- Marche toutes les montées raides dès le début.\n"
            "- Mange dès 30–45 min, puis toutes les 20–30 min (≈ 50–70 g de glucides/h). Bois selon la soif.\n"
            "- Descentes relâchées : c'est là que se joue la fin de course.\nBonne course ! 💪")
    # vendredi repos
    if w not in (12,):
        add(lun + dt.timedelta(4), "😴 Repos", DESC["REPOS"])


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


L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//coach-trail//FR", "CALSCALE:GREGORIAN",
     "X-WR-CALNAME:Coach trail – 40 km du 31 janvier"]
now = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
garde = sorted(e for e in ev if e[0] >= debut)
for i, (d, t, de) in enumerate(garde):
    L += ["BEGIN:VEVENT", f"UID:coach-trail-v3-{d.isoformat()}-{i}@coach-trail", f"DTSTAMP:{now}",
          f"DTSTART;VALUE=DATE:{d:%Y%m%d}", f"DTEND;VALUE=DATE:{d + dt.timedelta(1):%Y%m%d}",
          fold("SUMMARY:" + esc(t)), fold("DESCRIPTION:" + esc(de)), "TRANSP:TRANSPARENT", "END:VEVENT"]
L.append("END:VCALENDAR")
sortie = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plan-40km-31-janvier.ics")
with open(sortie, "w", newline="") as f:
    f.write("\r\n".join(L) + "\r\n")
print(len(garde), "événements ->", sortie)
