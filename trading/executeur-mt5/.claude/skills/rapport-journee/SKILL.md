---
name: rapport-journee
description: Rapport de fin de journée de l'agent principal de trading - trades, prix, argent gagné ou perdu, analyse des marchés EUR/USD et EUR/JPY. Enregistré dans rapports/. Utiliser à la fermeture (17h45), ou quand l'utilisateur demande le rapport, le bilan ou /rapport-journee.
---

# Rapport de fin de journée (agent principal, aucun ordre)

Tu ne passes, ne modifies et ne fermes **aucun ordre**. Tu fais seulement le bilan.

1. Lance `py -I executeur_mt5.py --rapport`. Si MT5 ne répond pas, écris un rapport court qui le dit, et arrête-toi.
2. Pour l'analyse, cherche sur le web (WebSearch) **les nouvelles du jour** qui ont pu faire bouger l'EUR/USD et l'EUR/JPY : banques centrales (BCE, Fed, Banque du Japon), chiffres économiques publiés (inflation, emploi, PMI…). Garde seulement ce qui date d'aujourd'hui, et cite tes sources. Si tu ne trouves rien de fiable, dis-le plutôt que d'inventer.
3. Écris le rapport **en français** dans `rapports/AAAA-MM-JJ.md` (date du jour), puis affiche-le en entier.

## Plan du rapport

```
# Rapport de trading du JJ/MM/AAAA
Compte RÉEL/DÉMO · mode … · solde … €

## En bref
3 lignes maximum : résultat du jour en €, stop de la journée atteint ou non, le fait marquant.

## Les trades
| Agent | Sens | Lots | Entrée (heure) | Sortie (heure) | Comment | Résultat € |
Positions encore ouvertes, s'il y en a.
Total du jour : … €  ·  Stop de la journée : … € (atteint / non atteint)
(En mode à blanc : « Aucun trade réel, mode à blanc » puis les trades que la règle aurait pris.)

## Ce que la règle a donné, marché par marché
Pour EUR/USD puis EUR/JPY : range 9h00-9h15 (taille en pips), signal ou non, issue (stop / TP1 / TP2 / ni l'un ni l'autre),
résultat en R et en € (réel ou virtuel), et pourquoi l'exécuteur a éventuellement refusé (journal).

## Analyse du marché
Pour chaque paire : sens de la journée, amplitude comparée à la moyenne des 20 derniers jours (journée calme ou agitée),
où le prix a fini par rapport au range, et les nouvelles du jour qui expliquent le mouvement (avec sources).

## À retenir
2 ou 3 observations factuelles (ex. « range très étroit : stop sous le minimum, trade sauté »).
Aucun conseil d'investissement, aucune promesse.
```

Règles : chaque chiffre vient de `--rapport` ou d'une source citée, jamais d'une supposition.
Écris « donnée indisponible » quand il manque quelque chose.
