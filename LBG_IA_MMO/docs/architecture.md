# Architecture (vue d'ensemble)

## Objectif

Construire un framework complet permettant :
- orchestration d’agents IA (LLM locaux + API)
- gestion d’un monde MMORPG dynamique
- simulation de populations civiles (NPC)
- quêtes dynamiques
- système de classes flexible et combinable
- jauges physiologiques (Lyra Engine)

## Composants

### Backend (`backend/`)
- API FastAPI typée, stable, orientée contrats.
- Ne contient pas de logique “métier MMO” directement : elle est portée par `mmo_server/` et exposée via des services/DTO.
- **Observabilité (opt-in)** : `GET /metrics` (format Prometheus texte) si `LBG_METRICS_ENABLED=1` ; protection optionnelle `LBG_METRICS_TOKEN` (header `Authorization: Bearer …`). Défaut **désactivé** ; checklist déploiement : `docs/runbook_validation_serveurs_lan.md` (§2bis, §2ter) et `bootstrap.md` (section métriques).

### Orchestrator (`orchestrator/`)
- Point d’entrée unique pour router une “intention” vers un ou plusieurs agents.
- **Observabilité (opt-in)** : même schéma que le backend pour `GET /metrics` (`LBG_METRICS_*`, désactivé par défaut).
- Registry de capacités + introspection robuste.
- Fallbacks déterministes (graceful degradation).
- **Lyra (futur)** : le contrat d’état optionnel `context.lyra` / `output.lyra` est décrit dans `lyra.md` ; **`lbg_agents.lyra_bridge`** applique un pas sur **`lyra_engine.gauges`** (si **`mmo_server`** dans le venv) pour **`agent.fallback`** et pour **`agent.dialogue`** avant l’appel HTTP à l’agent dialogue.
- Après routage, appelle le paquet **`agents/`** (`lbg_agents.dispatch.invoke_after_route`) pour enrichir le champ `output`. Le dialogue peut cibler un **agent HTTP** (`LBG_AGENT_DIALOGUE_URL`, port **8020** en prod systemd, voir `agents/README.md`). L’intention **`devops_probe`** déclenche **`agent.devops`** : GET HTTP et lecture de fichiers **uniquement** via listes blanches d’environnement (`agents/README.md`) ; dry-run **`LBG_DEVOPS_DRY_RUN`** ; garde **`LBG_DEVOPS_APPROVAL_TOKEN`** + `context.devops_approval` ; audit JSON **`agents.devops.audit`** (champ `ts`) sur stdout et/ou fichier **`LBG_DEVOPS_AUDIT_LOG_PATH`** (JSONL).
- Introspection : **`GET /v1/capabilities`** (liste des `CapabilitySpec`). Le backend expose **`GET /v1/pilot/capabilities`** en proxy pour l’UI `/pilot/`.

#### Brain (autonomie) — v1 (conscience + motivation)

Objectif : fournir une **autonomie safe** (“je fais des checks tout seul”) + une **conscience de l’état** (jauges) qui pilote une **motivation** (intent) — sans exécution destructive implicite.

- **Tick** : toutes les \(30s\) (configurable).
- **Périmètre v0 (safe)** :
  - DevOps `selfcheck` en **dry-run** (étapes HTTP + systemd *allowlistées*).
  - Ping `GET /healthz` du worker desktop (si `LBG_AGENT_DESKTOP_URL` est défini).
- **Périmètre v0 (sous approbation)** :
  - `systemd_restart` uniquement si opt-in + jeton d’approbation côté orchestrateur.

Endpoints orchestrator :
- `GET /v1/brain/status`
- `POST /v1/brain/toggle` (`{ "enabled": true|false }`)
- `POST /v1/brain/approve` (`{ "request_id": "…" }`) : approuve une demande (ex. restart) en file.

Proxy backend (same-origin) pour l’UI pilot :
- `GET /v1/pilot/orchestrator/brain/status`
- `POST /v1/pilot/orchestrator/brain/toggle`
- `POST /v1/pilot/orchestrator/brain/approve`

Conscience/motivation exposées via `brain/status` :
- `gauges` : jauges \([0–100]\) (ex. `confidence`, `stress`, `fatigue`, `curiosity`)
- `intent` : intention courante (`monitor|diagnose|request_approval|remediate`)
- `narrative` : résumé 1–2 lignes “pourquoi j’agis”
- `approval_requests[]` : file des demandes (restart, raison, approved/done)

