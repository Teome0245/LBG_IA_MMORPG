## Bootstrap — LBG_IA_MMO (monorepo)

Ce workspace contient un scaffold complet dans `LBG_IA_MMO/` :
- `agents/` (stubs invoqués après routage, paquet `lbg_agents`)
- `backend/` (FastAPI)
- `orchestrator/` (multi-agents)
- `mmo_server/` (simulation headless)
- `infra/` (Docker + systemd + scripts)
- `docs/`

### Prérequis

- **Linux/WSL**: Python **3.10+** (3.11+ possible), `python3-venv`, `pip`, Docker (optionnel)

### Installation (local dev)

Depuis la racine du workspace :

```bash
cd LBG_IA_MMO
bash infra/scripts/install_local.sh
```

### Variables d’environnement (clés API, `LBG_*`)

Fichier unique : `LBG_IA_MMO/infra/secrets/lbg.env` (copier depuis `infra/secrets/lbg.env.example` si besoin).  
Avant les terminaux uvicorn, une fois par shell :

```bash
cd LBG_IA_MMO
set -a && source infra/secrets/lbg.env && set +a
```

### Lancer les services (local dev)

Dans 3 terminaux, depuis `LBG_IA_MMO/` (venv activé ; idéalement `lbg.env` sourcé comme ci‑dessus) :

```bash
source .venv/bin/activate
uvicorn orchestrator.main:app --host 0.0.0.0 --port 8010
```

```bash
source .venv/bin/activate
export LBG_ORCHESTRATOR_URL="http://127.0.0.1:8010"
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

```bash
source .venv/bin/activate
cd mmo_server && python3 -m uvicorn http_app:app --host 127.0.0.1 --port 8050
```
Après `source .venv/bin/activate`, `python3` pointe vers le venv (sur Ubuntu nu, la commande **`python` peut être absente** — utiliser **`python3`** ou le chemin absolu **`…/LBG_IA_MMO/.venv/bin/python -m uvicorn …`**).

(Tick monde + `GET /v1/world/lyra` ; aligner **`LBG_MMO_SERVER_URL=http://127.0.0.1:8050`** dans `lbg.env` pour le sync Lyra côté backend. L’état monde est **persisté** en JSON (défaut `mmo_server/data/world_state.json`, ou **`LBG_MMO_STATE_PATH`** — voir `mmo_server/README.md` et `docs/ops_vm_user.md` sur VM.) Boucle headless sans HTTP : `python3 mmo_server/main.py`.)

Astuce LAN : après modification du seed (nouveaux PNJ), le `mmo_server` peut continuer à charger l’état persisté.
Pour forcer le rechargement du seed sur la VM MMO, utiliser le script :

```bash
cd LBG_IA_MMO
LBG_VM_HOST=192.168.0.245 LBG_VM_USER=lbg bash infra/scripts/reset_mmo_state_vm.sh
```

### Serveur WebSocket jeu (`mmmorpg_server/`, port 7733)

Paquet **porté** dans le monorepo depuis le dépôt source `mmmorpg` (voir `LBG_IA_MMO/mmmorpg_server/README.md`, protocole `LBG_IA_MMO/docs/mmmorpg_PROTOCOL.md`). Après `install_local.sh` (sauf si `LBG_SKIP_MMMORPG_WS=1`) :

```bash
cd LBG_IA_MMO
source .venv/bin/activate
python -m mmmorpg_server
```

Sur **VM MMO** (après `LBG_DEPLOY_ROLE=mmo`) : `sudo systemctl status lbg-mmmorpg-ws` — voir `mmmorpg_server/README.md`.

### Vérification rapide (phase C — stack locale)

Une fois **backend (8000)**, **orchestrateur (8010)** et **`mmo_server` (8050)** démarrés (`lbg.env` sourcé si besoin) :

```bash
cd LBG_IA_MMO
bash infra/scripts/verify_stack_local.sh
```

