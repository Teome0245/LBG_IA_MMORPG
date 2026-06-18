# Companion Bot (Phase 1)

Microservice **autonome** (FastAPI) qui fournit un canal de chat naturel et une **mémoire persistante**.

- UI dédiée : **hors scope Phase 1** (Phase 2). Ici, on expose un endpoint simple et stable.
- JSON « mécanique » : **uniquement** via `debug=true` (ou logs), pas dans le fil normal.

## Endpoints

- `GET /healthz` → `{ "status": "ok" }`
- `POST /v1/chat` → `{ "reply": "..." }` (et si `debug=true` → `debug: {...}`)
- `GET /v1/session/{session_id}` → derniers messages (et si `debug=true` → état moteur + meta)
- `POST /v1/session/{session_id}/tick` → nudge autonome optionnel (quota strict) + debug opt-in
- `GET /v1/session/{session_id}/events?after_id=...` → poll incrémental (événements > after_id)

## Configuration (variables d'environnement)

- `LBG_COMPANION_DB_PATH` : chemin SQLite (défaut: `./data/companion.sqlite3`)
- `LBG_COMPANION_CORS_ORIGINS` : origines autorisées (CSV), ex. `http://192.168.0.110:5174`
- `LBG_COMPANION_DEBUG_DEFAULT` : `1|0` (défaut `0`)

LLM OpenAI-compatible (optionnel — sinon fallback "stub") :

- `LBG_COMPANION_LLM_BASE_URL` : ex. `http://192.168.0.110:11434/v1` (Ollama OpenAI-compatible)
- `LBG_COMPANION_LLM_API_KEY` : si requis par le provider
- `LBG_COMPANION_LLM_MODEL` : ex. `gpt-4o-mini` / `llama3.1` / etc.

## Lancer en local (dev)

```bash
cd LBG_IA_MMO/companion_bot
python3 -m venv .venv
.venv/bin/pip install -e ../hybrid_proactive_agent
.venv/bin/pip install -e ".[dev]"
.venv/bin/uvicorn lbg_companion_bot.main:app --host 0.0.0.0 --port 8065
```

## Tests

```bash
.venv/bin/pip install -e ../hybrid_proactive_agent
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest tests/ -v
```

## Déploiement VM (systemd)

Voir `infra/systemd/lbg-companion-bot.service` et `infra/secrets/lbg.env.example`.

## UI web (Phase 2)

Voir `web/README.md` (Vite/React, port 5174, debug masqué via `?debug=1`).
