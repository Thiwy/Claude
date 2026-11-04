---
name: scan-marches
description: Lance les 4 agents d'analyse (bot-or, bot-eurusd, bot-eurjpy, bot-eth) sur TradingView et donne un résumé. Lecture seule, aucun ordre. Utiliser quand l'utilisateur demande le scan des marchés, le point du matin ou /scan-marches.
---

# Scan des 4 marchés

1. Appelle `tv_health_check`. Si TradingView ne répond pas, propose `tv_launch` et attends l'accord de l'utilisateur.
2. Note le symbole et l'unité de temps actuels avec `chart_get_state`, pour les remettre à la fin.
3. Lance les agents **l'un après l'autre, jamais en parallèle** (ils utilisent le même graphique) : `bot-or`, puis `bot-eurusd`, puis `bot-eurjpy`, puis `bot-eth`.
4. Remets le graphique sur le symbole et l'unité de temps notés à l'étape 2.
5. Affiche un tableau récapitulatif, puis le rapport de chaque agent :

| Marché | Prix | Statut | Entrée | Stop | TP1 | TP2 | Suivi |
|---|---|---|---|---|---|---|---|

Ne passe aucun ordre et ne propose pas de taille de position. Termine par : « Un signal est une règle remplie, pas un trade à prendre. »
