# Pont jeu ↔ IA (brouillon — phase C)

Comment un **dialogue PNJ** (orchestrateur, agents, LLM) reste **aligné** avec l’état **mmmorpg** une fois les deux stacks branchées. Complète l’ADR **`0002`** avec des **flux** et **garde‑fous** opérationnels.

**Prérequis** : identifiants **`npc_id`** stables (`fusion_spec_monde.md`), contrat **`context.lyra`** (`fusion_spec_lyra.md`, `lyra.md`).

---

## 1. État actuel (sans pont WS)

- **IA** : backend appelle **`GET /v1/world/lyra`** (`mmo_server`) si **`LBG_MMO_SERVER_URL`** + **`world_npc_id`**.
- **Jeu** : clients **`mmmorpg`** en **WS** — pas de lien automatique avec **`mmo_server`**.

Les états peuvent **diverger** (acceptable en R&D — ADR 0002).

---

## 2. Phase 1 — Lecture seule vers l’IA

**Objectif** : l’orchestrateur / le backend enrichissent **`context.lyra`** à partir d’une **vue** du monde jeu **sans écrire** dans le simulateur WS.

**Pistes techniques** (une ou plusieurs) :

| Piste | Description |
|-------|-------------|
| **A. Export HTTP** côté serveur jeu intégré | `GET /internal/v1/npc/{npc_id}/lyra-snapshot` (LAN uniquement, auth service) renvoyant jauges / pose minimale. |
| **B. Miroir léger** | Processus qui lit le **game state** du serveur WS et met à jour un **cache** consommé comme aujourd’hui par **`mmo_server`** ou par le backend directement. |
| **C. Snapshot dans message** | Extension **`world_tick`** ou message dédié incluant un bloc **`lyra_hint`** pour PNJ — le client ne l’utilise pas forcément ; un **bridge** côté serveur alimente l’API IA. |

**Implémentation actuelle (monorepo)** :

- **Piste A** réalisée via l’HTTP interne optionnel de `mmmorpg_server` :
  - `GET /internal/v1/npc/{npc_id}/lyra-snapshot?trace_id=...`
  - **auth optionnelle** : header **`X-LBG-Service-Token`** si `MMMORPG_INTERNAL_HTTP_TOKEN` est défini côté serveur WS.
- Le backend consomme cette source en **priorité** si `LBG_MMMORPG_INTERNAL_HTTP_URL` est défini (sinon fallback sur `mmo_server` via `LBG_MMO_SERVER_URL`).

**Règles** :

- Toute lecture porte un **`trace_id`** ou **`request_id`** pour corrélation avec les logs **`mmmorpg`**.
- **Timeouts** et **fallback** : si le jeu ne répond pas, conserver le comportement **`mmo_server`** ou Lyra **sans** `mmo_world` (dégradation documentée).

---

## 3. Phase 2 — Écriture / réconciliation

**Objectif** : une **proposition** issue du LLM (quête acceptée, humeur, flag RP) **ne s’applique** au monde partagé que si le **serveur jeu** valide.

**Modèle** :

1. **File d’événements** (idempotents) : `npc_dialogue_commit` avec `npc_id`, `payload`, `trace_id`.
2. Le **serveur jeu** valide (règles métier, anti‑triche, cohérence avec la scène).
3. **Réponse** : `accepted` / `rejected` + `reason` ; propagation vers **`output`** agent et UI.

Évite l’**écriture directe** depuis l’orchestrateur dans deux mondes à la fois (interdit ADR 0002 sans règle).

**Garde‑fous ops (LAN)** :

- L’appel `mmmorpg_server` → backend se fait via `POST /v1/pilot/internal/route` (service→service).
- Protéger cet endpoint par token + rate‑limit (`LBG_PILOT_INTERNAL_TOKEN`, `LBG_PILOT_INTERNAL_RL_*`)
  et configurer `MMMORPG_IA_BACKEND_TOKEN` côté serveur WS. Détails : `ops_pont_interne_auth_rl.md`.