Le script appelle les **`/healthz`** et tente un **`GET /v1/world/lyra?npc_id=npc:smith`** (échoue sans impact si le PNJ n’existe pas dans le seed). Variables optionnelles : `LBG_BACKEND_URL`, `LBG_ORCH_URL`, `LBG_MMO_HTTP_URL`.

**Prod LAN (trois VM)** — après déploiement et secrets : smoke SSH + systemd + Ollama sur **110** :

```bash
cd LBG_IA_MMO
bash infra/scripts/smoke_vm_lan.sh
```

### Smokes LAN : temps, redondance, variables

Les smokes LAN font souvent intervenir le pont WS→IA et/ou le LLM : la latence peut être élevée. Avant de relancer plusieurs scripts “au hasard”, préfère un chemin minimal et ajuste les timeouts.

**Variables communes** :

- **`LBG_SMOKE_TIMEOUT_S`** : timeout `curl` / CLI (défaut typique **120**, certains smokes plus courts). Augmente si le LLM est lent.
- **`LBG_SMOKE_REPEAT`** : nombre de répétitions pour certains smokes WS→IA (ex. `ws_ia_cli`) afin de lisser la variance (défaut typique **3**).

**Chemins recommandés (éviter les doublons)** :

- **Vérif infra/services (rapide, sans LLM)** :

```bash
cd LBG_IA_MMO
bash infra/scripts/smoke_vm_lan.sh
```

- **Smoke LAN minimal (non destructif, sans LLM, sans bench)** :

```bash
cd LBG_IA_MMO
LBG_SMOKE_TIMEOUT_S=30 bash infra/scripts/smoke_lan_minimal.sh
```

- **Smoke LAN quick (enchaîne, avec timings)** :

```bash
cd LBG_IA_MMO
LBG_SMOKE_TIMEOUT_S=30 bash infra/scripts/smoke_lan_quick.sh
```

Optionnels :

```bash
# Ajoute un appel /v1/pilot/route (peut toucher au LLM)
LBG_SMOKE_WITH_PILOT=1 LBG_SMOKE_TIMEOUT_S_PILOT=120 bash infra/scripts/smoke_lan_quick.sh

# Ajoute un test réputation (sans LLM) via commit reputation_delta
LBG_SMOKE_WITH_REP=1 LBG_SMOKE_TIMEOUT_S_MINIMAL=30 LBG_SMOKE_REP_DELTA=11 bash infra/scripts/smoke_lan_quick.sh

# Ajoute un test réputation "fallback monde" (sans LLM) — vérifie que `mmo_server` reste cohérent
LBG_SMOKE_WITH_REP_WORLD=1 LBG_SMOKE_TIMEOUT_S_MINIMAL=30 LBG_SMOKE_REP_DELTA=11 bash infra/scripts/smoke_lan_quick.sh

# Option : remet la réputation à 0 avant les smokes rep (évite l'accumulation run après run)
LBG_SMOKE_RESET_REP=1 LBG_SMOKE_WITH_REP=1 LBG_SMOKE_TIMEOUT_S_MINIMAL=30 LBG_SMOKE_REP_DELTA=11 bash infra/scripts/smoke_lan_quick.sh

# Option : valide le gate token sur mmo_server (écriture interne) si `LBG_MMO_INTERNAL_TOKEN` est défini
LBG_SMOKE_WITH_MMO_AUTH=1 bash infra/scripts/smoke_lan_quick.sh

# Ajoute WS→IA final-only (LLM) + répétitions
LBG_SMOKE_WITH_WS=1 LBG_SMOKE_TIMEOUT_S_WS=180 LBG_SMOKE_REPEAT=3 bash infra/scripts/smoke_lan_quick.sh
```

- **Pont “lecture monde” (snapshot interne WS) uniquement** :

```bash
cd LBG_IA_MMO
LBG_SMOKE_TIMEOUT_S=30 bash infra/scripts/smoke_bridge_ws_lyra.sh
```

- **Réputation (sans LLM)** :

