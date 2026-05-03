# Agents (minimal)

Après le routage d’intention, l’orchestrator appelle `lbg_agents.dispatch.invoke_after_route`, qui enrichit le champ `output` de la réponse.

## Contrats de sortie (shapes)

Le champ `output` renvoyé par l’orchestrator contient toujours :
- `capability` : nom de la capability résolue (ex. `npc_dialogue`, `quest_request`, `combat_action`)
- des champs spécifiques au handler, décrits ci-dessous

### Convention “agent HTTP” (ex. `agent.dialogue`)

Quand `agent.dialogue` appelle le service HTTP dialogue, `dispatch` renvoie :
- `agent: "http_dialogue"`
- `remote`: **objet JSON** retourné par `POST /invoke` (contient typiquement `reply`, `lines`, `speaker`, `meta`, etc.)
- `lyra` (optionnel) : si `context.lyra` est présent, **même logique** que le fallback — pas de jauges `lyra_engine` si applicable (`lbg_agents.lyra_bridge`), puis copie dans la sortie pour `/pilot/`. Le corps `POST /invoke` reçoit un `context` où `lyra` est déjà **mis à jour** après ce pas (pour que le LLM voie l’état courant).

Exemple (simplifié) :

```json
{
  "capability": "npc_dialogue",
  "agent": "http_dialogue",
  "remote": {
    "reply": "…",
    "lines": ["…"],
    "speaker": "Hagen le forgeron",
    "meta": { "stub": false, "llm": true, "model": "phi4-mini:latest" }
  }
}
```

### Convention “quest stub” (`agent.quests`)

Le handler `agent.quests` (stub) renvoie un objet `quest` stable, exploitable par `/pilot/` :
- `agent: "quests_stub"`
- `quest`: objet structuré (`title`, `giver`, `objectives`, `rewards`, `next_steps`)
- `quest_state`: état minimal (`quest_id`, `status`, `step`) pour simuler l’avancement via `context.quest_state`
- `meta.stub: true`

Exemple (simplifié) :

```json
{
  "capability": "quest_request",
  "agent": "quests_stub",
  "quest": {
    "title": "Petite quête : aide",
    "giver": "Un habitant",
    "objectives": [{ "kind": "task", "text": "…", "status": "open" }],
    "rewards": { "gold": 10, "xp": 70, "items": [] },
    "next_steps": ["…"]
  },
  "quest_state": { "quest_id": "q-…", "status": "open", "step": 0 },
  "meta": { "stub": true }
}
```

#### Flux “quête → avancement” (stub)

- **Création** : premier appel sans `context.quest_state` → renvoie `quest` + `quest_state`.
- **Avancement** : appel suivant avec `context.quest_state.quest_id` → renvoie un `quest_state` mis à jour (step++).

Dans `/pilot/`, le `quest_state` est automatiquement réinjecté dans `context` après une création de quête.

### Convention “combat stub” (`agent.combat`)

Le handler `agent.combat` (stub) renvoie une rencontre minimale :
- `agent: "combat_stub"`
- `encounter` : `encounter_id`, `opponent`, `round`, `hp` (joueur / adversaire), `suggested_actions`, `narrative`, `status` (`ongoing` | `victory` | `defeat` | `fled` pour les fins de rencontre côté stub)
- `encounter_state` : même information en forme compacte (réutilisable tel quel dans `context.encounter_state` pour le tour suivant)
- `meta.stub: true`, `meta.sterile: true` (aucun effet sur `mmo_server` / persistance monde tant qu’un moteur de combat n’est pas branché)

Le nom d’adversaire peut venir de `context.enemy_name`, `target_name` ou `opponent`, sinon heuristique sur le texte (`gobelin`, `loup`, `bandit`).

**Poursuite de rencontre** : si `context.encounter_state` contient un `encounter_id` valide et un statut non terminal, le stub **continue** la même rencontre (tour suivant, dégâts textuels simplifiés ; mots-clés `fuir` / `défendre` reconnus). Sinon, **nouvelle** rencontre.

Dans `/pilot/`, l’`encounter_state` peut être réinjecté automatiquement depuis le stockage local (comme `quest_state` pour les quêtes).

### Convention « chef de projet » (`agent.pm`)

Intent orchestrateur **`project_pm`** (classifieur ou `context.pm_focus` / `context.project_pm`). Sortie stub :
- `agent: "pm_stub"`
- `brief` : `title`, `summary`, `hints` (pistes actionnables), `docs` (chemins repo)
- `agent_site` (optionnel) : si `context.agent_site` est une chaîne non vide

