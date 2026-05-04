# pilot_web (UI minimale)

Page statique servie par le **backend** sous `/pilot/` pour :

- afficher la santé agrégée (`GET /v1/pilot/status`) ;
- lister les capabilities (`GET /v1/pilot/capabilities`) ;
- envoyer une intention **timée** (`POST /v1/pilot/route` → `trace_id`, `elapsed_ms`, résultat orchestrator) ; si la réponse agent contient `output.commit`, le backend tente le commit HTTP interne vers `mmmorpg` ; pour **modifier l’inventaire joueur** (`flags.player_item_*`), renseigner `context.player_id` ou `context.mmmorpg_player_id` (UUID session), ou utiliser `actor_id` : `player:<uuid>` ;
- presets (dialogue PNJ, quête, avancement quête, combat, avancement combat, DevOps, **Lyra (test)**) ; option **DevOps dry-run** (injecte `context.devops_dry_run`) ;
- option **No cache** (injecte `context._no_cache=true`) pour debug / bypass du cache dialogue ; après un tour dialogue, la vue lisible affiche **`profil résolu`** (`output.remote.meta.dialogue_profile_resolved`) lorsque l’agent le fournit ;
- persistance **navigateur** (à chaque envoi) : historique PNJ par `npc_name`, **`quest_state`** (quête), **`encounter_state`** (combat — clé `enemy_name` / `target_name` / `opponent`, sinon `global`) ;
- affichage optionnel d’**`output.lyra`** (JSON formaté) lorsque l’agent renvoie ce champ — voir `docs/lyra.md` ; aperçu de **`context.lyra`** sous le champ JSON ; le preset **Lyra (test)** route vers **`agent.fallback`** ; avec **`npc_name`** + **`lyra`** dans le contexte et un texte de **dialogue**, l’intent **dialogue** applique aussi le pas de jauges et affiche **`output.lyra`** ;
- health des agents en **proxy same-origin** : `GET /v1/pilot/agent-dialogue/healthz`, `GET /v1/pilot/agent-quests/healthz`, `GET /v1/pilot/agent-combat/healthz`, `GET /v1/pilot/agent-pm/healthz` (évite d’ouvrir 8020/8030/8040/8055 depuis le navigateur) ; **invoke direct** `POST /v1/pilot/agent-dialogue/invoke` (même JSON que l’agent 8020) — la réponse peut inclure `meta.dialogue_profile_resolved` (profil effectif après registre / alias) ;
- **Registre PNJ & catalogue monde** (lecture seule, proxy backend → agent dialogue) : `GET /v1/pilot/agent-dialogue/npc-registry` (option `?npc_id=`), `GET /v1/pilot/agent-dialogue/world-content` (liste des `race_id` + nombre de créatures) — dans l’UI *Chat*, boutons *Charger* / *Charger world-content* ;
- **Réputation (debug, sans LLM)** : boutons **Rep +11 / Rep -5** + **Reset (→0)** sur `context.world_npc_id` (défaut `npc:merchant`) via `POST /v1/pilot/reputation` ; affichage de `lyra_meta.reputation.value` via `POST /v1/pilot/internal/route` (intent `devops_probe`, dry-run). Si le backend active `LBG_PILOT_INTERNAL_TOKEN`, renseigner le champ **Service token** (header `X-LBG-Service-Token`) — valeur stockée localement dans le navigateur.
- **Monde (aid, sans LLM)** : boutons “Aider / Reset jauges” via `POST /v1/pilot/aid` + relecture `GET /v1/pilot/mmo-server/world-lyra` (proxy same-origin vers `mmo_server`).
- **WS (test client minimal)** : se connecte au serveur WebSocket `mmmorpg_server` (LAN) et envoie un `hello` avec `world_npc_id` / `npc_name` / `text`. Affiche `world_tick.npc_reply` (placeholder remplacé via `trace_id`). Optionnel : snapshot avant/après via l’HTTP interne `:8773` (header `X-LBG-Service-Token` via le champ “token service”).
- **Desktop (hybride)** `#/desktop` : `POST /v1/pilot/route` avec `context.desktop_action` (worker Windows/Linux, allowlists + dry-run + approval) ; **Proposer via IA** → `POST /v1/pilot/agent-dialogue/invoke` si `LBG_DIALOGUE_DESKTOP_PLAN=1` sur l’agent dialogue (8020) — voir `docs/desktop_hybride.md` ; champ **résumé MMO** : JSON `session_summary` fusionné dans le `context` (persistance navigateur `lbg_pilot_mmo_session_summary_json`) pour le lien doux MMO → assistant (ADR 0004, `docs/lyra.md`).
- **Métriques Prometheus** : sous *Monitoring*, liens `GET /metrics` (backend, orchestrator depuis `orchestrator_url` de la santé, HTTP interne depuis le champ WS) ; champ **Bearer métriques** optionnel (stockage `localStorage`, aligné sur `LBG_METRICS_TOKEN` côté VM) ; bouton **Tester fetch backend /metrics** (same-origin). Pour :8010 / :8773, ouvrir les onglets ou utiliser `curl` si CORS / réseau bloque le fetch.

L’API publique `POST /v1/intents/route` reste disponible sans métadonnées de timing.

## Runbook “serveurs OK” (LAN)

Pour une recette courte “2–5 minutes” (smokes + page WS test client), voir :

- `docs/runbook_validation_serveurs_lan.md`

## Réputation (LAN / prod)

Endpoints utilisés par la page :

- `POST /v1/pilot/reputation` — applique un `reputation_delta` côté serveur jeu (HTTP interne) **sans LLM** ; peut être protégé par `LBG_PILOT_INTERNAL_TOKEN`.
- `POST /v1/pilot/aid` — applique des deltas “gameplay v1” sur `mmo_server` (**sans LLM**) ; peut être protégé par `LBG_PILOT_INTERNAL_TOKEN`.
- `GET /v1/pilot/mmo-server/world-lyra` — proxy same-origin vers `mmo_server` (`GET /v1/world/lyra`).
- `POST /v1/pilot/internal/route` — utilisé uniquement pour **relire** `lyra_meta` après modification (pas de LLM si l’intent reste `devops_probe`).

## Commandes (copier-coller)

**Prérequis** : venv installé (`bash infra/scripts/install_local.sh` depuis `LBG_IA_MMO/`).

**Terminal 1 — orchestrator**

```bash
cd LBG_IA_MMO
source .venv/bin/activate
uvicorn orchestrator.main:app --host 0.0.0.0 --port 8010
```

**Terminal 2 — backend**

```bash
cd LBG_IA_MMO
source .venv/bin/activate
export LBG_ORCHESTRATOR_URL="http://127.0.0.1:8010"
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

**Terminal 3 — vérif**

```bash
curl -sS http://127.0.0.1:8000/healthz
curl -sS http://127.0.0.1:8000/v1/pilot/status
```

**Navigateur** (après `curl` OK)

- `http://127.0.0.1:8000/pilot/` ou `http://localhost:8000/pilot/`
- VM privée (systemd) : `http://<IP_VM>:8000/pilot/`

## `ERR_CONNECTION_REFUSED`

Signifie en général : **rien n’écoute sur le port 8000** → lancer le backend (terminal 2) et attendre le message uvicorn `Uvicorn running on http://0.0.0.0:8000`.

Sous **WSL**, navigateur **Windows** : essayer `http://localhost:8000/pilot/` ; si ça refuse, dans WSL exécuter `hostname -I` et ouvrir `http://<première_IP>/pilot/`.

## URL du backend dans la page

Le champ « URL du backend » permet de cibler autre chose que l’origine (sauvegarde `localStorage`).