Variables d’environnement (orchestrator) :
- `LBG_BRAIN_ENABLED` : `1|0` (défaut `0`)
- `LBG_BRAIN_INTERVAL_S` : secondes (défaut `30`, borné \([5,3600]\))
- `LBG_BRAIN_DEVOPS_AUTORESTART` : `1|0` (défaut `0`) — autorise la tentative de restart automatique
- `LBG_BRAIN_DEVOPS_APPROVAL` : jeton d’approbation (si vide, aucun restart n’est tenté en autonomie)
- `LBG_BRAIN_STATE_PATH` : chemin du fichier de persistance (défaut `/var/lib/lbg/brain/state.json`)
- `LBG_BRAIN_MAX_ACTIONS_PER_TICK` : budget d’actions par tick (défaut `3`)
- `LBG_BRAIN_RESTART_COOLDOWN_S` : cooldown restart systemd (défaut `600`)

#### DevOps — exécution des remédiations (phase 3 produit)

Les réponses **`selfcheck`** (et textes d’audit associés) peuvent inclure des **`remediation_hints`** : indications **lisibles** pour un opérateur (relancer un service, vérifier une URL, consulter un log). **Règle projet** : ces hints ne déclenchent **aucune** action corrective **automatique** côté LLM ou agent sans revue humaine. L’exécution sur l’infra (ex. **`systemd_restart`** après approbation, quota, fenêtre UTC) reste **explicite** (outil DevOps, systemd, playbook) — typiquement un **humain** ou un **agent d’outillage contrôlé** (ex. Cursor sur poste de confiance avec les mêmes prérequis SSH que la doc `ops_vm_user.md`) applique le correctif. Ne pas brancher de boucle « LLM → restart production » sans garde-fous documentés et revus.

### MMO Server (`mmo_server/`)
- Serveur headless tick-based.
- Monde data-driven, entités, quêtes, classes, simulation.
- NPC gouvernés par `lyra_engine/` (comportements + jauges).
- **HTTP** (`http_app`, uvicorn typiquement **8050**) : tick en thread d’arrière-plan ; **`GET /v1/world/lyra`** expose les jauges PNJ pour **`context.lyra`** (voir `docs/lyra.md`, variable **`LBG_MMO_SERVER_URL`** côté backend). En **prod systemd** (`lbg-mmo-server`), l’écoute est **`0.0.0.0:8050`** pour permettre au **backend sur une autre VM** d’appeler le LAN (`192.168.x.x:8050`) ; en local, **`127.0.0.1`** reste recommandé. Persistance **`WorldState`** en JSON (chargement au boot, sauvegarde périodique + arrêt) — **`LBG_MMO_STATE_PATH`**, **`LBG_MMO_SAVE_INTERVAL_S`** (`mmo_server/README.md`).

### Frontend et Pilotage (`pilot_web/` et `web_client/`)
- **Routage unifié (Nginx, port 8080)** : La VM 110 centralise l'accès utilisateur.
    - `http://<IP>:8080/` : Interface **Lyra / Pilotage** (Originale).
    - `http://<IP>:8080/mmo/` : Interface **Client MMO** (Vite).
    - `http://<IP>:8080/v1/` : Proxy vers le backend API (VM 140:8000).
- **Déploiement** : 
    - Le rôle `front` de `deploy_vm.sh` gère Lyra.
    - `deploy_web_client.sh` gère le MMO (build avec `--base=/mmo/` et déploiement dans le sous-dossier).
- **Note** : Le serveur Python sur le port **8081** est déprécié et supprimé.

## Exécution

- **Local** : plusieurs processus Python (API, orchestrator, `mmo_server`, option **`mmmorpg_server`**).
- **Docker** : 3 services + réseau interne.
- **systemd** : unités séparées, redémarrage automatique, logs journald.

## Production (VM)

La prod **LBG_IA_MMO** sur le LAN privé est actuellement sur **`192.168.0.140`** (machine dédiée à ce monorepo). La **répartition LAN** (orchestration + LBG_IA, MMO, LLM) est décrite dans **`docs/fusion_env_lan.md`** ; vue historique / fusion : **`docs/plan_fusion_lbg_ia.md`**.

Recommandation pour **cette** machine : **déploiement via systemd** (voir `../../bootstrap.md`) avec :
- code dans `/opt/LBG_IA_MMO`
- venv partagé `/opt/LBG_IA_MMO/.venv`
- ports exposés : API `8000`, orchestrator `8010`, Nginx `8080` (Interface Unifiée).

**Mise à jour depuis le dev** : le chemin nominal pour pousser une évolution vers cette VM est `infra/scripts/deploy_vm.sh` (staging + `rsync` sudo + `install_local.sh` en tant que **`lbg`** + reconfiguration systemd), lancé depuis le poste de développement (ex. WSL) **sans obligation** de faire tourner les mêmes services en local : la pile réelle est celle **systemd sur la VM** (unités `User=lbg`) ; les contrôles se font sur la prod privée (`curl`, UI `/pilot/`). Détail : `bootstrap.md`, `docs/ops_vm_user.md`.