Options (stub) :
- `context.pm_include_plan: true` ou texte contenant « plan de route », « roadmap », « jalons », « tâches », « milestones », etc. : tente d’ajouter `brief.current_step`
  en lisant **uniquement** `docs/plan_de_route.md` via un chemin connu (VM `/opt/LBG_IA_MMO/docs/plan_de_route.md` ou dev `docs/plan_de_route.md`).
  Override possible : `LBG_PM_PLAN_PATH` (chemin fichier).
- Sortie : `brief.current_step` (string | null) + `brief.current_step_found` (bool)
- **Données structurées (sans LLM)** : dès que le plan est inclus (`pm_include_plan` ou mots-clés ci-dessus), ou si `context.pm_include_structure` / `pm_include_tasks` / `pm_include_milestones` vaut `true`, le stub ajoute :
  - `brief.milestones` : liste d’objets `{ id, date, summary, raw }` (dernières lignes `| YYYY-MM-DD | … |` du fichier, cap `LBG_PM_MILESTONES_MAX`, défaut 8)
  - `brief.tasks` : liste d’objets `{ id, title, status, source }` (découpage de l’« Étape actuelle », ligne « File d’attente », tâches de contrôle sur les derniers jalons ; cap `LBG_PM_TASKS_MAX`, défaut 12)
  - `brief.file_attente` / `brief.file_attente_found` : ligne **File d’attente** si présente

### Lyra (echo + jauges optionnelles)

Si `context.lyra` est un **objet** JSON, les réponses **`minimal_stub`** (handler `_echo`, ex. **`agent.fallback`**) incluent **`lyra`** dans la sortie.

- **Echo** : si `gauges` n’utilise pas les clés `hunger` / `thirst` / `fatigue` du moteur, `output.lyra` reprend `context.lyra` tel quel.
- **Simulation** : si `gauges` contient au moins une de ces clés et que **`lyra_engine`** est importable (paquet **`mmo_server`** installé, venv monorepo), `lbg_agents.lyra_bridge` applique `GaugesState.step(dt_s)` (`dt_s` dans `context.lyra`, défaut 60 s) et renvoie les jauges mises à jour + `meta.lyra_engine` = `gauges.step`.

## Corrélation / trace

Pour le debug “prod”, `/pilot/` génère un `trace_id` sur `POST /v1/pilot/route` et le propage dans `context._trace_id`.
Tu peux réutiliser ce champ dans les logs (backend/orchestrator/agents) pour corréler un appel.

## Réconciliation “IA → jeu” (commit dialogue) — shape de sortie

Pour permettre au backend de tenter un commit vers `mmmorpg_server`, un agent (ex. dialogue) peut proposer un bloc `output.commit` :

- `output.commit.npc_id` (string, requis) : `npc:<id>`
- `output.commit.flags` (object, optionnel) : flags “dialogue” proposés

Le backend applique une **whitelist** et des **limites** avant d’appeler l’HTTP interne du serveur jeu (voir `bootstrap.md` et `docs/fusion_pont_jeu_ia.md`).

## Variables d’environnement

