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

### DevOps — exécuteur à liste blanche (`agent.devops`)

Capability orchestrateur : **`devops_probe`** → handler **`agent.devops`**. Actions décrites dans `context.devops_action` (priorité de routage absolue) ou texte type « sonde devops » / « healthz backend ».

| Variable | Effet |
|----------|--------|
| `LBG_DEVOPS_HTTP_ALLOWLIST` | Liste d’URLs **exactes** autorisées pour `http_get`, séparées par des virgules. Si vide : défaut `http://127.0.0.1:8010/healthz` et `http://127.0.0.1:8000/healthz`. |
| `LBG_DEVOPS_LOG_ALLOWLIST` | Chemins de fichiers **exactes** pour `read_log_tail` (virgules). **Vide par défaut** → lecture fichier refusée. |
| `LBG_DEVOPS_DEFAULT_PROBE_URL` | URL utilisée quand le texte déclenche une sonde sans `devops_action` (défaut : healthz orchestrator). |
| `LBG_DEVOPS_DRY_RUN` | Si `1` / `true` / `yes` / `on` : **aucune** requête HTTP ni lecture fichier ; allowlist et audit inchangés. |
| `context.devops_dry_run` | Si `true` : même effet dry-run **pour cet appel** (sans redémarrer) ; combiné avec la case « DevOps dry-run » dans `/pilot/`. La variable d’environnement reste prioritaire (si elle active le dry-run, le contexte ne peut pas le désactiver). |
| `LBG_DEVOPS_APPROVAL_TOKEN` | Si défini (non vide) : toute exécution réelle (`http_get` / `read_log_tail` hors dry-run) exige `context.devops_approval` **égal** au jeton (comparaison `secrets.compare_digest`). Le jeton n’est jamais journalisé dans l’audit. Si non défini : pas de garde (comportement précédent). |
| `context.devops_approval` | Chaîne à fournir par l’appelant quand `LBG_DEVOPS_APPROVAL_TOKEN` est actif ; à ne pas logger côté client. |
| `LBG_DEVOPS_AUDIT_LOG_PATH` | Si défini : chaque audit est **ajouté** (append) dans ce fichier au format **JSONL** (une ligne JSON par action, champ `ts` en UTC ISO). Les répertoires parents sont créés si besoin. |
| `LBG_DEVOPS_AUDIT_STDOUT` | Si `0` / `false` / `no` / `off` : n’écrit plus l’audit sur stdout (fichier seul si `LBG_DEVOPS_AUDIT_LOG_PATH` est défini ; sinon l’audit est perdu — à éviter). |

Chaque action DevOps émet une ligne JSON `event: agents.devops.audit` (`ts`, `outcome`, `dry_run`, `dry_run_source`, `approval_gate_active`, `trace_id`, `url` / `path`, etc.) sur **stdout** par défaut (journald) et **en plus** dans le fichier si configuré. Valeur d’`outcome` supplémentaire : **`approval_denied`**. En cas d’erreur d’écriture fichier, un seul message `agents.devops.audit_file_error` part sur **stderr**.

**Prod** : compte **`lbg`** (sudoer, services non-root) — **`docs/ops_vm_user.md`** ; rotation JSONL / jeton — **`docs/ops_devops_audit.md`** (`infra/logrotate/lbg-devops-audit`).

Exemple `context` (JSON) :

```json
{
  "devops_action": { "kind": "http_get", "url": "http://127.0.0.1:8010/healthz" }
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
