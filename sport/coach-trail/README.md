# Coach trail

Skill Claude Code qui joue le rôle de coach de trail running. Il répond en français sur l'entraînement,
l'intensité et les zones cardiaques, le dénivelé, la descente, le renforcement, l'affûtage, la nutrition
et la stratégie de course. Il construit des plans semaine par semaine et les ajuste selon tes retours.

- `.claude/skills/coach-trail/SKILL.md` : le rôle du coach et ses règles (questions, ajustements, sécurité).
- `references/principes-entrainement.md` : la base de connaissances, avec les sources.
- `references/athlete-profile.md` : mon profil de coureur (historique, objectif, journal). Le coach le met à jour.
- `references/plan-objectif.md` : le plan en cours (trail 40 km / 1000 m D+, 1er février 2027).

## Utilisation

Copie le dossier `.claude/skills/coach-trail/` dans le `.claude/skills/` de ton projet (ou dans `~/.claude/skills/`),
lance `claude`, puis parle de course, par exemple :

> Voici ma semaine : mardi 45 min, jeudi côtes, samedi 2 h. Ajuste mon plan.

Le skill se déclenche tout seul dès qu'on parle de course. Pour l'appeler directement : `/coach-trail`.

Sur claude.ai, tu peux aussi importer le dossier zippé dans Paramètres → Capacités → Skills.

## Calendrier

`calendrier/plan-40km-31-janvier.ics` contient toutes les séances du plan (avec leur description).
Importe-le dans Google Agenda (ordinateur : Paramètres → Importer et exporter → Importer),
dans Apple Calendrier (double-clic sur le fichier) ou dans Outlook (Fichier → Ouvrir et exporter → Importer).
