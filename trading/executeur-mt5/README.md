# Exécuteur MT5 : les agents qui tradent sur OANDA

```
Agent principal « trading »  (le chef — NE TRADE JAMAIS)
  /trader-mt5       état du compte, lance les agents, résume, te demande ta validation
  /rapport-journee  rapport de fin de journée à 17h45 (trades, € gagnés/perdus, analyse du marché)
  ├─ trader-eurusd  → trade l'EUR/USD
  └─ trader-eurjpy  → trade l'EUR/JPY
                         ↓
executeur_mt5.py  (calcule le signal, la taille, vérifie TOUS les garde-fous)
                         ↓
MetaTrader 5 ouvert sur le PC, connecté à OANDA  →  ordre avec stop et TP attachés
```

Règle : le range du matin (09:00–09:15, heure de Paris), la même que `../scripts/morning_scan.py`.

## Installation (Windows, une seule fois)

1. MetaTrader 5 ouvert et connecté à ton compte OANDA.
2. Dans MT5 : **Outils → Options → Expert Advisors → cocher « Autoriser le trading algorithmique »**,
   puis activer le bouton **Algo Trading** de la barre d'outils (il doit être vert).
3. Installer le module Python officiel de MetaTrader :

```bash
py -m pip install MetaTrader5
```

4. Vérifier la logique (sans MT5) puis la connexion :

```bash
py -I test_executeur.py
```

```bash
py -I executeur_mt5.py --etat
```

## Utilisation

Depuis ce dossier :

```bash
claude
```

puis tape `/trader-mt5`. Ou sans Claude :

| Commande | Effet |
|---|---|
| `py -I executeur_mt5.py` | analyse EURUSD et EURJPY une fois |
| `py -I executeur_mt5.py --symbole EURUSD --envoyer` | mode validation : envoie l'ordre prévu |
| `py -I executeur_mt5.py --boucle` | repasse chaque minute jusqu'à 17:35 (à lancer toi-même) |
| `py -I executeur_mt5.py --etat` | compte, positions, résultat du jour |
| `py -I executeur_mt5.py --fermer-tout` | ferme les positions ouvertes par l'exécuteur |
| `py -I executeur_mt5.py --rapport` | bilan brut de la journée (le rapport complet : `/rapport-journee` dans Claude) |

Tout est noté dans `journal.csv` (ouvrable avec Excel).

**Arrêt d'urgence :** crée un fichier vide nommé `STOP` dans ce dossier. Plus aucun ordre ne part tant qu'il existe.

```bash
New-Item STOP
```

## Trading automatique, sans rien relancer

`lancer-trading.bat` lance `executeur_mt5.py --boucle` : il repasse **chaque minute** de 8h55 à 17h35,
prend les trades de chaque marché, ferme à 17h30, et continue même si MetaTrader 5 ou internet coupe un moment
(il réessaie chaque minute et te prévient). Un changement de `config.json` est pris en compte sans relancer.
Tout ce qu'il fait est noté dans `rapports\boucle.log`.

Pour qu'il démarre tout seul du lundi au vendredi à 8h55 (une seule fois, dans PowerShell) :

```bash
schtasks /Create /TN "Trading agents" /TR "D:\Claude\claude-repo\trading\executeur-mt5\lancer-trading.bat" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 08:55
```

Pour le lancer tout de suite (par exemple si le PC était éteint à 8h55) :

```bash
schtasks /Run /TN "Trading agents"
```

Conditions : PC allumé, session Windows ouverte, pas de mise en veille, MetaTrader 5 ouvert avec Algo Trading au vert.
`py -I executeur_mt5.py --etat` affiche « Boucle automatique : ACTIVE » quand elle tourne.
Pour l'arrêter : fichier `STOP` (elle s'arrête à la minute suivante).

**Plusieurs trades par jour.** Après un trade (gagné ou perdu), l'agent attend que le prix **revienne dans le range**,
puis en ressorte : c'est un nouveau signal. Au plus `trades_max_par_marche` (3) par marché et `trades_max_jour` (6) au total,
et toujours dans la limite des stops de la journée (compte et agent).

## Notifications sur le téléphone

Avec l'app gratuite **ntfy** (Android / iPhone, sans compte), tu es prévenu quand :
un agent **ouvre** une position, une position est **fermée** (stop, TP, 17h30) avec le gain ou la perte,
OANDA **refuse** un ordre, le **stop de la journée** est atteint, et quand le **rapport du soir** est prêt.

Installation (une fois) :
1. Crée ton sujet secret (un nom au hasard, que personne ne peut deviner) :

```bash
"trading-" + [guid]::NewGuid().ToString("N").Substring(0,16) | Out-File -Encoding ascii notification.txt
```

