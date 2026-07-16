# AGENTS.md

## Cursor Cloud specific instructions

Ce dépôt est un monorepo (racine `LBG_IA_MMO/`). La pile Python (orchestrateur + backend + `mmo_server`, avec l'UI **Pilot**) est le chemin de dev/test local le plus simple. Le `bootstrap.md` et `LBG_IA_MMO/README.md` documentent les commandes standard ; les points ci‑dessous sont les pièges non évidents.

### Environnement
- Le venv partagé est `LBG_IA_MMO/.venv` (créé par `infra/scripts/install_local.sh`). Les paquets sont installés en éditable ; le hot-reload uvicorn suit les sources, mais une **réinstallation de dépendances nécessite de redémarrer** les process uvicorn.
- Le fichier `infra/secrets/lbg.env(.example)` cible des **IP LAN privées** (`192.168.0.x`) injoignables ici. Pour le dev local, **ne pas** sourcer ce fichier tel quel : passer des URLs `127.0.0.1` en variables d'env au lancement (voir ci‑dessous). Sans Ollama (LAN), les réponses LLM tombent en **stub** ; pour l'agent dialogue, forcer `LBG_DIALOGUE_LLM_DISABLED=1` donne un stub propre.

### Lancer les services (piège d'imports plats)
Certains modules utilisent des imports **plats** ; le répertoire de travail compte :
- **Orchestrateur (8010)** : lancer **depuis `LBG_IA_MMO/orchestrator/`** avec `uvicorn main:app` (comme le service systemd). La commande `uvicorn orchestrator.main:app` depuis la racine du bootstrap **échoue** (`ModuleNotFoundError: No module named 'shared_registry'`).
- **`mmo_server` (8050)** : lancer **depuis `LBG_IA_MMO/mmo_server/`** avec `uvicorn http_app:app`.
- **Backend (8000)** : lancer depuis `LBG_IA_MMO/` avec `uvicorn backend.main:app` ; définir `LBG_ORCHESTRATOR_URL=http://127.0.0.1:8010` et `LBG_MMO_SERVER_URL=http://127.0.0.1:8050` (+ `LBG_MMO_CORS_DEV=1` pour le web_client).
- **Agent dialogue (8020, optionnel)** : depuis `LBG_IA_MMO/`, `uvicorn lbg_agents.dialogue_http_app:app`. Sans lui, le routage `npc_dialogue` retombe en stub avec une erreur « rien n'écoute sur :8020 » (bénin).
- **UI Pilot** : http://127.0.0.1:8000/pilot/ (servie par le backend). Test de fumée cœur : `POST /v1/pilot/route` avec `{"text":"Je veux parler au forgeron"}` → intent `npc_dialogue` routé vers `agent.dialogue`.
- **web_client (Vite, 5173)** : `npm --prefix web_client run dev` ; nécessite le serveur WS `mmmorpg_server` (`python -m mmmorpg_server`, port 7733) pour le MMO complet.

### Tests & lint
- `pytest -q` **depuis la racine échoue à la collecte** : collisions de noms de modules préexistantes (`main`, `core`, `shared_registry`) et sous-projets optionnels non installés (`linux_agent`, `windows_agent`, `tools`). Utiliser `pytest --continue-on-collection-errors` (≈673 tests passent) ou des runs ciblés par package. La CI de référence est `bash infra/ci/test_pytest.sh`. Quelques échecs restants dépendent de données de seed du monde ou de l'état mémoire de l'hôte — préexistants, non liés à l'environnement.
- **Aucun linter Python** configuré. Le seul « lint » CI (`LBG_IA_MMO/.github/workflows/pytest.yml`, non actif sur GitHub car hors racine) est une vérif de syntaxe bash `bash -n` sur les scripts de smoke.
