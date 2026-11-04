# Scripts de trading

| Fichier | Rôle |
|---|---|
| `morning_scan.py` | Scan du matin : range 9h00–9h15 (heure de Paris), stop, TP1, TP2 et historique sur 60 jours |
| `range_du_matin.pine` | Indicateur TradingView : dessine le range et les niveaux, envoie les alertes |
| `watchlist.json` | Marchés suivis |
| `universe.txt` | Liste des actions (symbole et nom) |

Ce sont la même règle que les agents de `../bots-tradingview/`.

## Lancer le scan du matin

```bash
py -I morning_scan.py
```

Test automatique de la règle :

```bash
py -I morning_scan.py --selftest
```

Ne pas ajouter : le dossier `state\` (données temporaires) ni aucun fichier contenant une clé d'API (ce dépôt est public).
