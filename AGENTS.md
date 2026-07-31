# AGENTS.md

Dépôt `LBG_IA_MMORPG`. Le produit principal vit dans deux dossiers :

- `LBG_IA_MMO/` — monorepo Python (FastAPI backend, orchestrateur multi-agents, `mmo_server` de simulation, `mmmorpg_server` WebSocket temps réel, agents HTTP, UI `pilot_web`). Voir `LBG_IA_MMO/README.md` et `bootstrap.md` (racine) pour l'architecture, l'installation et les commandes de référence.
- `web_client/` — client MMO web (Vite/canvas) qui se connecte au serveur WebSocket `mmmorpg_server`.

Les autres dossiers à la racine (`content/`, `infra/`, `docs/`, images de map, etc.) sont des assets/outillage de contenu, pas des applications à lancer.

## Cursor Cloud specific instructions

Périmètre couvert : pile de dev locale complète (backend + orchestrateur + mmo_server + serveur WebSocket jeu + agent dialogue + client web Vite), lint (`bash -n`) et tests `pytest`.

### Secrets / env local (localhost, pas les IP LAN)

- Les services se configurent via `LBG_IA_MMO/infra/secrets/lbg.env` (gitignoré ; se source avec `set -a && source infra/secrets/lbg.env && set +a`).
- Piège : `lbg.env.example` cible les **IP LAN de prod** (`192.168.0.x`). En local il faut **tout forcer sur `127.0.0.1`**. Valeurs minimales utiles : `LBG_ORCHESTRATOR_URL`, `LBG_AGENT_DIALOGUE_URL`, `LBG_MMO_SERVER_URL` en `http://127.0.0.1:<port>`, `LBG_MMO_CORS_DEV=1` (autorise le client Vite 5173), `MMMORPG_IA_BACKEND_PATH=/v1/pilot/route` (route publique, la valeur par défaut `/v1/pilot/internal/route` exige un token).
- Aucun LLM (Ollama) n'est disponible dans cet environnement : mettre `LBG_DIALOGUE_LLM_DISABLED=1`. L'agent dialogue répond alors en **mode stub déterministe** (réplique « Configurez LBG_DIALOGUE_LLM_BASE_URL … »). C'est le comportement attendu en dev, pas une erreur.

### Démarrage des services (ports)

- Orchestrateur `8010`, backend `8000` (sert l'UI `/pilot/`), `mmo_server` `8050`, agent dialogue `8020`, serveur WebSocket jeu `mmmorpg_server` `7733`, client Vite `5173`. Commandes de référence : `bootstrap.md`.
- **Piège important** : l'orchestrateur doit être lancé **depuis le dossier `orchestrator/`** (`cd LBG_IA_MMO/orchestrator && uvicorn main:app --port 8010`). La commande `uvicorn orchestrator.main:app` documentée depuis la racine **échoue** avec `ModuleNotFoundError: shared_registry` car `shared_registry.py` et `team/` ne sont pas listés dans les `packages.find` du `pyproject.toml`. Le backend (`uvicorn backend.main:app`) et le `mmo_server` (`cd mmo_server && python -m uvicorn http_app:app`) se lancent bien depuis la racine.
- Client web : sur l'écran de login, le champ IP par défaut est `192.168.0.245` ; en local il faut saisir `127.0.0.1`. Le client ouvre `ws://<ip>:7733` et récupère la grille de collision sur `mmo_server` (`:8050`).
- Vérif rapide de la pile : `curl -sS http://127.0.0.1:8000/v1/pilot/status` doit renvoyer `orchestrator/agent_dialogue/mmo_server = ok`.

### Tests & lint

- **Ne pas** lancer `pytest -q` sur tout l'arbre : il y a des collisions de collection **préexistantes** (plusieurs `main.py`/`app` en `import`-mode racine entre `backend`/`orchestrator`/`mmo_server`, plus des helpers non packagés `core`, `core3_account_admin`). Lancer suite par suite. `mmo_server/tests` passe proprement (bon smoke). `backend`/`agents`/`mmmorpg_server` passent en très grande majorité (quelques échecs liés à l'infra LAN/Proxmox/Ollama absente, pas au code applicatif).
- Le workflow `LBG_IA_MMO/.github/workflows/pytest.yml` n'est **pas** à la racine du dépôt : GitHub Actions ne l'exécute donc jamais. Il n'y a pas de CI verte de référence.
- « Lint » = vérif syntaxe shell `bash -n` (aucun linter Python type ruff/flake8). Les scripts `*.sh` doivent rester en **LF** (voir `.gitattributes`).

### Notes

- `python3.12-venv` (paquet système) est requis pour créer le venv.
- L'installation editable régénère des `*.egg-info/SOURCES.txt` (fichiers suivis) ; ne pas les committer par accident.
