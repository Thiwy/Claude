import datetime as dt, uuid
D=dt.date
Z2="Endurance fondamentale : tu dois pouvoir parler en phrases complètes. Allure indicative 6'30–7'00/km, plus lent si la FC s'emballe. Marche si besoin."
QUAL="Échauffement 15 min Z2. Efforts en montée à un effort dur (Z4–Z5), redescente en marchant/trottinant de façon contrôlée (= travail de descente). Retour au calme 10 min. Pas de côtes ? Escaliers, pont, parking ou tapis incliné 8–12 %. ⚠️ Séance dure : à faire après le feu vert du cardiologue (sinon remplacer par un footing Z2)."
SL="Sortie longue Z2 du début à la fin. Marche dans les montées raides dès le début. Descentes relâchées, pas courts. Manger dès 1 h 30 de sortie (nov.–déc. : 30–40 g de glucides/h ; janv. : 50–70 g/h). Note : FC moyenne, FC dernière heure, état des jambes en fin de sortie."
RENFO="Renfo complet 25–30 min : step-down lent (3–4 s en descente) 3×10/jambe, squat bulgare 3×10, fente arrière 3×10, chaise 3×40 s, montées sur pointes jambes tendues 3×12 puis genoux fléchis 3×12, descente lente sur 1 jambe 3×10, pont fessier 1 jambe 3×12, planche 3×40 s, planche latérale 3×30 s."
RLEGER="Renfo léger 15 min : gainage (planche, planche latérale, dead bug) + mollets. Pas de travail lourd des jambes avant la sortie longue."
VELO="Vélo 20 km FACILE (Z1–Z2) : c'est de l'endurance pour le cœur sans choc pour les jambes."
ev=[]
def add(d,t,desc): ev.append((d,t,desc))
weeks={
1:("40 min Z2 + 4 lignes droites",None,"40 min Z2",("1 h 15 · 200 m D+",None)),
2:("45 min fartlek : 6 × (1 min vite / 2 min lent)",None,"45 min Z2",("1 h 30 · 300 m D+",None)),
3:("50 min : escaliers 6 × 1 min",None,"45 min Z2",("1 h 45 · 400 m D+",None)),
4:("RÉCUP 40 min Z2",None,"40 min Z2",("1 h 15 · 250 m D+",None)),
5:("55 min : escaliers 8 × 1 min","30–35 min Z1 (facultatif, si mollets OK)","45 min Z2",("2 h · 500 m D+",None)),
6:("55 min : escaliers/tapis 5 × 3 min","30–35 min Z1 (facultatif, si mollets OK)","40 min Z2",("2 h · 600 m D+","45 min Z2 (bloc : jambes fatiguées de la veille)")),
9:("PIC 1 h : tapis/escaliers 6 × 3 min","30–35 min Z1 (facultatif, si mollets OK)","45 min Z2",("3 h–3 h 15 · 900 m D+ · RÉPÉTITION GÉNÉRALE",None)),
10:("55 min dont 3 × 12 min allure course","30–35 min Z1 (facultatif, si mollets OK)","40 min Z2",("2 h 15 · 600 m D+","1 h Z2 (bloc)")),
11:("AFFÛTAGE 45 min dont 6 × 1 min vif",None,"35 min Z2",("1 h 30 · 300 m D+",None)),
}
start=D(2026,11,9)
for w in range(1,13):
    mon=start+dt.timedelta(weeks=w-1)
    late=w>=11
    add(mon,"🚴 Vélo 20 km + "+("gainage léger" if late else "renfo complet"), VELO+"\n\n"+(RLEGER.replace(" avant la sortie longue","")+" Plus de renfo lourd des jambes dans les 10 derniers jours." if late else RENFO))
    add(mon+dt.timedelta(1),"🚴 Vélo 20 km facile",VELO)
    if w in weeks:
        q,j,v,(sl,dim)=weeks[w]
        qd = Z2 if ("Z2" in q and "dont" not in q and "escaliers" not in q) else QUAL
        if w==1 or w==4: qd=Z2
        if w==2: qd="Fartlek à plat : après 15 min Z2, 6 × (1 min vite / 2 min lent), puis 10 min calmes. "+Z2
        if w==10: qd="15 min Z2, puis 3 × 12 min à l'allure prévue en course (effort Z3 : phrases courtes), 3 min lent entre chaque, 10 min calmes. Si possible sur un parcours vallonné."
        if w==11: qd="Affûtage : 45 min Z2 dont 6 × 1 min vif (pas à fond) pour garder du rythme. Le volume baisse, c'est normal."
        add(mon+dt.timedelta(2),"🏃 "+q,qd)
        if j: add(mon+dt.timedelta(3),"🏃 "+j,Z2)
        add(mon+dt.timedelta(4),"🏃 "+v+" + renfo léger",Z2+"\n\n"+(RLEGER if not late else "Pas de renfo des jambes (affûtage)."))
        add(mon+dt.timedelta(5),"⛰️ Sortie longue "+sl,SL+(("\n\nRÉPÉTITION GÉNÉRALE : comme le jour J (chaussures, sac, tenue, petit-déjeuner, ravitaillement 50–70 g/h, allure prudente).") if w==9 else ""))
        if dim: add(mon+dt.timedelta(6),"🏃 "+dim,Z2+" Objectif : courir sur des jambes fatiguées de la veille.")
    elif w==7:
        add(D(2026,12,23),"🏃 45 min Z2 (semaine des fêtes)",Z2)
        add(D(2026,12,26),"⛰️ Sortie longue 2 h 15 · 500 m D+",SL)
    elif w==8:
        add(D(2026,12,30),"🏃 1 h : escaliers 6 × 2 min + descentes contrôlées",QUAL)
        add(D(2026,12,31),"🏃 40 min Z2",Z2)
        add(D(2027,1,2),"⛰️ Sortie longue 2 h 45 · 700 m D+",SL)
    elif w==12:
        add(D(2027,1,27),"🏃 35 min Z2 + 4 accélérations",Z2+" Finis par 4 accélérations progressives de 20 s.")
        add(D(2027,1,29),"🏃 25 min très facile","Footing très facile pour garder les jambes en éveil. Prépare ton sac et ton ravitaillement.")
        add(D(2027,1,30),"😴 Repos (ou 15 min de marche)","Repos. Repas riche en glucides et pauvre en fibres. Rien de nouveau. Coucher tôt.")
        add(D(2027,1,31),"🏁 TRAIL 40 km · 1000 m D+","Objectif : finir en bon état. Estimation 5 h–6 h (réaliste ≈ 5 h 30).\n- Les 10 premiers km doivent paraître faciles.\n- Marche toutes les montées raides dès le début.\n- Mange dès 30–45 min puis toutes les 20–30 min (≈ 50–70 g de glucides/h). Bois selon la soif.\n- Descentes relâchées.\n- Petit-déjeuner riche en glucides 2–3 h avant le départ.\nBonne course ! 💪")
