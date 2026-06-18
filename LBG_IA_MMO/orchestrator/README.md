# Orchestrator (multi-agents)

Composant responsable de :
- introspection robuste
- classification des intentions (déterministe + **option LLM** pour le langage courant)
- registry des capacités
- routage multi-agents + fallback

## Classification LLM des intentions (optionnel)

Variables (voir `infra/secrets/lbg.env.example`) :

- `LBG_ORCHESTRATOR_INTENT_LLM=1` — active la couche LLM si `LBG_ORCHESTRATOR_INTENT_LLM_BASE_URL` est défini.
- `LBG_ORCHESTRATOR_INTENT_LLM_MODEL`, `LBG_ORCHESTRATOR_INTENT_LLM_API_KEY`, timeouts et `LBG_ORCHESTRATOR_INTENT_LLM_OVERRIDE_CONF`.

Le modèle répond en JSON interne ; seuls des intents « sûrs » sans action structurée sont autorisés (`npc_dialogue`, `quest_request`, `combat_action`, `devops_probe`, `project_pm`, `unknown`). Le routeur ajoute `output.orchestrator_route_meta` (`intent_source`, `assistant_reply` optionnelle).

Surcharge client : `context._intent_classify` = `llm` ou `deterministic` (pilot accueil : **Routage intention**).

## Moteur de jobs autonome (« type Cowork », sous garde-fous)

Transforme un **objectif en langage naturel** en **plan multi-étapes**, l'exécute **en tâche de fond** et **s'auto-corrige** (retry borné), sans contourner la policy d'actions. Détail : `../docs/assistant_core_plan.md` (Jalon 7).

- **Planner** : `services/planner.py` — découpe l'objectif + réutilise `action_proposal` pour mapper chaque étape sur une capability du registry ; planner **LLM optionnel** (`LBG_JOBS_PLANNER_LLM`), repli déterministe.
- **Moteur** : `services/jobs.py` — `Job`/`JobStep`, machine à états, persistance best-effort, boucle `advance_job` (observe→agit→corrige), runner daemon `ensure_started` (gate `LBG_JOBS_RUNNER_ENABLED`, **off par défaut**).
- **Auto-correction (2 niveaux)** :
  - *étape* : retry borné (`LBG_JOBS_STEP_MAX_ATTEMPTS`) ;
  - *objectif* : **replan automatique** (`LBG_JOBS_MAX_REPLANS`, défaut 1) — quand une étape échoue malgré ses retries, le moteur re-planifie l'objectif **avec le journal d'erreurs** (event `replanned`), borné, et **sauté si le plan est identique** (`replan_skipped`, évite les boucles — surtout avec le planner déterministe).
- **Validation sémantique** : `_step_satisfies` détecte le **succès trompeur** (`outcome` `bad_request`/`unknown_kind`/`allowlist_denied`/`forbidden`/`approval_*`, ou `open_app` sans `ok`/`dry_run`) — l'étape est alors traitée comme un échec (retry/replan), rapatrié de la logique `misleading_success` de P03.
- **Mémoire d'expériences** : `services/experience_memory.py` — journal `experiences.jsonl` (best-effort, sans dépendance) ; succès/échecs des jobs enregistrés et **rappelés** (`recall_similar`) pour enrichir le **planner LLM** (`LBG_JOBS_MEMORY_*`).
- **Garde-fous** : chaque étape passe par `evaluate_action_policy` ; périmètre restreint **safe_read + dry-run** ; une action à effet de bord exige un **token** (autonomie semi-auto), sinon le job passe en `waiting_approval`.
- **Élargissement par capability** : même avec un token, une action n'est élevée en **exécution réelle** que si sa capability est dans `LBG_JOBS_REAL_CAPABILITIES` (vide par défaut ⇒ tout reste en dry-run). Sinon elle reste en dry-run / `waiting_approval`.
- **Persistance** : Redis optionnel (`LBG_JOBS_REDIS_URL`, extra `pip install -e ./orchestrator[redis]`), sinon fichier JSON (`LBG_JOBS_STATE_PATH`), sinon mémoire. Dégradation propre si Redis indisponible.
  - **Layout Redis** : `index` (défaut, recommandé) écrit **une clé par job** (`{prefix}:job:{id}`) + un **set d'index** (`{prefix}:index`) — chaque mutation ne réécrit que le job concerné (scalable multivers). `snapshot` conserve l'ancien blob unique (`LBG_JOBS_REDIS_KEY`). Préfixe via `LBG_JOBS_REDIS_PREFIX` (défaut `lbg:jobs`).
- **UI** : vue Pilot `#/jobs` (proxies same-origin `/v1/pilot/jobs*`) — création, liste, timeline live, approbation/annulation/avance manuelle.

Endpoints :

- `POST /v1/jobs` — créer (objectif, `approval_token?`, `auto_start?`).
- `GET /v1/jobs` — lister (filtre `actor_id`).
- `GET /v1/jobs/{id}` — état complet (étapes, policy, résultats, timeline).
- `POST /v1/jobs/{id}/approve` — autoriser (token) un job `waiting_approval`.
- `POST /v1/jobs/{id}/cancel` — annuler.
- `POST /v1/jobs/{id}/advance` — avancer d'une étape (pilotage / debug).

Variables : `LBG_JOBS_*` (voir `infra/secrets/lbg.env.example`).

### Briques rapatriées de P03 (multi-VM, remédiation, agentique)

- **Élévation agentique** (`router/agentic.py`) : avec `LBG_CHAT_AGENTIC=1` ou `context.prefer_agentic=true`, un message Chat **actionnable** sur `POST /v1/route` crée un **job de fond** (plan + exécution auto-corrigée) au lieu d'un dispatch one-shot. N'élève que des intents actionnables (`devops_probe`, `desktop_control`, `core3_bot_action`, `project_pm`, `world_aid`) **et** seulement si le runner est activé. Toggle UI : Pilot ▸ console ▸ « Mode agentique ».
- **Planner ReAct** : le prompt système du planner LLM raisonne en mode ReAct (décomposition, anticipation d'échec, dry-run d'abord, replan sur le journal d'erreurs).
- **SSH multi-VM** (`agents/.../ssh_client.py`, `remote_targets.py`) : action DevOps **`ssh_run`** pour exécuter une commande **allowlistée** sur une VM LAN (`action.server_id` = `linux-140/110/245`, `core/front/mmo`, ou `action.host`). **OFF par défaut** (`LBG_MCP_SSH_ENABLED`). Dry-run + approbation comme les autres actions sensibles ; refus dur des commandes hors allowlist / destructrices.
- **Remédiation** (`agents/.../remediation.py`) : flux **`remediation_plan` → `remediation_apply` → `remediation_validate`** (kinds DevOps). `plan`/`validate` sont read-only (selfcheck) ; `apply` exécute une action DevOps allowlistée sous approbation. Aucune commande shell libre.

## Démarrage

Voir `../../bootstrap.md`.

