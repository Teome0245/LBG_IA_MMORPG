# Plan de fusion LBG_IA ↔ LBG_IA_MMO ↔ mmmorpg

**Objectif** : fusionner progressivement **trois** lignées de code en **un produit cohérent** — orchestration IA (**LBG_IA**), chaîne agents + monde « slice IA » (**LBG_IA_MMO**), serveur jeu temps réel (**mmmorpg**) — sans se perdre : ce document est la **piste d’atterrissage** ; `plan_de_route.md` pointe ici pour les jalons.

### Objectif final (décision)

- **ADR** : **`docs/adr/0001-tronc-monorepo.md`** — tronc unique, sources **LBG_IA** / **mmmorpg** en lecture pour la fusion.
- **Un seul dépôt Git** : ce monorepo (**`LBG_IA_MMO/`**) devient le **référentiel unique** du projet assemblé (code, docs, déploiement).
- **Trois machines (LAN)** : topologie **3 hôtes** reste la cible d’exploitation (répartition dans **`fusion_env_lan.md`** — isoler charge et pannes, pas « un serveur par dépôt » à terme).
- **Un projet complet cohérent** : une base de code unifiée, contrats et runbooks alignés, sans maintenir indéfiniment trois historiques parallèles.

### Règle sur les dépôts sources **LBG_IA** et **mmmorpg**

- **Ne pas modifier** le contenu canonique de **`~/projects/LBG_IA/`** ni de **`~/projects/mmmorpg/`** pour les besoins de la fusion : ils servent de **référence** (lecture, comparaison, reprise de versions).
- Toute évolution fonctionnelle se fait par **reproduction, adaptation et intégration dans le monorepo** (nouveaux packages ou répertoires sous **`LBG_IA_MMO/`**, avec traçabilité dans les ADR / ce plan).
- Un **workspace Cursor multi-racines** reste utile **pendant la migration** pour ouvrir les trois arbres côte à côte ; l’état **cible** est **un clone / un seul repo** pour le développement quotidien.

**Dépôts concernés** (chemins typiques sous WSL/Linux) :

| Dépôt | Rôle dans ce plan |
|--------|-------------------|
| **`~/projects/LBG_IA_MMORPG/LBG_IA_MMO/`** (ce monorepo) | **Tronc cible** : intégration de tout le livrable ; VM, systemd, `mmo_server`, agents `lbg_agents`, et à terme code porté depuis **LBG_IA** et **mmmorpg**. |
| **`~/projects/LBG_IA/`** | **Source** (non modifiée ici) : orchestrateur Docker/Vue, `RouterIA`, Postgres, etc. ; doc : `LBG_IA/docs/REFERENCE_PROJET_LBG_IA.md`. |
| **`~/projects/mmmorpg/`** | **Source** (non modifiée ici) : **`mmmorpg_server`**, WebSocket (**7733**), `PROTOCOL.md`, client Godot prototype. **Complémentaire** de `mmo_server` dans le monorepo : voir **§3.4**. |
| **`~/projects/new_mmo/`** (ou clone sous `LBG_IA_MMO/third_party/new_mmo/`) | **Serveur jeu Core3 / SWGEmu** (binaire **`core3`**, **MMOCoreORB**, MariaDB **`swgemu`**). **Lignée distincte** du couple Python `mmmorpg_server` + `mmo_server` — coexistence et migration : **`docs/adr/0005-new-mmo-core3-coexistence.md`**, **`docs/migration_new_mmo_core3.md`**. |

**MMO — deux briques aujourd’hui** : **mmmorpg** (joueurs, WS, planète Terre1, entités réseau) et **`mmo_server`** (tick léger, **HTTP** `/v1/world/lyra`, **Lyra PNJ ↔ backend/orchestrateur**). La fusion « monde » consiste à **les unifier dans le monorepo** (autorité, ponts, dépréciation progressive des doublons) selon les phases et ADR, sans confondre les rôles tant que les contrats ne sont pas unifiés.