| Variable | Effet |
|----------|--------|
| `LBG_AGENT_DIALOGUE_URL` | Si définie (ex. `http://127.0.0.1:8020`), le handler **`agent.dialogue`** envoie un `POST {url}/invoke` avec le corps JSON `{ actor_id, text, context }`. Sinon : stub local (`minimal_stub`). |
| `LBG_AGENT_DIALOGUE_TIMEOUT` | Secondes pour la réponse HTTP (défaut **120**). Augmenter si `ReadTimeout` (LLM/Ollama lent). |
| `LBG_AGENT_QUESTS_URL` | Si définie (ex. `http://127.0.0.1:8030`), le handler **`agent.quests`** envoie un `POST {url}/invoke`. Sinon : stub local structuré (`quests_stub`). |
| `LBG_AGENT_QUESTS_TIMEOUT` | Secondes pour la réponse HTTP (défaut **30**). |
| `LBG_AGENT_COMBAT_URL` | Si définie (ex. `http://127.0.0.1:8040`), le handler **`agent.combat`** envoie un `POST {url}/invoke`. Sinon : stub local (`combat_stub`, toujours **stérile** côté monde). |
| `LBG_AGENT_COMBAT_TIMEOUT` | Secondes pour la réponse HTTP (défaut **30**). |
| `LBG_AGENT_PM_URL` | Si définie (ex. `http://127.0.0.1:8055`), le handler **`agent.pm`** envoie un `POST {url}/invoke`. Sinon : stub local **`pm_stub`** (brief jalons/risques déterministe). |
| `LBG_AGENT_PM_TIMEOUT` | Secondes pour la réponse HTTP (défaut **45**). |
| `LBG_AGENT_DESKTOP_URL` | Si définie (ex. `http://192.168.0.50:8060`), le handler **`agent.desktop`** envoie un `POST {url}/invoke`. Sinon : exécution locale **uniquement** (utile dev), mais en prod on vise un worker Windows. |
| `LBG_OPENGAME_SANDBOX_DIR` | Racine des prototypes OpenGame (défaut `generated_games/opengame`). Toutes les cibles sont résolues sous ce dossier. |
| `LBG_OPENGAME_DRY_RUN` | Dry-run OpenGame (`1` par défaut si non défini). Mettre `0` pour autoriser une tentative réelle. |
| `LBG_OPENGAME_EXECUTION_ENABLED` | Garde supplémentaire pour l’exécution réelle (`0` par défaut). Doit valoir `1` en plus du dry-run désactivé. |
| `LBG_OPENGAME_BIN` | Binaire CLI à lancer (défaut `opengame`, résolu via `PATH`). |
| `LBG_OPENGAME_TIMEOUT_S` | Timeout d’exécution CLI, en secondes (défaut **900**, borné 30..7200). |
| `LBG_OPENGAME_MAX_OUTPUT_CHARS` | Taille max capturée pour stdout/stderr dans la réponse (défaut **12000**). |
| `LBG_OPENGAME_APPROVAL_TOKEN` | Si défini, une exécution réelle exige `context.opengame_approval`. |
| `LBG_OPENGAME_AUDIT_LOG_PATH` | Fichier JSONL optionnel pour l’audit `agents.opengame.audit`. |
| `LBG_OPENGAME_AUDIT_STDOUT` | Si `0` / `false`, coupe l’audit stdout OpenGame. |
| `LBG_PM_PLAN_PATH` | Chemin absolu ou relatif vers le markdown du plan (prioritaire sur les chemins par défaut VM/dev). |
| `LBG_PM_MILESTONES_MAX` | Nombre max de lignes datées conservées dans `brief.milestones` (défaut **8**, plafonné à 30). |
| `LBG_PM_TASKS_MAX` | Nombre max d’entrées dans `brief.tasks` (défaut **12**, plafonné à 40). |

### Topologie cible — un service d’agents par machine (optionnel)

- **Même codebase** : chaque VM (core **140**, MMO **245**, front **110**, poste **dev**) peut exécuter le **paquet agents** avec des **`LBG_AGENT_*_URL`** pointant vers les **ports locaux** de cette machine (`127.0.0.1`) ou vers un autre hôte LAN si l’agent tourne ailleurs.
- **Orchestrateur unique** : il reste sur le **core** (souvent) ; les URL dans `/etc/lbg-ia-mmo.env` décrivent **où** vivent les workers HTTP (tous sur 140 en LAN typique, ou répartis).
- **Contrôle infra délégué** : un agent outil sur une autre VM reste possible via URL dédiée (ex. **`AGENT_DEVOPS_VM_URL`** dans `lbg.env` — hors dispatch standard aujourd’hui, réservé aux intégrations futures / ponts HTTP).
- **Contexte** : `context.agent_site` (ex. `"core"`, `"mmo"`, `"dev"`) peut être propagé pour **étiqueter** la réponse (stub PM, futures métriques) ; le routage reste **déterministe** côté orchestrateur (`project_pm`, `devops_probe`, etc.).

Unité systemd core : **`lbg-agent-pm.service`** (port **8055**), installée par **`deploy_vm.sh`** rôle **core** avec les autres agents HTTP.

### OpenGame — forge de prototypes (`agent.opengame`)

Capability orchestrateur : **`prototype_game`** → handler **`agent.opengame`**. Par design, on exige une action structurée via `context.opengame_action` ; un texte seul ne déclenche pas de génération.

Action MVP :
- `generate_prototype` : `{"kind":"generate_prototype","project_name":"snake","prompt":"Build a Snake clone"}`

Garde-fous :
- **Sandbox obligatoire** : cible sous `LBG_OPENGAME_SANDBOX_DIR`.
- **Dry-run par défaut** : aucun appel CLI OpenGame tant que `LBG_OPENGAME_DRY_RUN` n’est pas à `0`.
- **Double verrou d’exécution** : exécution réelle seulement si `LBG_OPENGAME_DRY_RUN=0` et `LBG_OPENGAME_EXECUTION_ENABLED=1`.
- **Dossier cible vide** : l’agent refuse un `project_name` dont le dossier existe déjà avec du contenu.
- **Pas de `--yolo`** : la commande utilise `--approval-mode auto-edit`, sans shell libre OpenGame.
- **Pas de modification automatique du cœur MMO** : les prototypes restent isolés et sont promus manuellement.
- **Audit JSONL/stdout** : événement `agents.opengame.audit` avec `trace_id`, `outcome`, `dry_run`, `sandbox_dir`, `target_dir`.
- **Approval optionnelle** : si `LBG_OPENGAME_APPROVAL_TOKEN` est défini, fournir `context.opengame_approval`.

