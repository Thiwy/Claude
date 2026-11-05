# Exécuteur MT5 : les agents qui tradent sur OANDA

```
/trader-mt5  (agent principal : état du compte, résumé, demande ta validation)
  ├─ trader-eurusd  → lance l'exécuteur pour EURUSD
  └─ trader-eurjpy  → lance l'exécuteur pour EURJPY
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

Tout est noté dans `journal.csv` (ouvrable avec Excel).

**Arrêt d'urgence :** crée un fichier vide nommé `STOP` dans ce dossier. Plus aucun ordre ne part tant qu'il existe.

```bash
New-Item STOP
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
| `trades_max_jour` | 2 | Nombre maximum de trades par jour, tous marchés confondus (1 par marché au plus). |
| `stop_min_pips` | 5 | Pas de trade si le stop est plus serré : le spread le mangerait. |
| `spread_max_pct_du_stop` | 25 | Pas de trade si le spread dépasse 25 % de la distance du stop. |
| `signal_age_max_minutes` | 10 | Pas de trade si le signal date de plus de 10 min. |
| `ecart_entree_max_R` | 0.3 | Pas de trade si le prix s'est éloigné de plus de 0,3R de l'entrée prévue. |
| `glissement_max_points` | 10 | Écart de prix toléré à l'exécution (10 points = 1 pip sur EURUSD). |
| `decalage_serveur_secours` | 2 | Décalage horaire du serveur MT5, utilisé seulement par `--etat` si le marché est fermé. |

## Des règles différentes pour chaque agent

Dans `symboles`, tout paramètre écrit pour un marché remplace la règle générale pour ce marché seulement :

```json
"symboles": {
  "EURUSD": {"unite_minutes": 5},
  "EURJPY": {"unite_minutes": 5, "stop_min_pips": 6, "objectif": "TP1", "risque_max_par_trade_euros": 1.5}
}
```

Pour ajouter un marché, ajoute une ligne avec son nom **exact dans MT5** (par exemple `"GBPUSD": {"unite_minutes": 5}`),
puis copie `.claude/agents/trader-eurusd.md` en changeant le nom et le symbole.

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