### Production (LAN privé) — état actuel documenté

**Répartition cible détaillée** (variables d’environnement, `deploy_vm.sh`, option frontend) : **`docs/fusion_env_lan.md`**.

Ancrage mémoire — **état visé** (à ajuster si les rôles évoluent) :

| IP | Rôle principal |
|----|----------------|
| **`192.168.0.140`** | **Orchestrateur LBG** (monorepo) + **stack LBG_IA** (Vue/Docker/`RouterIA` selon déploiement) — **`deploy_vm.sh`** → cette machine par défaut. |
| **`192.168.0.245`** | **Serveur MMO** : **`mmmorpg`** + **`mmo_server`** (HTTP Lyra) |
| **`192.168.0.110`** | **LLM local** (Ollama, etc.) + modules déportés ; **option** : frontend statique |

**Stratégie d’hébergement** (décision **indépendante** de la fusion des dépôts) :

- **Garder trois serveurs** : isolation des pannes, **déploiements** découplés, **charge** séparée (jeu vs orchestration IA), surface d’attaque réduite par service.
- **Rassembler** certaines fonctionnalités sur une machine plus tard : coût d’infra, simplicité d’ops, **mais** documenter les **ports**, **URLs** (`LBG_*`, `MMMORPG_*`, etc.) et **timeouts** réseau (latence LAN faible mais non nulle).

#### Répartition idéale : une, deux ou trois machines

| Mode | Idée | Quand |
|------|------|--------|
| **3 hôtes** | Rôles réseau séparés (ex. **core / LLM+front / MMO** — voir **`fusion_env_lan.md`**) | **Cible de fusion** : un dépôt, trois VMs, déploiements découpés par rôle. |
| **2 hôtes** | Regrouper deux rôles sur une VM | Réduction matérielle ; **ADR** + mise à jour des **URLs** dans tous les `.env`. |
| **1 hôte** | Toute la stack sur une machine (ports distincts) | Lab ; **documenter** conflits de ports et ordre de démarrage. |

Tout changement de répartition doit être reflété dans **`plan_fusion_lbg_ia.md`** (ce tableau), **`plan_de_route.md`** (*État courant*), et les fichiers d’environnement concernés (`lbg.env.example`, `bootstrap.md` si chemins changent).

#### Script `deploy_vm.sh` (ce monorepo uniquement)

- **Fichier** : `LBG_IA_MMO/infra/scripts/deploy_vm.sh`.
- **Périmètre** : déploiement du **monorepo LBG_IA_MMO** vers **une** VM (`LBG_VM_HOST`, défaut **`192.168.0.140`**), promotion vers `/opt/LBG_IA_MMO`, `install_local.sh`, unités **systemd** du dépôt.
- **Hors périmètre aujourd’hui** : ne déploie **pas** encore tout le périmètre **porté** depuis les dépôts sources (les morceaux encore non intégrés au monorepo suivent leur procédure d’origine en attendant).
- **Vision** : à mesure que **LBG_IA** et **mmmorpg** sont **reproduits dans le monorepo**, étendre ce script (ou scripts sœurs sous `infra/`) pour couvrir les **rôles** documentés dans **`fusion_env_lan.md`** — **un seul repo**, déploiements paramétrés par machine.
- **Fusion** : tant que les rôles restent sur des **hôtes** différents, **`deploy_vm.sh`** reste le **chemin nominal** pour ce qui est **déjà** dans le monorepo ; regrouper physiquement des services ne change pas l’exigence de **documenter** ports et `ROOT_DIR`.

Les variables d’environnement des backends doivent pointer vers les **bons hôtes** (ex. `LBG_MMO_SERVER_URL` vers **140** si `mmo_server` y reste ; `LBG_ORCHESTRATOR_URL` / agents **110** si l’UI LBG_IA appelle l’orchestrateur MMO sur une autre machine ; clients **mmmorpg** vers **245** — **à figer dans un tableau env par rôle** en phase A du plan).

