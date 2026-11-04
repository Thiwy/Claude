# Claude

Tout ce que Claude a créé pour moi, rangé par thème.

```
claude/
├── cuisine/
│   └── chef-cuisinier/        Agent « Chef » : recettes, techniques, nutrition, sécurité alimentaire
└── trading/
    ├── bots-tradingview/      4 agents d'analyse (or, EUR/USD, EUR/JPY, ETH) + commande /scan-marches
    ├── scripts/               morning_scan.py et l'indicateur range_du_matin.pine (à ajouter depuis le PC)
    └── skills-trader/         les 11 skills trader-* (à ajouter depuis le PC)
```

## Utiliser un agent

Claude Code charge les agents et les skills du dossier `.claude/` du projet où il est lancé.
Deux façons de faire :

- **Pour un projet** : copier le dossier `.claude/` voulu à la racine du projet, puis lancer `claude` depuis ce projet.
- **Partout** : copier les fichiers dans ton dossier personnel `~/.claude/agents/` et `~/.claude/skills/`
  (sous Windows : `C:\Users\<toi>\.claude\agents\` et `C:\Users\<toi>\.claude\skills\`).

Puis, dans Claude Code, tape `/agents` pour vérifier qu'ils sont reconnus.

> Les bots de trading **analysent** seulement : ils ne passent jamais d'ordre.
> Un signal est une règle remplie, pas un trade à prendre.