Contrat de sortie minimal :

```json
{
  "capability": "prototype_game",
  "agent": "opengame_executor",
  "handler": "opengame",
  "ok": true,
  "outcome": "dry_run",
  "project_name": "snake",
  "sandbox_dir": "generated_games/opengame",
  "target_dir": "generated_games/opengame/snake",
  "planned": {
    "tool": "opengame",
    "command": ["opengame", "-p", "<prompt>", "--approval-mode", "auto-edit"],
    "timeout_s": 900
  }
}
```

### DevOps — exécuteur à liste blanche (`agent.devops`)

Capability orchestrateur : **`devops_probe`** → handler **`agent.devops`**. Actions décrites dans `context.devops_action` (priorité de routage absolue) ou texte type « sonde devops » / « healthz backend » / **« diagnostic complet »** (action **`selfcheck`**).

| Variable | Effet |
|----------|--------|
| `LBG_DEVOPS_HTTP_ALLOWLIST` | Liste d’URLs **exactes** autorisées pour `http_get`, séparées par des virgules. Si vide : défaut `http://127.0.0.1:8010/healthz` et `http://127.0.0.1:8000/healthz`. |
| `LBG_DEVOPS_SYSTEMD_UNIT_ALLOWLIST` | Noms d’unités **exactes** autorisées pour `systemd_is_active` (ex. `lbg-backend.service`), virgules. **Vide par défaut** → `systemd_is_active` refusé. |
| `LBG_DEVOPS_SYSTEMD_RESTART_ALLOWLIST` | Noms d’unités **exactes** autorisées pour `systemd_restart` (ex. `lbg-backend.service`), virgules. **Vide par défaut** → `systemd_restart` refusé. |
| `LBG_DEVOPS_SYSTEMD_RESTART_MAX_PER_WINDOW` | Nombre max de **tentatives réelles** `systemd_restart` par fenêtre glissante (défaut **8**, plafonné à 50). |
| `LBG_DEVOPS_SYSTEMD_RESTART_WINDOW_S` | Taille de la fenêtre glissante en secondes (défaut **3600**, min 60 s, max 7 jours). Compteur **par processus** uvicorn (best-effort multi-workers). |
| `LBG_DEVOPS_SYSTEMD_RESTART_MAINTENANCE_UTC` | Si non vide : `HH:MM-HH:MM` en **UTC** ; les restarts **réels** sont refusés en dehors de cet intervalle (si début > fin, la fenêtre traverse minuit). |
| `LBG_DEVOPS_SELFCHECK_HTTP` | (Optionnel) URLs healthz **exactes** pour l’action **`selfcheck`**, virgules — chacune doit être dans `LBG_DEVOPS_HTTP_ALLOWLIST`. Si vide : sonde `LBG_DEVOPS_DEFAULT_PROBE_URL` puis `…/healthz` dérivés de `LBG_ORCHESTRATOR_URL` et `MMMORPG_IA_BACKEND_URL` lorsqu’ils sont définis. |
| `LBG_DEVOPS_SELFCHECK_SYSTEMD` | (Optionnel) Sous-ensemble d’unités pour **`selfcheck`** (virgules), toutes devant rester dans `LBG_DEVOPS_SYSTEMD_UNIT_ALLOWLIST`. Si vide : par défaut **`lbg-backend.service`** et **`lbg-orchestrator.service`** s’ils sont dans l’allowlist, sinon les premières unités de l’allowlist. |
| `LBG_DEVOPS_LOG_ALLOWLIST` | Chemins de fichiers **exactes** pour `read_log_tail` (virgules). **Vide par défaut** → lecture fichier refusée. |
| `LBG_DEVOPS_DEFAULT_PROBE_URL` | URL utilisée quand le texte déclenche une sonde sans `devops_action` (défaut : healthz orchestrator). |
| `LBG_DEVOPS_DRY_RUN` | Si `1` / `true` / `yes` / `on` : **aucune** requête HTTP ni lecture fichier ; allowlist et audit inchangés. |
| `context.devops_dry_run` | Si `true` : même effet dry-run **pour cet appel** (sans redémarrer) ; combiné avec la case « DevOps dry-run » dans `/pilot/`. La variable d’environnement reste prioritaire (si elle active le dry-run, le contexte ne peut pas le désactiver). |
| `LBG_DEVOPS_APPROVAL_TOKEN` | Si défini (non vide) : toute exécution réelle (`http_get` / `read_log_tail` / `systemd_is_active` / `systemd_restart` / sous-étapes du **`selfcheck`** hors dry-run) exige `context.devops_approval` **égal** au jeton (comparaison `secrets.compare_digest`). Le jeton n’est jamais journalisé dans l’audit. Si non défini : pas de garde (comportement précédent). |
| `context.devops_approval` | Chaîne à fournir par l’appelant quand `LBG_DEVOPS_APPROVAL_TOKEN` est actif ; à ne pas logger côté client. |
| `context.devops_selfcheck` | Si `true` : équivalent à `devops_action: { "kind": "selfcheck" }` lorsque aucune action explicite n’est fournie (pratique pour `/pilot/` ou scripts). |
| `LBG_DEVOPS_AUDIT_LOG_PATH` | Si défini : chaque audit est **ajouté** (append) dans ce fichier au format **JSONL** (une ligne JSON par action, champ `ts` en UTC ISO). Les répertoires parents sont créés si besoin. |
| `LBG_DEVOPS_AUDIT_STDOUT` | Si `0` / `false` / `no` / `off` : n’écrit plus l’audit sur stdout (fichier seul si `LBG_DEVOPS_AUDIT_LOG_PATH` est défini ; sinon l’audit est perdu — à éviter). |