**Routage LLM (convergence minimale, sans port de code)** : tant que le **catalogue** détaillé des providers (`orchestrateur/backend/src/providers/`, `RouterIA`, etc.) reste sur **LBG_IA** en référence, on peut quand même **unifier le comportement** côté monorepo en alignant **`LBG_DIALOGUE_FAST_*`**, **`LBG_DIALOGUE_REMOTE_*`**, l’ordre `LBG_DIALOGUE_AUTO_ORDER` et le failover sur les **mêmes** URL OpenAI-compatibles (`/v1/chat/completions`) et **mêmes clés** que ceux configurés pour Groq, OpenRouter ou tout backend distant utilisé par LBG_IA. L’agent MMO (`lbg_agents/dialogue_llm.py`) consomme déjà ces endpoints ; **un routeur unique dans le monorepo n’est pas une exigence produit** — tout port ou bibliothèque partagée reste **optionnel** et à trancher plus tard si besoin. Référence env : `infra/secrets/lbg.env.example`, `agents/README.md`.

En cas de divergence entre ce plan et le code, **le code et les ADR adoptés après fusion** font foi — ce fichier doit être **mis à jour** à chaque jalon.

---

## 1. Principes (non négociables pour ne pas « se perdre »)

1. **Pas de big bang** : intégration par **strangler** (briques coexistants dans le monorepo, contrats explicites, puis retrait du doublon).
2. **Un dépôt cible, sources en lecture** : **LBG_IA** et **mmmorpg** ne sont **pas** modifiés pour la fusion ; le **tronc unique** est **`LBG_IA_MMO/`** — y **porter** le code et la doc utiles, avec ADR pour les arbitrages (structure de dossiers, dépendances).
3. **Contrats avant refactor** : OpenAPI / schémas pour **agents**, **Lyra**, **monde** avant de mélanger les implémentations portées.
4. **Une vérité Lyra** : deux moteurs de jauges actuels → **spécification unifiée** (namespaces ou modèle unique) documentée avant migration code.
5. **Sécurité** : conserver le niveau **le plus strict** des trois lignées (DevOps, jetons, audit, réseau privé).
6. **Exploitation** : viser **trois machines** comme cadre de prod (voir **`fusion_env_lan.md`**), pas trois dépôts à long terme.

---

## 2. Synthèse « meilleur des trois »

| Domaine | **LBG_IA** | **LBG_IA_MMO** | **mmmorpg** |
|---------|------------|----------------|-------------|
| **UX / produit** | SPA Vue (`/lyra`, `/agents/map`), chat riche | Pilot `/pilot/` intégration / debug | Client **Godot** (prototype), focus **serveur** d’abord |
| **Orchestration IA** | `RouterIA`, `IntentClassifierV2`, Brain + LLM | Orchestrateur **léger**, capabilities, **`trace_id`** | N/A (serveur jeu, pas routeur intentions) |
| **Infra** | Docker Compose, Postgres, Traefik | **systemd**, VM, `deploy_vm.sh`, `lbg.env` | `python -m mmmorpg_server`, variables `MMMORPG_*` |
| **Agents / IA jeu** | Agents HTTP `/execute`, catalogue | `lbg_agents`, dialogue/quêtes/combat, DevOps probe | PNJ **basiques** côté `game_state` / entités (Phase 1) |
| **Lyra** | `LyraEngineV2` | `context.lyra`, **`mmo_server`** sync PNJ | Non central aujourd’hui — **à brancher** (PNJ ↔ IA) via pont |
| **Monde jeu** | `WorldSimulationCore` (in-process) | **`mmo_server`** HTTP + persistance fichier **slice IA** | **Autorité** réseau : WS, `world_tick`, jour/nuit 6 h, entités |
| **Doc** | `REFERENCE_PROJET_LBG_IA`, infra Git | `ops_*`, `bootstrap` | `ARCHITECTURE.md`, `PROTOCOL.md`, `SERVER_NEXT.md` |

