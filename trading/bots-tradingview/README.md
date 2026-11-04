# Bots d'analyse TradingView

4 agents Claude Code, un par marché, plus une commande qui les lance tous.
Ils lisent ton graphique TradingView avec le serveur MCP `tradingview` et appliquent la règle du
**range du matin** (9h00–9h15, heure de Paris). **Lecture seule : aucun ordre n'est passé.**

| Fichier | Marché | Symbole | Bougies |
|---|---|---|---|
| `.claude/agents/bot-or.md` | Or | `TVC:GOLD` | 15 min |
| `.claude/agents/bot-eurusd.md` | EUR/USD | `FX:EURUSD` | 5 min |
| `.claude/agents/bot-eurjpy.md` | EUR/JPY | `FX:EURJPY` | 5 min |
| `.claude/agents/bot-eth.md` | ETH/USD | `COINBASE:ETHUSD` | 5 min |
| `.claude/skills/scan-marches/SKILL.md` | les 4, l'un après l'autre | | |

## La règle

1. **Range** : plus haut et plus bas entre 09:00 et 09:15.
2. **Signal** : première bougie clôturée entre 09:15 et 17:30 au-dessus du haut (ACHAT) ou en dessous du bas (VENTE).
3. **Stop** : milieu du range, au maximum 1 % de l'entrée.
4. **TP1** = 1R, **TP2** = 2R.
5. Stop et objectif dans la même bougie : on compte le stop.

C'est la même règle que `morning_scan.py` et l'indicateur `range_du_matin.pine` (voir `../scripts/`).

## Installation (Windows)

Copie le dossier `.claude` de ce dossier dans `D:\Claude\trading` (là où tu lances Claude Code), puis :

```bash
cd D:\Claude\trading
```

```bash
claude
```

Dans Claude Code : `/agents` pour vérifier, puis `/scan-marches`.
Pour relancer le scan toutes les 15 minutes : `/loop 15m /scan-marches`.

Prérequis : TradingView Desktop ouvert et le serveur MCP `tradingview` configuré dans Claude Code.