```bash
cd LBG_IA_MMO
LBG_SMOKE_TIMEOUT_S=30 bash infra/scripts/smoke_reputation_lan.sh
```

- **Réputation E2E (sans LLM, fiable)** :

```bash
cd LBG_IA_MMO
LBG_SMOKE_TIMEOUT_S=30 bash infra/scripts/smoke_reputation_e2e_no_llm_lan.sh
```

- **Réputation “fallback monde” (sans LLM)** : vérifie que `mmo_server` reflète la réputation après commit (utile si le backend doit retomber sur `meta.source=mmo_world` quand le snapshot WS est indispo).

```bash
cd LBG_IA_MMO
LBG_SMOKE_TIMEOUT_S=30 bash infra/scripts/smoke_reputation_fallback_world_lan.sh
```

- **Auth (write) — pilot reputation** :

```bash
cd LBG_IA_MMO
LBG_SMOKE_TIMEOUT_S=10 bash infra/scripts/smoke_pilot_reputation_auth_lan.sh
```

- **Route backend (valide l’injection Lyra dans la réponse)** :

```bash
cd LBG_IA_MMO
LBG_SMOKE_TIMEOUT_S=120 bash infra/scripts/smoke_pilot_route_lyra_meta_lan.sh
```

- **WS→IA (réponse finale, bench JSON)** :

```bash
cd LBG_IA_MMO
LBG_SMOKE_TIMEOUT_S=180 LBG_SMOKE_REPEAT=3 bash infra/scripts/smoke_ws_ia_final_only_json.sh
```

Astuce : si tu veux “ça passe ou ça casse vite”, baisse `LBG_SMOKE_REPEAT` à 1 et garde un timeout raisonnable.

Si tu vois une erreur du type `set: pipefail\r: invalid option name`, le script a des fins de ligne Windows (CRLF).
Correctif rapide :

```bash
cd LBG_IA_MMO
bash infra/scripts/fix_crlf.sh
```

Note : `infra/scripts/deploy_vm.sh` exécute automatiquement ce correctif avant `rsync` (désactivable via `LBG_SKIP_FIX_CRLF=1`).

### Pont “jeu WS → IA” (Lyra snapshot, lecture seule)

Quand `mmmorpg_server` (WS) expose son **HTTP interne** et que le backend est configuré avec
`LBG_MMMORPG_INTERNAL_HTTP_URL`, le backend enrichit `context.lyra` via :
`GET /internal/v1/npc/{npc_id}/lyra-snapshot?trace_id=...` (LAN uniquement).

**Smoke LAN** (valide l’endpoint snapshot + l’appel `/v1/pilot/route` avec `world_npc_id`) :

```bash
cd LBG_IA_MMO
bash infra/scripts/smoke_bridge_ws_lyra.sh
```

**Token (optionnel)** :

- Serveur WS : `MMMORPG_INTERNAL_HTTP_TOKEN` (attend le header `X-LBG-Service-Token`)
- Backend : `LBG_MMMORPG_INTERNAL_HTTP_TOKEN` (envoie le header)

**Échecs typiques (dégradation attendue)** :

- Si l’HTTP interne `mmmorpg_server` ne répond pas (timeout / 401 / 404), le backend **retombe** sur
  `mmo_server` si `LBG_MMO_SERVER_URL` est défini ; sinon, `context.lyra` peut rester absent.
- Dans tous les cas, l’appel `/v1/pilot/route` doit continuer à répondre (best-effort).

### Réconciliation “IA → jeu” (phase 2) — commit idempotent

Le serveur WS `mmmorpg_server` expose aussi (HTTP interne) :

- `POST /internal/v1/npc/{npc_id}/dialogue-commit` (idempotent par `trace_id`)

**Contrat backend (filtrage/validation avant commit)** :