**Lecture stratégique** : **mmmorpg** apporte le **chemin client ↔ serveur** et l’**état monde multijoueur** ; **LBG_IA_MMO** apporte la **chaîne IA** (orchestrateur, agents, **Lyra PNJ** via `mmo_server`) ; **LBG_IA** apporte la **coquille produit** (UI, DB, routeur riche). Produit unifié = **décider où vit l’autorité PNJ/joueur** (probablement **mmmorpg**) et comment **l’orchestrateur** lit/écrit (HTTP interne, message queue, ou extension du protocole WS — **ADR requis**).

---

## 3. Correspondance détaillée

### 3.1 Agents

| Concept | LBG_IA | LBG_IA_MMO |
|---------|--------|------------|
| Enregistrement | `init_agents()`, `BaseAgent`, ids `devops_wsl`, `windows`, `linux_*`, etc. | `CapabilitySpec` + `routed_to` → `lbg_agents.dispatch` |
| HTTP sortant vers agent | `/capabilities`, `/execute` | `/invoke` (dialogue, quêtes, combat), healthz |
| DevOps | `RoutingPolicy.devops_actions`, `POST /agents/{id}/run` + `ADMIN_TOKEN` | `devops_probe`, allowlists, `LBG_DEVOPS_APPROVAL_TOKEN`, audit JSONL |
| **Fusion** | Normaliser vers **une** surface (gateway : `/execute` *et* `/invoke` en interne) ou **deux profils** documentés (générique vs jeu). |

### 3.2 Lyra

| Concept | LBG_IA | LBG_IA_MMO |
|---------|--------|------------|
| Moteur | `LyraEngineV2` + état local `LyraState` (jauges 0–100 + profils) | `lyra_engine.gauges` (jauges moteur 0–1) + contrat `context.lyra` / `output.lyra` |
| Jauges existantes | **`chaleur`**, **`energie`**, **`patience`**, **`confiance`** (0–100) | **`hunger`**, **`thirst`**, **`fatigue`** (0–1) + extensions libres (ex. `stress`, `patience`) dans `context.lyra.gauges` |
| Mécaniques d’évolution | **Temporel (tick/decay)** : boucle `lyra_tick_loop` appelle `LyraEngineV2.apply_decay()` toutes les **30 s**. Règles v2.3 : énergie **100 → 0 en ~4 h** (≈0,416 %/min) ; si énergie à 0, chaleur/patience/confiance décrochent au même débit ; si énergie < 30, conversion automatique **1 %** de la jauge la plus haute (chaleur/patience/confiance) → **+3 %** énergie (1×/tick) ; si énergie > 90, buff périodique ; profil HAL9000 si chaleur < 20 (hystérésis). **Évènements** : `update_on_success/error/long_conv` (voir `lyra_state.py`) + `modify_gauge` clamp 0–100 + `get_style_modifier()` par seuils | `GaugesState.step(dt_s)` si au moins une jauge moteur (`hunger`/`thirst`/`fatigue`) est présente, clamp 0–1 ; sinon echo (pas de step) ; `meta.source=mmo_world` ou `mmmorpg_ws` évite double-step |
| Contrat API | Routes `GET /lyra/state`, `POST /lyra/update`, `GET /lyra/snapshot` (v2, events Postgres) | `context.lyra`, `output.lyra`, `meta.source: mmo_world` (ou `mmmorpg_ws`) ; injection possible via backend (`LBG_MMO_SERVER_URL`) |
| **Fusion** | **Reprendre** les mécaniques LBG_IA (succès/erreur/long_conv + style par seuils) et **ajouter** les jauges LBG_IA (chaleur/energie/patience/confiance) dans le schéma Lyra du monorepo, **sans casser** le flux PNJ (hunger/thirst/fatigue). Ensuite : **ajustement / dédoublonnage** (mapping, renommage, namespaces `lyra_assistant` vs `lyra_npc`, plages 0–1 vs 0–100) pour éviter les doublons. |

