# pilot_shell — UI type Cursor (v2)

Interface opérateur LBG par défaut depuis la Phase 6.

## URLs

| URL | Description |
|-----|-------------|
| `/pilot/v2/` | **pilot_shell** (cette app) |
| `/pilot/` | Redirige vers v2 ; legacy : `?legacy=1` |

## Développement

```bash
cd LBG_IA_MMO/pilot_shell
npm install
npm run dev
# → http://localhost:5175/pilot/v2/
```

Proxies Vite (dev) :

| Chemin | Cible défaut |
|--------|----------------|
| `/v1`, `/metrics` | `http://127.0.0.1:8000` |
| `/mmo` | `http://127.0.0.1:8080` |
| `/companion-api` | `http://127.0.0.1:8065` |

Variables : `VITE_BACKEND_PROXY`, `VITE_MMO_PROXY`, `VITE_COMPANION_PROXY`, `VITE_MMO_CLIENT_URL`, `VITE_COMPANION_BASE_URL`.

## Build & déploiement

```bash
cd LBG_IA_MMO
bash infra/scripts/deploy_pilot_shell.sh
```

Artefacts : `pilot_web/v2/` — servis sous `/pilot/v2/`.

## Fonctionnalités

- **Agent** : modes **Chat** (assistant PM + LLM), **Supervisé** (`POST /v1/pilot/tasks/run`), **Ops**, **Proposition**
- **MMO** : iframe client `/mmo/` + outils API debug
- **Companion** : chat autonome (`/companion-api`)
- **Jobs** : CRUD + flux SSE → panneau Logs
- **Panneau bas** : xterm (`route …`), logs, `/metrics`
- **Vues** : Ops, MMO, Jobs, PM, Lyra, Desktop, Santé, Companion

## Raccourcis

| Raccourci | Action |
|-----------|--------|
| `Ctrl+Shift+P` | Palette de commandes |
| `Ctrl+B` | Basculer sidebar |
| `Ctrl+J` | Basculer panneau bas |
| `Ctrl+L` | Basculer panneau Agent |

## Réglages

Tokens : mêmes clés `localStorage` que le pilot legacy (`lbg_pilot_service_token_v1`, etc.).

## Documentation

- Plan : `docs/ui_refactor_plan.md`
- ADR : `docs/adr/0011-pilot-shell-react.md`

## Monde MMO

Référence serveur : **Core3 Prime (VM 246)** — ADR 0012.