- Whitelist flags (config) : `LBG_MMMORPG_COMMIT_ALLOWED_FLAGS` (CSV). Défaut : `quest_accepted,quest_id,quest_step,mood,rp_tone,reputation_delta`.
- Limites best‑effort :
  - `LBG_MMMORPG_COMMIT_MAX_FLAGS` (défaut 16)
  - `LBG_MMMORPG_COMMIT_MAX_KEY_LEN` (défaut 64)
  - `LBG_MMMORPG_COMMIT_MAX_STR_LEN` (défaut 256)
- Types autorisés : valeurs JSON simples (`string/bool/int/float/null`). Si invalide : le backend n’appelle pas le commit et renvoie `commit_result.ok=false` (le dialogue reste servi).

**Smoke LAN** (commit puis vérifie que le snapshot expose `world_flags`) :

```bash
cd LBG_IA_MMO
bash infra/scripts/smoke_mmmorpg_commit.sh
```

Pilot statique sur **110** derrière Nginx, API sur **140** : depuis `LBG_IA_MMO/`,  
`bash infra/scripts/install_nginx_pilot_110.sh` (installe le paquet et active la conf), puis **`LBG_CORS_ORIGINS`** dans `lbg.env` et **`bash infra/scripts/push_secrets_vm.sh`** (au moins la VM **140**) — détails **`docs/fusion_env_lan.md`**.

### Pilot web (`/pilot/`) — commandes à saisir

`ERR_CONNECTION_REFUSED` ou page blanche = en pratique **aucun process n’écoute sur le port 8000** (backend non démarré) ou mauvaise URL selon ton setup (voir dépannage ci‑dessous).

**0. Une fois : installation du venv** (depuis la racine du workspace) :

```bash
cd LBG_IA_MMO
bash infra/scripts/install_local.sh
```

**0. (Optionnel) Agent HTTP dialogue** — pour que `agent.dialogue` appelle un vrai service sur le port **8020** (sinon stub local). Laisser tourner :

```bash
cd LBG_IA_MMO
source .venv/bin/activate
uvicorn lbg_agents.dialogue_http_app:app --host 0.0.0.0 --port 8020
```

**1. Terminal A — orchestrator** (laisser tourner) :

```bash
cd LBG_IA_MMO
source .venv/bin/activate
# Si l’étape 0 tourne : décommente / ajoute la ligne suivante
# export LBG_AGENT_DIALOGUE_URL="http://127.0.0.1:8020"
uvicorn orchestrator.main:app --host 0.0.0.0 --port 8010
```

**2. Terminal B — backend** (laisser tourner ; **obligatoire** pour `/pilot/`) :

```bash
cd LBG_IA_MMO
source .venv/bin/activate
export LBG_ORCHESTRATOR_URL="http://127.0.0.1:8010"
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

**3. Terminal C — vérif rapide** (doit répondre avant d’ouvrir le navigateur) :

```bash
curl -sS http://127.0.0.1:8000/healthz
curl -sS http://127.0.0.1:8000/v1/pilot/status
```

Tu dois voir du JSON (ex. `{"status":"ok"}` et un objet avec `backend":"ok"`).

**Health des agents (proxy same-origin)** — depuis le navigateur ou un poste du LAN, sans ouvrir les ports **8020** / **8030** / **8040** côté client : le backend relaie vers `LBG_AGENT_DIALOGUE_URL`, `LBG_AGENT_QUESTS_URL` et `LBG_AGENT_COMBAT_URL` :

```bash
curl -sS http://127.0.0.1:8000/v1/pilot/agent-dialogue/healthz
curl -sS http://127.0.0.1:8000/v1/pilot/agent-quests/healthz
curl -sS http://127.0.0.1:8000/v1/pilot/agent-combat/healthz
```

L’UI `/pilot/` utilise ces URLs pour les liens « healthz (proxy) ».

**4. Navigateur** — une fois le `curl` OK :

- URL : `http://127.0.0.1:8000/pilot/` ou `http://localhost:8000/pilot/`

**Dépannage**