**Règles de mapping (constat LBG_IA, à intégrer puis dédoublonner juste après)** :

- **Énergie** : **dérivée** = moyenne de **Faim + Soif + Fatigue** (valide “pour le moment”). Formule proposée dans `fusion_spec_lyra.md` (§6).
- **Stress ↔ confiance** : même mesure (alias) → **canonique = `confiance`** (valide “pour le moment”) ; `stress` devient une **vue** optionnelle.
- **Chaleur** : jauge **complémentaire** (pas une résultante directe), utile au style/ton (HAL/normal, empathie, etc.).
- **Recharge par consommation** : mécanique “consommer X recharge Y” à formaliser dans le schéma unifié (ex. conversions / transferts type `LyraEngineV2` : 1 % d’une jauge → +3 % énergie).

**Notes de portage (source LBG_IA, lecture seule)** :

- Jauges + règles : `LBG_IA/orchestrateur/backend/src/services/lyra_state.py`
- UX (sliders, presets, historique, style preview) : `LBG_IA/orchestrateur/frontend/src/pages/LyraPage.vue` + composants `components/lyra/*`
- Contrat API LBG_IA : `LBG_IA/orchestrateur/backend/docs/API_REFERENCE.md` (section Lyra)

### 3.3 Monde (LBG_IA vs slice IA dans ce monorepo)

| Concept | LBG_IA | LBG_IA_MMO |
|---------|--------|------------|
| Simulation | `WorldSimulationCore`, async, entités + besoins | `WorldState`, `SimulationLoop`, thread, **HTTP** dédié |
| Persistance | Moins centralisée côté fichier monde dans l’extrait analysé | `world/persistence.py`, `LBG_MMO_STATE_PATH` |
| Client jeu | `/world/*`, `/godot/*` (doc) | Pilot + **`LBG_MMO_SERVER_URL`** pour **Lyra PNJ** (pas le client joueur) |
| **Fusion (IA)** | Option : consommer **`/v1/world/lyra`** ou état exporté depuis **mmmorpg** quand un pont existe | Rôle **slice IA** : jauges PNJ pour dialogue/orchestrateur ; **pas** l’autorité mouvement joueur |

### 3.4 Monde jeu temps réel — **mmmorpg** vs **`mmo_server`** (LBG_IA_MMO)

| Concept | **`~/projects/mmmorpg`** | **`mmo_server`** (ce monorepo) |
|---------|--------------------------|--------------------------------|
| **Rôle** | Serveur **multijoueur** : WebSocket, `hello` / `move`, `world_tick`, entités joueurs + PNJ **réseau** | Service **out-of-band** pour **IA** : HTTP **8050**, `GET /v1/world/lyra`, persistance **`WorldState`** orientée **jauges Lyra** PNJ |
| **Transport** | **WebSocket** (`docs/PROTOCOL.md`), port **7733** (`MMMORPG_*`) | **HTTP** REST (healthz, lyra) |
| **Tick** | `game_loop_broadcast`, `MMMORPG_TICK_RATE_HZ` (ex. 20 Hz) | Tick **5** Hz dans `http_app`, thread dédié |
| **Alignement `plan_mmorpg.md`** | Roadmap explicite Phase 1–3, `SERVER_NEXT.md` | Cohérent avec vision **data-driven** / PNJ ; **pas** le même code |
| **Fusion cible (pistes)** | **A.** **Serveur jeu porté** (depuis la source **mmmorpg**) = **autorité monde** dans le monorepo ; `mmo_server` absorbé ou **déprécié** au profit d’APIs dans ce serveur (HTTP interne Lyra). **B.** **Coexistence** : `mmo_server` reste **passerelle IA** jusqu’à parité dans le serveur jeu intégré. **C.** **Décision actuelle** : tout le code utile **reproduit dans `LBG_IA_MMO/`** (pas de modification du dépôt **`~/projects/mmmorpg`**), CI et ADR pour structure des dossiers et pont. |