## Déploiement global final et reproductibilité

**Finalité** : pouvoir **reconstruire un serveur équivalent** (même stack applicative, même emplacement des fichiers, mêmes services systemd) à partir d’une VM ou d’un matériel **neuf**, sans dépendre du tacite (mémoire d’une personne ou d’une seule machine déjà configurée).

**Principes** :

- **Source de vérité** : le dépôt `LBG_IA_MMO/` (code, `pyproject.toml`, unités sous `infra/systemd/`, scripts sous `infra/scripts/`). Les versions d’OS et de Python doivent rester **documentées** dans `bootstrap.md` (ex. Ubuntu 22.04 LTS, Python 3.10 côté Jammy).
- **Chemins figés** : `/opt/LBG_IA_MMO` pour l’application, `/opt/LBG_IA_MMO/.venv` pour le venv partagé (aligné sur les unités systemd).
- **Enchainement reproductible** : (1) prérequis système et utilisateur déployeur ; (2) mise du **contenu du monorepo** sur la cible ; (3) `install_local.sh` (venv + `pip install -e` des trois paquets) ; (4) installation des unités systemd et `daemon-reload` + `enable --now`. Le script `deploy_vm.sh` automatise (2)–(4) depuis le poste de dev ; pour un **premier** tir ou une VM sans accès depuis ce poste, suivre la checklist **serveur vierge** dans `bootstrap.md`.
- **Découverte des dépendances Python** : aujourd’hui les versions sont dans les `pyproject.toml` ; à terme, figer des **lockfiles** ou un export `pip freeze` de référence si tu exiges une reproductibilité binaire stricte.
- **Évolution** : toute nouvelle dépendance système (paquet `apt`, service additionnel, port, variable d’environnement obligatoire) doit être **répercutée dans `bootstrap.md` et, en cas d’impact produit, dans ce fichier**.

**Piste d’industrialisation** (optionnelle, plus tard) : image disque ou **cloud-init**, recette **Ansible**, ou image **OCI** dérivée de `infra/docker/`, pour en équipe matérialiser le même « déploiement global » en une commande ; le contenu du dépôt reste la référence fonctionnelle.

## Réseau et exposition (règle projet)

- **Prod actuelle** : la VM de production **n’est pas exposée sur Internet**. Elle reste sur un **réseau privé** de confiance (LAN / segment dédié / accès contrôlé). Les services (`8000`, `8010`, etc.) ne doivent être joignables que depuis ce périmètre et les acteurs autorisés (postes, bastion, VPN, selon ton infra).
- **Futur public** : si une offre ou un client doit être **accessible depuis l’extérieur**, le déploiement se fait sur une **VM (ou brique) distincte**, **exposée et durcie** (TLS, contrôle d’accès, surface minimale, séparation par rapport à la prod privée). La prod privée **ne devient pas** une cible Internet directe.
- Tant que l’on reste en **réseau privé sécurisé**, l’administration (SSH, mises à jour) et l’accès aux APIs restent alignés sur cette règle : pas de dérogation sans revue d’architecture explicite.

## Documents de référence

- `lexique.md` : termes, acronymes et définitions (**ADR**, composants) — transmission / onboarding
- `plan_de_route.md` : priorités (documentation, plateforme, Lyra, MMO, fusion) et état courant
- `plan_fusion_lbg_ia.md` : stratégie de fusion **LBG_IA** + **mmmorpg** (`~/projects/mmmorpg`, serveur WS) + ce monorepo (alignement produit unique, pont jeu ↔ IA)
- `fusion_etat_des_lieux_v0.md` : inventaire HTTP/WS et variables de pont (état des lieux fusion, phase A)
- `adr/0002-mmo-autorite-pont.md` : autorité monde (`mmmorpg` vs slice IA `mmo_server`)
- `fusion_spec_monde.md` / `fusion_pont_jeu_ia.md` : sources de vérité monde et pont IA
- `vision_projet.md` : vision globale / agents / auto‑évolution
- `lyra.md` : jauges & IA incarnée
- `plan_mmorpg.md` : plan serveur MMO (modules cibles)
- `ops_devops_audit.md` : VM — audit DevOps JSONL (logrotate), rotation du jeton d’approbation
- `ops_vm_user.md` : compte **`lbg`** (sudoer, SSH, `User=` systemd, `/opt`, secrets `640 root:lbg`)