| Symptôme | Piste |
|----------|--------|
| `Connection refused` sur `:8000` | Backend pas lancé : refaire l’étape 2 et regarder les logs uvicorn (erreur d’import, port déjà pris, etc.). |
| Port déjà utilisé | Autre chose sur 8000 : sous Linux/WSL `ss -tlnp` (repérer `:8000`) ou lancer uvicorn sur un autre port, ex. `--port 8001`, puis ouvrir `http://127.0.0.1:8001/pilot/`. |
| Navigateur **Windows**, code sous **WSL** | Souvent `http://localhost:8000/pilot/` suffit. Sinon, dans WSL : `hostname -I` → utiliser la **première IP** affichée : `http://<cette_IP>:8000/pilot/`. |
| Santé orchestrator `error` dans `/v1/pilot/status` | Terminal A (8010) arrêté ou `LBG_ORCHESTRATOR_URL` incorrect dans le terminal B. |

**VM privée** (services déjà sous systemd) : pas de démarrage manuel ; ouvre `http://192.168.0.140:8000/pilot/` (adapte l’IP).

### Tester

```bash
source .venv/bin/activate
pytest backend/tests orchestrator/tests mmo_server/tests agents/tests
```

### Docker

```bash
cd LBG_IA_MMO/infra/docker
docker compose up --build
```

### systemd (Linux)

Les unités template sont dans `LBG_IA_MMO/infra/systemd/`.
Hypothèse: déploiement dans `/opt/LBG_IA_MMO` + venv partagé `/opt/LBG_IA_MMO/.venv`.

Exemple (à adapter) :

```bash
sudo mkdir -p /opt/LBG_IA_MMO
sudo rsync -a --delete LBG_IA_MMO/ /opt/LBG_IA_MMO/
sudo bash /opt/LBG_IA_MMO/infra/scripts/install_local.sh

sudo cp /opt/LBG_IA_MMO/infra/systemd/lbg-agent-dialogue.service /etc/systemd/system/
sudo cp /opt/LBG_IA_MMO/infra/systemd/lbg-orchestrator.service /etc/systemd/system/
sudo cp /opt/LBG_IA_MMO/infra/systemd/lbg-backend.service /etc/systemd/system/
sudo cp /opt/LBG_IA_MMO/infra/systemd/lbg-mmo-server.service /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now lbg-agent-dialogue lbg-orchestrator lbg-backend lbg-mmo-server
```

### Production (VM Linux `192.168.0.140`)

Ici, on distingue bien :
- **Dev** : ton poste (WSL) + itérations rapides, Docker optionnel.
- **Prod** : VM Linux `192.168.0.140` (systemd recommandé).

#### Déploiement global initial (serveur vierge, reproductibilité)

Objectif : une **nouvelle** machine Linux sur le réseau privé peut recevoir la même stack que la prod actuelle, **sans** supposer qu’elle a déjà été préparée manuellement.

**Référence environnement** (à tenir à jour si tu changes de base) : Ubuntu **22.04 LTS** (Jammy), Python **3.10** via `python3`/`venv` système, déploiement applicatif sous **`/opt/LBG_IA_MMO`**.

**Sur la VM (une fois)** :

1. Compte dédié **`lbg`** : **sudoer** + SSH par clé — procédure : `LBG_IA_MMO/docs/ops_vm_user.md`. (Ancien compte personnel : possible le temps de la migration via `LBG_VM_USER=…`.)
2. Paquets minimaux (root) : `sudo apt update && sudo apt install -y python3 python3-venv rsync openssh-server` (et `git` si tu clones le dépôt sur la VM au lieu de recevoir un `rsync`).
3. Répertoire cible : `sudo mkdir -p /opt/LBG_IA_MMO` ; après premier déploiement, propriétaire **`lbg:lbg`** (fait par `deploy_vm.sh`).

**Depuis le poste de dev** (arbre `LBG_IA_MMO` à jour) :

**SSH (poste de dev / WSL)** : si `ssh lbg@<vm>` n’utilise pas automatiquement la bonne clé, force-la :