def esc(s): return s.replace("\\","\\\\").replace(",","\\,").replace(";","\;").replace("\n","\\n")
def fold(line):
    b=line.encode(); out=[]
    while len(b)>73:
        cut=73
        while (b[cut]&0xC0)==0x80: cut-=1
        out.append(b[:cut].decode()); b=b[cut:]
    out.append(b.decode()); return "\r\n ".join(out)
L=["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//coach-trail//FR","CALSCALE:GREGORIAN","X-WR-CALNAME:Coach trail – 40 km du 31 janvier"]
now=dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
for i,(d,t,desc) in enumerate(sorted(ev)):
    L+= ["BEGIN:VEVENT",f"UID:coach-trail-{d.isoformat()}-{i}@coach-trail",f"DTSTAMP:{now}",f"DTSTART;VALUE=DATE:{d:%Y%m%d}",f"DTEND;VALUE=DATE:{d+dt.timedelta(1):%Y%m%d}",fold("SUMMARY:"+esc(t)),fold("DESCRIPTION:"+esc(desc)),"TRANSP:TRANSPARENT","END:VEVENT"]
L.append("END:VCALENDAR")
import os; open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"plan-40km-31-janvier.ics"),"w",newline="").write("\r\n".join(L)+"\r\n")
print(len(ev),"séances")
for d,t,_ in sorted(ev)[:9]: print(d,t)