### 3.1 Contrat “commit dialogue” (backend → serveur jeu)

**But** : transformer une proposition du LLM en **événement idempotent** appliqué (ou rejeté) par l’autorité jeu.

**Source** : l’agent peut inclure un bloc `output.commit` dans sa réponse orchestrateur.

**Forme attendue (agent → backend)** :

- `output.commit.npc_id` (**string**, requis) : ex. `npc:merchant` (sinon fallback `context.world_npc_id`).
- `output.commit.flags` (**object**, optionnel) : ensemble de flags “dialogue” proposés.

**Validation backend (best-effort, avant HTTP interne)** :

- **Whitelist config-driven** : seules les clés listées dans `LBG_MMMORPG_COMMIT_ALLOWED_FLAGS` sont transmises.
  - Défaut (si variable absente) : `quest_accepted, quest_id, quest_step, mood, rp_tone`
- **Limites** :
  - `LBG_MMMORPG_COMMIT_MAX_FLAGS` (défaut 16)
  - `LBG_MMMORPG_COMMIT_MAX_KEY_LEN` (défaut 64)
  - `LBG_MMMORPG_COMMIT_MAX_STR_LEN` (défaut 256)
- **Types** : valeurs JSON simples uniquement (`string/bool/int/float/null`). Le backend rejette le commit s’il détecte des types non supportés.

**Forme envoyée au serveur jeu (backend → mmmorpg_server)** :

`POST /internal/v1/npc/{npc_id}/dialogue-commit`

Payload JSON :

- `trace_id` (**string**, requis) : idempotence (même `trace_id` → noop accepté).
- `flags` (**object**, optionnel) : résultat après filtration/validation.

**Résultat** :

- `HTTP 200` : `accepted=true` (appliqué ou noop idempotent).
- `HTTP 409` : `accepted=false` + `reason` (rejet autorité jeu).
- En cas d’erreur côté backend (contrat invalide) : `commit_result.ok=false` et `error=invalid_commit_flags` (le dialogue reste servi).

---

## 4. Côté protocole WebSocket (piste long terme)

- Nouveau type de message **client → serveur** réservé aux **outils** / admin : *hors scope* joueur standard.
- Ou **canal séparé** (HTTP interne) pour ne pas mélanger avec `move` / `hello` joueurs.

Le détail sera fixé lors du **portage `mmmorpg`** dans le monorepo (RFC courte + tests d’intégration).

---

## 5. Checklist de reprise

- [x] Chaîne **backend** : `world_npc_id` + **`LBG_MMO_SERVER_URL`** → `context.lyra` avant orchestrateur (test **`backend/tests/test_pilot_route_mmo_lyra_chain.py`**).
- [x] Contrôle **manuel** services : **`infra/scripts/verify_stack_local.sh`** (+ section **bootstrap.md**).
- [x] Exposer une **lecture** stable depuis le **serveur jeu** (`mmmorpg` porté) → état minimal pour l’IA (HTTP interne `mmmorpg_server` + `backend/services/mmo_lyra_sync.py`).
- [x] Décider **auth** : **token service** (réseau privé + header `X-LBG-Service-Token`) via `MMMORPG_INTERNAL_HTTP_TOKEN` (serveur WS) / `LBG_MMMORPG_INTERNAL_HTTP_TOKEN` (backend).
- [x] Tests E2E (smoke) : `infra/scripts/smoke_bridge_ws_lyra.sh` (snapshot + appel `/v1/pilot/route` avec `world_npc_id`).
- [x] Documenter les **échecs** (timeouts) : voir section “pont WS → IA (Lyra snapshot)” dans `bootstrap.md` (runbook court).

---

## Voir aussi

- `adr/0002-mmo-autorite-pont.md`
- `fusion_spec_agents.md`
- `fusion_spec_monde.md`