```bash
export LBG_SSH_IDENTITY="$HOME/.ssh/id_ed25519"
```

Optionnel : `export LBG_SSH_KNOWN_HOSTS_FILE=/tmp/lbg_known_hosts` (fichier `known_hosts` écrivable ; voir `docs/ops_vm_user.md`).

```bash
cd LBG_IA_MMO
LBG_VM_HOST=<IP_OU_HOSTNAME> LBG_VM_USER=<utilisateur_ssh> bash infra/scripts/deploy_vm.sh
```

Le script aligne le code, le venv, les unités systemd et redémarre les services. En **première** exécution, prévoir saisie **sudo** sur la VM si le ticket n’est pas encore en cache.

**Contrôle de fin de chaine** : `systemctl status lbg-orchestrator lbg-backend lbg-mmo-server` et `curl` sur `http://<vm>:8010/healthz` et `:8000/healthz`.

**Audit DevOps (JSONL) sur la VM** : si `LBG_DEVOPS_AUDIT_LOG_PATH` est défini (ex. `/var/log/lbg/devops_audit.jsonl`), créer le répertoire avec les bons droits, installer le fragment logrotate depuis le dépôt (`infra/logrotate/lbg-devops-audit` → `/etc/logrotate.d/`), et suivre la procédure de rotation du jeton `LBG_DEVOPS_APPROVAL_TOKEN` — détail : `LBG_IA_MMO/docs/ops_devops_audit.md`.

**Pour la traçabilité long terme** : consigner dans `docs/plan_de_route.md` (*État courant*) toute modification des prérequis ou des chemins « figés » ci‑dessus.

#### Pousser les évolutions dev → prod (habituel)

À faire **à chaque lot** que tu veux voir tourner sur la VM privée :

1. **Valider** : idéalement en local/WSL, `pytest backend/tests orchestrator/tests mmo_server/tests` (et tests manuels). **Tu peux aussi pousser direct vers la VM sans lancer la stack sur WSL** : la validation se fait alors **uniquement sur la prod privée** (étape 3). Sur réseau privé de confiance c’est un choix acceptable ; pour limiter les régressions (packaging, imports), les tests locaux restent recommandés.
2. **Déployer** : depuis `LBG_IA_MMO/`, exécuter `bash infra/scripts/deploy_vm.sh` (SSH + sudo sur la VM ; voir variables `LBG_VM_HOST`, `LBG_VM_USER` si besoin).
3. **Contrôler la prod** : `systemctl status` des trois services, `curl` sur `/healthz` (ports 8000 et 8010), et un scénario métier si tu en as un.
4. **Doc (priorité 0)** : si le comportement ou l’usage change, mettre à jour `docs/plan_de_route.md` (tableau *État courant*) et toute section API / infra concernée dans ce fichier ou `docs/architecture.md`.

Le script synchronise le code vers un répertoire de **staging** sur la VM, le promeut sous `/opt/LBG_IA_MMO` avec `sudo`, réinstalle le venv au besoin et recharge **systemd**.

##### Déployer depuis WSL sans exécuter les services en local

Tu n’as pas besoin d’ouvrir `uvicorn` sur ta machine : le dépôt vit sous WSL, le script pousse le code, la **VM exécute** systemd.

Exemple (adapte IP et user si besoin) :

```bash
cd LBG_IA_MMO
LBG_VM_HOST=192.168.0.140 LBG_VM_USER=lbg bash infra/scripts/deploy_vm.sh
```

Puis **contrôles depuis le même WSL** (ou tout poste du LAN autorisé) :

```bash
curl -sS http://192.168.0.140:8000/healthz
curl -sS http://192.168.0.140:8000/v1/pilot/status
curl -sS http://192.168.0.140:8010/healthz
curl -sS http://192.168.0.140:8020/healthz
```

Interface pilot sur la VM : `http://192.168.0.140:8000/pilot/` (navigateur sur un poste du réseau privé).

#### Déploiement “simple” (rsync + venv + systemd)