Chaque action DevOps émet une ligne JSON `event: agents.devops.audit` (`ts`, `outcome`, `dry_run`, `dry_run_source`, `approval_gate_active`, `trace_id`, `url` / `path` / `unit`, etc.) sur **stdout** par défaut (journald) et **en plus** dans le fichier si configuré. Valeur d’`outcome` supplémentaire : **`approval_denied`**. Le **`selfcheck`** émet en plus des lignes `selfcheck_http_get`, `selfcheck_systemd_is_active` et une synthèse `selfcheck_summary`. En cas d’erreur d’écriture fichier, un seul message `agents.devops.audit_file_error` part sur **stderr**.

**`selfcheck`** : agrège des sondes **bornées** (pas d’URL ou d’unité arbitraires côté prompt) ; le champ `remediation_hints` propose des pistes **textuelles** (ex. `journalctl`, `systemctl restart` — **non exécutées** par l’exécuteur). Une évolution ultérieure pourra ajouter des actions correctives derrière un garde-fou plus strict.

Recette LAN (dry-run par défaut) : `bash infra/scripts/smoke_devops_systemd_lan.sh` (voir en-tête du script pour `LBG_DEVOPS_SYSTEMD_UNIT_ALLOWLIST` sur le **core**) ; bundle diagnostic : `bash infra/scripts/smoke_devops_selfcheck_lan.sh`.

### Desktop — agent Windows hybride (`agent.desktop`)

Capability orchestrateur : **`desktop_control`** → handler **`agent.desktop`**. Par design, on n’exécute **rien**
sur simple texte : il faut fournir une action structurée via `context.desktop_action` (priorité de routage).

Actions MVP :
- `open_url` : `{"kind":"open_url","url":"https://…"}`
- `notepad_append` : `{"kind":"notepad_append","path":"C:\\…\\notes.txt","text":"…"}`
- `open_app` : `{"kind":"open_app","app":"notepadpp","args":[]}`

Actions Computer Use (UI) — **désactivées par défaut** (nécessite `LBG_DESKTOP_COMPUTER_USE_ENABLED=1`) :
- `observe_screen`, `click_xy`, `move_xy`, `drag_xy`, `type_text`, `hotkey`, `scroll`, `wait_ms`

Macro :
- `run_steps` : exécute une liste d’étapes bornée ; options `stop_on_fail`, sortie `step_outputs[]` + `errors[]`

Garde-fous :
- **Allowlist URL** (match exact)
- **Allowlist répertoires fichiers**
- **Dry-run par défaut**
- **Approval token** optionnel pour toute exécution réelle
- **Audit JSONL** (stdout et/ou fichier)
- **Computer Use** : feature flag, limites de taille screenshot, limites `type_text`, limites `run_steps`