---

## 4. Matrice de décision — choix du « tronc »

Noter chaque ligne **1–5** (importance) puis scorer **LBG_IA** vs **MMO** (lequel convient le mieux). Somme pondérée pour décision **indicative** (à valider humainement).

| Critère | Poids (à remplir) | Meilleur candidat (note) |
|---------|-------------------|---------------------------|
| UI riche (Vue) indispensable | | LBG_IA |
| Postgres / tâches longues (Antigravity, etc.) | | LBG_IA |
| Déploiement VM systemd sans Docker | | MMO |
| Serveur monde processus séparé + persistance fichier | | MMO |
| Contrat agents jeu (`invoke`, capabilities MMO) | | MMO |
| Pipeline RouterIA / Brain déjà stabilisé | | LBG_IA |
| Audit DevOps fichier + jeton (modèle MMO) | | MMO |
| **Serveur WS + client Godot (Phase jeu)** | | **mmmorpg** |
| **Slice IA monde / Lyra PNJ sans WS** | | **LBG_IA_MMO** (`mmo_server`) |
| Équipe / habitude sur un dépôt | | (contexte) |

**Décision alignée avec l’objectif « un repo »** (révisable par ADR) : **tronc = monorepo `LBG_IA_MMO/`**. Y **intégrer** en priorité ce qui existe déjà (orchestrateur léger, `mmo_server`, `lbg_agents`), puis **porter** depuis **LBG_IA** (UI Vue, Postgres, `RouterIA`, etc.) et depuis **mmmorpg** (serveur WS, protocole, logique monde) par **copie adaptée** — pas de modification des dépôts sources. Pour la **boucle jeu**, le serveur temps réel porté depuis **mmmorpg** reste la **brique autoritaire réseau** une fois intégré ; **`mmo_server`** peut rester passerelle IA jusqu’à convergence (voir §3.4).

---

## 5. Phases de réalisation

### Phase A — Cartographie (sans modifier les dépôts sources)

- [x] Inventaire **routes HTTP** : monorepo dans **`fusion_etat_des_lieux_v0.md`** (OpenAPI) ; **LBG_IA** référencé via **`orchestrateur/backend/docs/HTTP_ROUTES.md`** (dépôt source, lecture seule).
- [x] Inventaire **mmmorpg** : synthèse **WS + `MMMORPG_*` + PROTOCOL** dans **`fusion_etat_des_lieux_v0.md`** ; détail dans le dépôt source (`docs/PROTOCOL.md`, `README.md`, `SERVER_NEXT.md`).
- [x] Table **variables d’environnement** : **LAN / `LBG_*`** dans **`fusion_env_lan.md`** ; pont fusion résumé §4 de **`fusion_etat_des_lieux_v0.md`** (table trois colonnes complète = option **phase B**).
- [x] **ADR tronc** : **`docs/adr/0001-tronc-monorepo.md`** (accepté).
- [x] **Sous-ADR** : **`docs/adr/0002-mmo-autorite-pont.md`** (autorité monde, pont jeu ↔ IA).
- [x] **Définition de fin** : **`docs/fusion_etat_des_lieux_v0.md`** (état des lieux fusion v0).

### Phase B — Spécifications transverses

- [x] Document **Lyra unifiée** : **`fusion_spec_lyra.md`** (champs, plages, `kind` assistant vs PNJ).
- [x] Document **Agents unifiés** : **`fusion_spec_agents.md`** (contrat minimal + mapping `execute` ↔ `invoke`).
- [x] Document **Monde** : **`fusion_spec_monde.md`** (A/B/C + diagramme Mermaid).
- [x] **Pont jeu ↔ IA** : **`fusion_pont_jeu_ia.md`** (phases lecture / réconciliation, checklist).

### Phase C — Intégration technique (strangler)