Depuis ta machine de dev (WSL), en supposant un accès SSH (user **`lbg`**, sudoer) :

```bash
rsync -a --delete LBG_IA_MMO/ lbg@192.168.0.140:/opt/LBG_IA_MMO/
ssh lbg@192.168.0.140 'cd /opt/LBG_IA_MMO && bash infra/scripts/install_local.sh'
ssh lbg@192.168.0.140 'sudo cp /opt/LBG_IA_MMO/infra/systemd/lbg-*.service /etc/systemd/system/ && sudo systemctl daemon-reload'
ssh lbg@192.168.0.140 'sudo systemctl enable --now lbg-agent-dialogue lbg-agent-quests lbg-agent-combat lbg-orchestrator lbg-backend lbg-mmo-server'
```

#### Déploiement via script (recommandé)

Un script “tout-en-un” existe :

```bash
cd LBG_IA_MMO
bash infra/scripts/deploy_vm.sh
```

Variables optionnelles :

```bash
LBG_VM_HOST=192.168.0.140 LBG_VM_USER=lbg bash infra/scripts/deploy_vm.sh
```

SSH / outillage (optionnel) :

```bash
export LBG_SSH_IDENTITY="$HOME/.ssh/id_ed25519"
export LBG_SSH_KNOWN_HOSTS_FILE=/tmp/lbg_known_hosts
# Désactiver le correctif CRLF automatique avant rsync (rare) :
# LBG_SKIP_FIX_CRLF=1 bash infra/scripts/deploy_vm.sh
```

#### Réseau/ports (par défaut)

- Agent HTTP dialogue : `8020/tcp` (`lbg-agent-dialogue`, `POST /invoke`)
- Orchestrator : `8010/tcp`
- Backend : `8000/tcp`
- MMO server : **`8050/tcp`** sur `127.0.0.1` en prod systemd (`http_app`, healthz + `/v1/world/lyra`) ; le backend utilise **`LBG_MMO_SERVER_URL`** si défini

#### Exemple API (intentions)

Sur un poste du **réseau privé**, avec backend et orchestrator déjà démarrés (local ou VM). Adapte l’hôte (`127.0.0.1` en dev, ou IP de la VM type `192.168.0.140` en prod).

**Backend** — le client appelle l’API ; le backend relaie vers l’orchestrator :

```bash
curl -sS -X POST "http://192.168.0.140:8000/v1/intents/route" \
  -H "Content-Type: application/json" \
  -d '{"actor_id":"test:1","text":"Je veux parler au forgeron","context":{}}'
```

Réponse attendue : HTTP **200** et un corps JSON du type `intent`, `confidence`, `routed_to`, `output`.

**Interface minimale `/pilot/`** : démarrer orchestrator + backend comme dans la section *Pilot web* plus haut, vérifier avec `curl` puis ouvrir l’URL dans le navigateur. Référence : `pilot_web/README.md`.

**Orchestrator (appel direct, debug)** — même charge utile, sans passer par le backend :

```bash
curl -sS -X POST "http://192.168.0.140:8010/v1/route" \
  -H "Content-Type: application/json" \
  -d '{"actor_id":"test:1","text":"Je veux parler au forgeron","context":{}}'
```

**Capabilities (introspection)** — liste enregistrée côté orchestrator :

```bash
curl -sS "http://192.168.0.140:8010/v1/capabilities"
```

**Capabilities via backend** (même origine que `/pilot/`) :

```bash
curl -sS "http://192.168.0.140:8000/v1/pilot/capabilities"
```

#### Documentation projet (à lire)

Dans `LBG_IA_MMO/docs/` :
- `plan_de_route.md` (priorités 0–3, suivi à jour à chaque étape)
- `architecture.md` (réseau, prod, composants)
- `vision_projet.md` (vision globale)
- `lyra.md` (Lyra 2.0 / jauges / intégrations)
- `plan_mmorpg.md` (plan serveur MMO multivers)