```bash
Get-Content notification.txt
```

2. Dans l'app ntfy : **+** → « Subscribe to topic » → recopie exactement ce nom.
3. Essai :

```bash
py -I executeur_mt5.py --test-notification
```

`notification.txt` n'est jamais envoyé sur GitHub : quiconque connaît ce nom peut lire tes notifications.
Une notification ratée (pas d'internet) ne bloque jamais le trading.
Les fermetures par stop ou TP sont signalées au tour suivant du chef (dans les 5 minutes).

## Parler à tes agents

Dans Claude Code, depuis ce dossier, écris le nom de l'agent avec `@` (la liste s'affiche quand tu tapes `@trader`) :

```
@trader-eurusd pourquoi tu n'as pas pris de trade ce matin ?
@trader-eurjpy combien tu as gagné ou perdu cette semaine ?
@trader-eurusd que ferais-tu si le prix cassait le range maintenant ?
```

Pour une question, l'agent est **en lecture seule** : il lit le journal, les rapports et `config.json`,
et utilise `--analyse`, qui n'envoie **jamais** d'ordre, même en mode auto. Il ne trade que lorsque le chef (`/trader-mt5`)
lui envoie un « TOUR DE TRADING ». L'agent n'a pas de mémoire d'une conversation à l'autre :
sa mémoire, ce sont `journal.csv` et `rapports/`.

## Rapport de fin de journée (17h45)

Dans Claude Code : `/rapport-journee`. L'agent principal écrit le rapport dans `rapports/AAAA-MM-JJ.md` :
trades (entrée, sortie, stop ou TP, résultat en €), total du jour, stop de la journée atteint ou non,
ce que la règle a donné sur chaque marché (même en mode à blanc), et une analyse du marché avec les nouvelles du jour.

Les rapports restent **sur ton PC** : `rapports/` n'est pas envoyé sur GitHub (solde et numéro de compte, dépôt public).

