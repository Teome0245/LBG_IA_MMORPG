# Agent Windows (Agent_IA)

Ce module contient le **worker Windows** (HTTP) exécuté sur le poste utilisateur.

## Chemin cible sur le PC Windows

Déploiement attendu : `C:\Agent_IA\`

## Démarrage

1) Copier le module sur Windows dans `C:\Agent_IA\`
2) Créer `C:\Agent_IA\desktop.env` (voir `desktop.env.example`)
3) Lancer :

```powershell
C:\Agent_IA\run_agent.cmd
```

## Endpoints

- `GET /healthz`
- `POST /invoke` (utilisé par `LBG_AGENT_DESKTOP_URL`)
- `GET /capabilities`, `POST /execute`, `POST /install` (historique / expérimental — pas requis pour `desktop_control`)

## Config hot-reload

Le fichier `desktop.env` est relu automatiquement quand il change (pas besoin de relancer uvicorn).