- [x] Branchement **réseau** : **`fusion_env_lan.md`** + script **`infra/scripts/verify_stack_local.sh`** (healthz backend / orchestrateur / `mmo_server`) ; variables **`LBG_*`** dans **`infra/secrets/lbg.env.example`**.
- [x] Embarquement **`mmo_server`** : déjà couvert par **`deploy_vm.sh`** (rôle `mmo`) et **`bootstrap.md`** — LAN documenté.
- [x] **Serveur jeu** : paquet **`mmmorpg_server/`** (port depuis le dépôt source `mmmorpg`, `pip install -e`, tests `pytest mmmorpg_server/tests`) — **systemd / LAN 7733** : à câbler comme pour le reste (VM **245**).
- [x] Tests **chaîne pilot ↔ Lyra MMO** : **`backend/tests/test_pilot_route_mmo_lyra_chain.py`**. **DevOps + `trace_id`** : **`backend/tests/test_pilot_route_devops_trace.py`**. **`verify_stack_local.sh`** pour healthz. **À étendre** : E2E WS + intention IA **réseau réel** ; DevOps avec services non mockés.
- [x] **Réputation locale (v1)** : commit `reputation_delta` côté **`mmmorpg_server`** (autorité “jeu WS”) + **double-write** best-effort vers **`mmo_server`** (`POST /internal/v1/npc/{npc_id}/reputation`, token optionnel `LBG_MMO_INTERNAL_TOKEN`) pour garder le fallback `meta.source=mmo_world` cohérent ; smokes LAN + auth dédiée ; doc `ops_pont_interne_auth_rl.md`.
- [x] **Fiabilisation scripts** : `infra/scripts/fix_crlf.sh` + exécution automatique avant `rsync` dans **`deploy_vm.sh`** (opt-out `LBG_SKIP_FIX_CRLF=1`) + `.editorconfig` (LF).

### Phase D — Convergence code

- [ ] Déduplication des implémentations de routage / Lyra / monde **dans le monorepo** (par étapes), sans toucher aux dépôts sources **LBG_IA** et **mmmorpg**.
- [ ] Migration progressive des **variables** vers un seul **schéma d’env** documenté (ex. `lbg.env.example` + rôles par machine).

### Phase E — Produit

- [ ] Une **UI** opérateur cohérente (portage Vue et/ou pilot étendu **dans le monorepo**).
- [ ] **Doc utilisateur** unique + **runbook** déploiement **trois machines** à partir du **seul repo**.

---

## 6. Risques et mitigations

| Risque | Mitigation |
|--------|------------|
| Double maintenance longue | Phases courtes + **ADR** à chaque choix |
| Régression sécurité | Reprendre les **garde-fous les plus stricts** ; tests DevOps |
| Lyra incohérente | **Spécification** avant migration ; tests de non-régression sur prompts |
| Dette Docker vs systemd | Documenter **deux modes** (dev compose / prod VM) si besoin transitoire |
| **Dérive entre dépôt source et portage** | Sources **LBG_IA** / **mmmorpg** en **lecture** ; versions de référence notées dans les ADR ; revue à chaque import majeur |
| **Trois dépôts vivants trop longtemps** | Objectif **un repo** : phases courtes, jalons dans `plan_de_route.md` |

---

## 7. Lien avec le travail courant (LBG_IA_MMO)

- Le **plan de route habituel** continue (plateforme, Lyra, MMO) ; la fusion **ajoute** le portage depuis les dépôts sources **sans les modifier**.
- Dès que la **phase A** est lancée, ajouter une ligne dans **`plan_de_route.md`** (*État courant*) à chaque jalon de fusion.
- Les évolutions **données monde** (PNJ YAML, etc.) dans le monorepo **restent compatibles** avec le pont jeu ↔ IA : privilégier **fichiers data** et **contrats stables**.
- **Backlog `mmmorpg` côté source** : consulter **`SERVER_NEXT.md`** pour **inspiration** et parité fonctionnelle lors du **port dans le monorepo** ; résumer en *État courant* les écarts volontaires ou reports.

---