**Où les retrouver :**
- sur le PC : `D:\Claude\claude-repo\trading\executeur-mt5\rapports\` (un fichier `AAAA-MM-JJ.md` par jour, s'ouvre avec le Bloc-notes) ;
- sur le téléphone : `rapport.bat` les copie aussi dans **OneDrive → Documents → trading → rapports** (app OneDrive) ;
- en parlant au chef (sur le PC ou en Remote Control) : « montre-moi le rapport d'hier ».
- `rapports\derniere-execution.log` dit ce qui s'est passé si un rapport manque.

**Pour qu'il se fasse tout seul chaque jour de semaine à 17h45**, une seule fois, dans PowerShell :

```bash
schtasks /Create /TN "Rapport trading" /TR "D:\Claude\claude-repo\trading\executeur-mt5\rapport.bat" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 17:45
```

Le PC doit être allumé et MetaTrader 5 ouvert à cette heure-là. Pour l'essayer tout de suite :

```bash
schtasks /Run /TN "Rapport trading"
```

Pour le supprimer :

```bash
schtasks /Delete /TN "Rapport trading" /F
```

## Les paramètres (`config.json`)

Les agents ne peuvent **pas** modifier ce fichier (bloqué dans `.claude/settings.json`) : c'est toi qui décides.

| Paramètre | Valeur de départ | Rôle |
|---|---|---|
| `mode` | `blanc` | `blanc` : rien n'est envoyé, tout est noté dans le journal. `validation` : un ordre part seulement après ton « oui ». `auto` : les ordres partent seuls. |
| `compte_reel_autorise` | `false` | Tant que c'est `false`, **aucun ordre ne part sur un compte réel**, quel que soit le mode. |
| `symboles` | EURUSD, EURJPY (5 min) | Marchés tradés et taille des bougies. Le nom doit être celui de MT5. |
| `range_debut` / `range_fin` | 09:00 / 09:15 | Le range du matin, heure de Paris. |
| `fin_signaux` | 17:30 | Plus de nouveau trade après cette heure. |
| `fermer_a_fin_signaux` | `true` | Ferme les positions encore ouvertes à 17:30. |
| `stop_max_pct` | 1.0 | Le stop ne peut pas être à plus de 1 % de l'entrée. |
| `objectif` | `TP1+TP2` | `TP1+TP2` : 2 demi-positions (une sort à 1R, l'autre à 2R). Ou `TP1`, ou `TP2`. |
| `perte_max_jour_euros` | **5** | **Stop de la journée.** Dès que les pertes du jour atteignent 5 €, plus aucun trade jusqu'au lendemain. Mieux : avant chaque ordre, l'exécuteur additionne les pertes du jour et ce que les positions ouvertes perdraient à leur stop, et réduit la taille pour que le total ne puisse pas dépasser 5 €. |
| `risque_max_par_trade_euros` | 2.5 | Perte maximale d'un seul trade si son stop est touché (`null` = pas de plafond, seulement le budget du jour). |
| `risque_par_trade_pct` | 0.5 | Autre plafond : % du solde. C'est le plus petit des trois (ce %, le maximum par trade, ce qui reste du budget du jour) qui compte. |
| `trades_max_jour` | 6 | Nombre maximum de trades par jour, tous marchés confondus. |
| `trades_max_par_marche` | 3 | Trades maximum par marché et par jour. Après un trade, il faut un retour dans le range puis une nouvelle cassure. |
| `stop_min_pips` | 5 | Pas de trade si le stop est plus serré : le spread le mangerait. |
| `spread_max_pct_du_stop` | 25 | Pas de trade si le spread dépasse 25 % de la distance du stop. |
| `signal_age_max_minutes` | 10 | Pas de trade si le signal date de plus de 10 min. |
| `ecart_entree_max_R` | 0.3 | Pas de trade si le prix s'est éloigné de plus de 0,3R de l'entrée prévue. |
| `glissement_max_points` | 10 | Écart de prix toléré à l'exécution (10 points = 1 pip sur EURUSD). |
| `decalage_serveur_secours` | 2 | Décalage horaire du serveur MT5, utilisé seulement par `--etat` si le marché est fermé. |

## Des paramètres pour chaque agent

Chaque agent = un marché dans `symboles`. Tout paramètre écrit dans son bloc remplace la règle générale
**pour lui seul** ; ce qui n'y est pas écrit reprend la règle générale.

```json
"symboles": {
  "EURUSD": {"unite_minutes": 5, "perte_max_jour_agent_euros": 2.5},
  "EURJPY": {"unite_minutes": 5, "perte_max_jour_agent_euros": 2.5, "stop_min_pips": 6,
             "objectif": "TP1", "risque_max_par_trade_euros": 1.5}
}
```

| Réglable par agent | Exemple |
|---|---|
| `perte_max_jour_agent_euros` | stop de la journée **de cet agent** : il s'arrête seul, les autres continuent |
| `risque_max_par_trade_euros`, `risque_par_trade_pct` | taille de ses trades |
| `objectif` | `TP1`, `TP2` ou `TP1+TP2` |
| `stop_max_pct`, `stop_min_pips`, `spread_max_pct_du_stop` | son stop loss et ses filtres |
| `range_debut`, `range_fin`, `fin_signaux`, `unite_minutes` | ses horaires et ses bougies |
| `signal_age_max_minutes`, `ecart_entree_max_R`, `glissement_max_points`, `fermer_a_fin_signaux` | ses conditions d'entrée et de sortie |

**Règles du compte, communes à tous** (refusées si on les met dans le bloc d'un agent) :
`mode`, `compte_reel_autorise`, `perte_max_jour_euros` (le stop de la journée du compte, 5 €), `trades_max_jour`.
Le stop du compte passe toujours avant : si les agents ont perdu 5 € à eux tous, tout s'arrête.

`py -I executeur_mt5.py --etat` affiche une ligne par agent : ce qu'il a perdu et si son stop est atteint.

Pour ajouter un agent : une ligne dans `symboles` avec le nom **exact dans MT5** (par exemple `"GBPUSD": {"unite_minutes": 5}`),
puis copier `.claude/agents/trader-eurusd.md` en changeant le nom et le symbole, et ajouter ses deux lignes dans `.claude/settings.json`.

## À savoir avec un petit stop de la journée

- Le plus petit ordre possible est en général **0,01 lot** : environ 0,09 € par pip sur EUR/USD.
  Avec 2,50 € de risque max, un trade est donc possible si le stop fait moins de ~27 pips ; sinon il est sauté.
- Avec si peu, `TP1+TP2` ne peut pas toujours être coupé en deux : l'exécuteur passe alors un seul ordre vers TP2.
- La perte réelle peut dépasser de quelques centimes ce qui est prévu (spread, glissement, trou de cotation le lundi matin).

## Plan de démarrage conseillé

1. **1 à 2 semaines en mode `blanc`** : lis `journal.csv`, compare avec ce que tu aurais fait.
2. Mode `validation`, `compte_reel_autorise: true`, **risque minimal** (`risque_par_trade_pct: 0.1`).
3. Augmenter seulement si tout se passe comme prévu. Le mode `auto` en dernier.

Rien n'a encore été testé avec un vrai MetaTrader 5 : seulement avec un MT5 simulé.
Le premier `--etat` et les premiers jours en mode `blanc` servent à le vérifier.