| Variable | Effet |
|----------|--------|
| `LBG_DESKTOP_URL_ALLOWLIST` | URLs **exactes** autorisées pour `open_url` (virgules). Vide → tout refusé. |
| `LBG_DESKTOP_FILE_ALLOWLIST_DIRS` | Répertoires parents autorisés pour `notepad_append` (virgules). Vide → tout refusé. |
| `LBG_DESKTOP_DRY_RUN` | Si `1`/`true`/`yes`/`on` : aucune action réelle (défaut recommandé **1**). |
| `context.desktop_dry_run` | Si `true` : force le dry-run pour cet appel (si l’env ne l’a pas déjà activé). |
| `LBG_DESKTOP_APPROVAL_TOKEN` | Si défini : toute exécution réelle exige `context.desktop_approval` identique (comparaison constante). |
| `LBG_DESKTOP_AUDIT_LOG_PATH` | Chemin fichier JSONL (append) pour l’audit. |
| `LBG_DESKTOP_AUDIT_STDOUT` | Si `0`/`false` : n’écrit plus l’audit sur stdout. |
| `LBG_DESKTOP_COMPUTER_USE_ENABLED` | Si `1`/`true` : active `observe_screen`/click/type/... et `run_steps`. Défaut : désactivé. |
| `LBG_DESKTOP_OBSERVE_REQUIRES_APPROVAL` | Si `1`/`true` : exige un token sur `observe_screen` (recommandé). |
| `LBG_DESKTOP_SCREENSHOT_DIR` | Dossier d’écriture des screenshots (`observe_screen`). |
| `LBG_DESKTOP_SCREENSHOT_RETURN` | `path|base64|none` (défaut `path`). |
| `LBG_DESKTOP_SCREENSHOT_MAX_WIDTH` | Largeur max (redimensionnement). |
| `LBG_DESKTOP_SCREENSHOT_FORMAT` | `jpeg|png`. |
| `LBG_DESKTOP_SCREENSHOT_JPEG_QUALITY` | Qualité JPEG (10..95). |
| `LBG_DESKTOP_TYPE_MAX_CHARS` | Limite dure de caractères pour `type_text`. |
| `LBG_DESKTOP_RUN_STEPS_MAX` | Nombre max d’étapes `run_steps`. |
| `LBG_DESKTOP_RUN_STEPS_TIMEOUT_MS` | Timeout global `run_steps`. |


**Prod** : compte **`lbg`** (sudoer, services non-root) — **`docs/ops_vm_user.md`** ; rotation JSONL / jeton — **`docs/ops_devops_audit.md`** (`infra/logrotate/lbg-devops-audit`).

Exemple `context` (JSON) :

```json
{
  "devops_action": { "kind": "http_get", "url": "http://127.0.0.1:8010/healthz" }
}
```

```json
{
  "devops_action": { "kind": "systemd_is_active", "unit": "lbg-backend.service" }
}
```

```json
{
  "devops_action": { "kind": "selfcheck" },
  "devops_dry_run": true
}
```

### LLM dans l’agent HTTP dialogue

Par défaut (**sans variable**), l’agent cible **Ollama** en local :  
`LBG_DIALOGUE_LLM_BASE_URL=http://127.0.0.1:11434/v1`,  
`LBG_DIALOGUE_LLM_MODEL=gemma4:latest` (valeur par défaut dans le code).  
En prod/LAN, ces valeurs sont en général définies via `/etc/lbg-ia-mmo.env` (poussé depuis `infra/secrets/lbg.env`) : le **modèle effectif** doit correspondre à ce que renvoie `curl http://<hôte-ollama>:11434/api/tags`.

| Variable | Effet |
|----------|--------|
| `LBG_DIALOGUE_LLM_BASE_URL` | Défaut : `http://127.0.0.1:11434/v1` (API `/v1` type OpenAI). |
| `LBG_DIALOGUE_LLM_DISABLED` | Si `1` / `true` : pas d’appel LLM → réponses **stub** (tests CI, machine sans Ollama). |
| `LBG_DIALOGUE_LLM_API_KEY` | Clé Bearer (souvent vide pour Ollama local). |
| `LBG_DIALOGUE_LLM_MODEL` | Défaut `gemma4:latest` (nom `ollama list`). |
| `LBG_DIALOGUE_LLM_TIMEOUT` | Secondes (défaut 120). |
| `LBG_DIALOGUE_LLM_TEMPERATURE` | Défaut 0.7. |
| `LBG_DIALOGUE_LLM_MAX_TOKENS` | Défaut 512. |
| `LBG_ORCHESTRATOR_DIALOGUE_TARGET_DEFAULT` | Décision orchestrateur pour les dialogues PNJ sans choix explicite (`fast` par défaut recommandé). |
| `context.dialogue_target` | `local`, `remote` ou `fast`. Si absent, l’orchestrateur l’injecte pour `agent.dialogue`. |
| `LBG_DIALOGUE_FAST_ENABLED` | Active le provider rapide explicite pour `dialogue_target=fast`. Si désactivé/incomplet, fallback vers `remote` si activé, sinon `local`. |
| `LBG_DIALOGUE_FAST_BASE_URL` / `LBG_DIALOGUE_FAST_MODEL` / `LBG_DIALOGUE_FAST_API_KEY` | Provider rapide OpenAI-compatible, typiquement Groq (`https://api.groq.com/openai/v1`, `llama-3.1-8b-instant`). |