## 8. Historique documentaire

| Date | Événement |
|------|-----------|
| 2026-04-11 | Création de `plan_fusion_lbg_ia.md` ; intégration au `plan_de_route.md` du monorepo LBG_IA_MMO. |
| 2026-04-11 | Ajout du dépôt **`~/projects/mmmorpg`** (WS, protocole, serveur jeu) ; §3.4 et phases A–C enrichis. |
| 2026-04-11 | **Topologie LAN prod** : 192.168.0.140 / 0.110 / 0.245 — stratégie hébergement distinct vs regroupement. |
| 2026-04-11 | **Répartition 1/2/3 machines** ; **`deploy_vm.sh`** = LBG_IA_MMO seulement ; typo `MMMORPG_*` corrigée. |
| 2026-04-11 | Répartition cible **140** (orch + LBG_IA), **245** (MMO), **110** (LLM + option front) → **`docs/fusion_env_lan.md`**. |
| 2026-04-12 | **Stratégie fusion** : **un seul dépôt** (monorepo), **LBG_IA** et **mmmorpg** **non modifiés** — reproduction / intégration ici ; **cible prod** : **trois machines**, projet **cohérent** ; principes, phases, matrice et risques alignés. |
| 2026-04-12 | **ADR 0001** : **`docs/adr/0001-tronc-monorepo.md`** — tronc **`LBG_IA_MMO/`**, sources externes en lecture ; phase A : case ADR tronc cochée. |
| 2026-04-12 | **`docs/lexique.md`** : lexique (dont définition **ADR**) pour transmission du projet. |
| 2026-04-12 | **Phase A (jalon)** : **`docs/fusion_etat_des_lieux_v0.md`** — inventaire routes monorepo (OpenAPI), renvoi **`HTTP_ROUTES.md`** (LBG_IA), synthèse **mmmorpg**. |
| 2026-04-12 | **ADR 0002** : **`docs/adr/0002-mmo-autorite-pont.md`** — autorité **`mmmorpg`** vs slice IA **`mmo_server`**, pont cible ; **seed PNJ** versionné (`mmo_server/world/seed_data/world_initial.json`, `LBG_MMO_SEED_PATH`). |
| 2026-04-12 | **Phase B** : **`fusion_spec_lyra.md`**, **`fusion_spec_agents.md`**, **`fusion_spec_monde.md`**, **`fusion_pont_jeu_ia.md`** — specs transverses (Lyra, agents, monde, pont). |
| 2026-04-12 | **Phase C (incrément)** : **`infra/scripts/verify_stack_local.sh`**, test **`test_pilot_route_mmo_lyra_chain.py`**, section bootstrap « vérification rapide ». |
| 2026-04-12 | **Port `mmmorpg_server/`** + **`docs/mmmorpg_PROTOCOL.md`** ; **`install_local.sh`** / **`install_local_mmo.sh`** + `LBG_SKIP_MMMORPG_WS` ; tests DevOps **`test_pilot_route_devops_trace.py`**. |
| 2026-04-12 | **Réseau prod + reprise LAN** : **`LBG_CORS_ORIGINS`**, conf **`pilot_web_110`**, **`smoke_vm_lan`** ; **`push_secrets`** 3 VM, **`deploy_vm` `all`** ; **110** : **Traefik** (`orchestrateur-traefik`) vs nginx **:80** → pilot **`LBG_NGINX_PILOT_PORT=8080`** + CORS ; **`fusion_env_lan.md`**. |
| 2026-04-12 | **systemd `lbg-mmmorpg-ws.service`** ; rôle **`deploy_vm.sh` mmo** ; **`push_secrets_vm.sh`** redémarre les unités présentes uniquement. |
| 2026-04-16 | **Réputation + monde** : double-write `mmo_server` + token `LBG_MMO_INTERNAL_TOKEN` ; smokes LAN (auth + fallback monde) ; `fix_crlf` intégré au déploiement ; doc fusion (phase C) alignée. |