**Ollama (machine locale)** : `ollama serve` puis `ollama pull llama3.2`, puis (les exports sont optionnels grâce aux défauts) :

```bash
uvicorn lbg_agents.dialogue_http_app:app --host 0.0.0.0 --port 8020
```

**Ollama sur les VM LBG (ex. `192.168.0.140` *vm140*, `192.168.0.110` *lbg-ia-backend*)** : le même catalogue de modèles peut exister sur les deux. Choisir l’URL selon **où tourne** le daemon Ollama utilisé par l’agent dialogue :

| Cas | `LBG_DIALOGUE_LLM_BASE_URL` |
|-----|-----------------------------|
| Ollama sur **la même VM** que `lbg-agent-dialogue` | `http://127.0.0.1:11434/v1` |
| Ollama sur une **autre** machine du LAN (ex. 110) | `http://192.168.0.110:11434/v1` |

Vérifier que le port **11434** est joignable (firewall) si l’agent et Ollama ne sont pas sur le même hôte. Modèles vus côté prod (exemples) : `llama3.2:latest`, `mistral:latest`, `qwen2.5:7b`, `phi4-mini:latest`, etc.

### Accélérer Ollama (réponses plus rapides)

| Levier | Idée |
|--------|------|
| **Modèle** | Préférer un petit modèle rapide (`phi4-mini`, `llama3.2` 3B si dispo, etc.) plutôt qu’un 7B+ si la qualité suffit. `ollama ps` pour voir ce qui est chargé. |
| **GPU** | Sur la machine qui exécute Ollama, un **GPU** (NVIDIA/AMD avec pilotes) réduit fortement la latence vs CPU seul. Vérifier qu’Ollama utilise bien le GPU (logs au démarrage). |
| **Moins de tokens** | Baisser **`LBG_DIALOGUE_LLM_MAX_TOKENS`** (ex. `256` ou `128`) : réponses plus courtes = génération plus rapide. |
| **Température** | Impact modeste sur la vitesse ; plutôt pour le style. |
| **Réseau** | Mettre l’agent dialogue et Ollama sur **la même machine** (`127.0.0.1:11434`) évite la latence LAN. |
| **Premier appel** | Le **premier** `/invoke` après démarrage peut être lent (chargement du modèle) ; les suivants sont en général plus rapides tant que le modèle reste en mémoire. |
| **Parallélisme** | Variable **`OLLAMA_NUM_PARALLEL`** (côté service Ollama) utile surtout si plusieurs requêtes simultanées, pas pour une seule requête plus rapide. |

### Variables “performance” (prod VM)

Sur VM (systemd), la configuration est chargée via `/etc/lbg-ia-mmo.env` (persistant entre déploiements). Valeurs recommandées (exemple) :

```bash
# Dialogue
LBG_AGENT_DIALOGUE_URL="http://127.0.0.1:8020"
LBG_AGENT_DIALOGUE_TIMEOUT="240"

# LLM (Ollama)
# - même VM : http://127.0.0.1:11434/v1
# - autre machine LAN (ex. 110) : http://192.168.0.110:11434/v1
LBG_DIALOGUE_LLM_BASE_URL="http://127.0.0.1:11434/v1"
LBG_DIALOGUE_LLM_MODEL="phi4-mini:latest" # ou un modèle présent dans /api/tags (ex. gemma4:latest)
LBG_DIALOGUE_LLM_MAX_TOKENS="24"
LBG_DIALOGUE_LLM_TEMPERATURE="0.2"
LBG_DIALOGUE_LLM_TIMEOUT="240"

# Backend → Orchestrator (évite les 502 si le LLM est lent)
LBG_ORCHESTRATOR_TIMEOUT="240"
```

Notes :
- Si Ollama est lent via `/v1/chat/completions`, l’agent dialogue utilise automatiquement l’API native Ollama (`/api/chat`) quand la base URL pointe sur `:11434`.
- Si tu veux désactiver le LLM (stub immédiat) : `LBG_DIALOGUE_LLM_DISABLED=true`.
- `LBG_DIALOGUE_LLM_MAX_TOKENS` peut être **très bas** (ex. `24` ou `48`) pour réduire la latence en prod.

**Multi-tours** : dans `context`, passer `history` : liste d’objets avec `role` (`"user"` ou `"assistant"`) et `content` (échanges précédents). Le tour courant est le champ `text` du joueur.

**Lyra (LLM)** : si `context.lyra` contient `gauges` (`hunger`/`thirst`/`fatigue` en 0–1, etc.), `dialogue_llm.build_system_prompt` ajoute un résumé et une consigne de ton au **system prompt** (sans citer de chiffres au joueur dans la consigne).

## Agent HTTP « dialogue »

Module : `lbg_agents.dialogue_http_app` (FastAPI).

- `GET /healthz` → JSON (`llm_configured`, `llm_model`, etc.).
- `POST /invoke` → corps `InvokeIn` (`actor_id`, `text`, `context`). Réponse : `agent`, `reply`, `lines`, `speaker`, `player_text`, `meta` (`stub`, `llm`, `model`, évent. `llm_error` si le LLM est configuré mais l’appel échoue).
- `GET /npc-registry` → registre PNJ (`npc_registry.json`), option `?npc_id=` pour une entrée.
- `GET /world-content` → inventaire **races + bestiaire** (JSON sous `content/world/`, surcharge par `LBG_WORLD_CONTENT_DIR`) ; inclut `race_ids`, `races_count`, `creatures_count` et la carte **`race_display`** (`race_id` → `display_name`) pour les clients légers (ex. HUD MMO web via proxy pilot).

**Tests** (sans activer un venv projet, avec **uv**) :

```bash
cd LBG_IA_MMO/agents
PYTHONPATH=src uv run --with pytest --with 'httpx>=0.26' --with 'fastapi>=0.110' python -m pytest tests/test_dialogue_http_app.py tests/test_world_content.py -q
```

### Lancer en local (WSL), 4ᵉ terminal

```bash
cd LBG_IA_MMO
source .venv/bin/activate
uvicorn lbg_agents.dialogue_http_app:app --host 0.0.0.0 --port 8020
```

Pour que **l’orchestrator** (terminal déjà prévu) appelle cet agent, redémarre-le **après** avoir exporté :

```bash
export LBG_AGENT_DIALOGUE_URL="http://127.0.0.1:8020"
uvicorn orchestrator.main:app --host 0.0.0.0 --port 8010
```

Sans cette variable, le dialogue reste en **stub** (aucun HTTP).

### Prod (systemd)

Unité : `infra/systemd/lbg-agent-dialogue.service` (port **8020**).  
L’unité `lbg-orchestrator.service` définit `LBG_AGENT_DIALOGUE_URL=http://127.0.0.1:8020` et démarre **après** `lbg-agent-dialogue`.

## Contrat `POST /invoke`

**Requête** (JSON) :

- `actor_id` (string)
- `text` (string)
- `context` (objet, défaut `{}`)

**Réponse** (schéma) : voir champs ci-dessus ; avec LLM, `meta.stub` est `false` et `meta.model` indique le modèle utilisé.

En cas d’erreur HTTP ou réseau, `dispatch` renvoie `agent: http_dialogue`, un champ `error`, et des champs de **fallback** type stub pour le debug.

## Paquet Python

- Dépendance runtime : **`httpx`** (appels depuis `dispatch`).
- Extras : **`dialogue_http_service`**, **`quests_http_service`**, **`combat_http_service`** (`fastapi`, `uvicorn`) — install via `pip install -e ".[dialogue_http_service,quests_http_service,combat_http_service]"` depuis `agents/`, ou via `install_local.sh` du monorepo.

## Évolution

Ajouter d’autres URLs ou une découverte par registry ; garder `invoke_after_route` comme point d’entrée unique.

## Agent HTTP « quests » (optionnel)

Module : `lbg_agents.quests_http_app` (FastAPI).

- `GET /healthz` → JSON
- `POST /invoke` → corps `InvokeIn` (`actor_id`, `text`, `context`)

Lancer en local (port suggéré **8030**) :

```bash
cd LBG_IA_MMO
source .venv/bin/activate
uvicorn lbg_agents.quests_http_app:app --host 0.0.0.0 --port 8030
```

Puis définir :

```bash
export LBG_AGENT_QUESTS_URL="http://127.0.0.1:8030"
```

### Prod (systemd)

Unité : `infra/systemd/lbg-agent-quests.service` (port **8030**).

## Agent HTTP « combat » (optionnel)

Module : `lbg_agents.combat_http_app` (FastAPI).

- `GET /healthz` → JSON
- `POST /invoke` → corps `InvokeIn` (`actor_id`, `text`, `context`) ; réponse alignée sur `combat_stub` (`encounter`, `meta.sterile`).

Lancer en local (port suggéré **8040**) :

```bash
cd LBG_IA_MMO
source .venv/bin/activate
uvicorn lbg_agents.combat_http_app:app --host 0.0.0.0 --port 8040
```

Puis définir :

```bash
export LBG_AGENT_COMBAT_URL="http://127.0.0.1:8040"
```

### Prod (systemd)

Unité : `infra/systemd/lbg-agent-combat.service` (port **8040**).
