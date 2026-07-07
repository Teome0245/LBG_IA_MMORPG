# Handoff — migration poste Claude (Windows/WSL) → VM 140

**Dernière mise à jour** : 7 juillet 2026  
**Public** : Claude Code sur **Windows** (ou opérateur via PuTTY)  
**Objectif** : consolider sur **192.168.0.140** (`lbg-backend`) le travail déjà fait en local, sans casser la prod LAN.

---

## 1. Résumé en une phrase

Le dépôt **`LBG_IA_MMORPG`** (monorepo `LBG_IA_MMO/`) est prêt côté **WSL/Cursor** (chat pilot, streaming, scripts deploy). La VM **140** doit devenir le **poste Claude Code permanent** (tmux + `claude work .`) **en cohabitation** avec les services systemd prod déjà en place.

---

## 2. Topologie LAN (ne pas confondre les rôles)

| IP | Hostname | Rôle | Ce qui y reste |
|----|----------|------|----------------|
| **110** | `lbg-ia-ui` | Front Nginx **:8080**, Ollama **:11434**, UI prod | Build statique `pilot_web/v2/` — **pas** le poste dev Claude |
| **140** | `lbg-backend` | Backend **:8000**, orchestrateur **:8010**, agents **:8020–8055** | **Cible migration** : code `/opt/LBG_IA_MMO` + Claude Code + builds `pilot_shell` |
| **245** | `lbg-mmo-precu` | Core3 PreCU | **Hors scope** migration non-MMO |
| **246** | `lbg-mmo-prime` | Core3 Prime | **Hors scope** migration non-MMO |

**URLs opérateur**

| Contexte | UI | API |
|----------|-----|-----|
| Prod LAN | `http://192.168.0.110:8080/pilot/v2/` | `http://192.168.0.140:8000` |
| WSL test (Cursor) | `http://127.0.0.1:5175/pilot/v2/` | Proxy Vite → 140 |
| Poste Claude sur 140 | Navigateur local ou 110 | `http://127.0.0.1:8000` (prod locale) |

**Compte SSH** : **`lbg`** (sudoer) sur **110 / 140 / 245**. PuTTY Windows : clé **`.ppk`** obligatoire. Le compte **`sdesharches`** n’est fiable que sur **245/246**, pas sur **110/140**.

---

## 3. Ce qui a déjà été fait (côté WSL / Cursor — juillet 2026)

### 3.1 Git — branche `feature/antigravity-tasks`

| Commit | Contenu |
|--------|---------|
| `c2ccc1a` | Lot principal : `pilot_shell` v2, chat SSE, `pm_llm`, outils assistant, `dev_pilot_workflow.sh`, hostnames LAN, build `pilot_web/v2` |
| `60cf478` | `bootstrap_claude_on_core140.sh`, doc VM 140 + Claude |
| `4caae13` | Nettoyage `node_modules` du dépôt (`.gitignore`) |

Remote : `https://github.com/Teome0245/LBG_IA_MMORPG.git`  
État attendu : working tree propre après pull de cette branche.

### 3.2 Fonctionnalités pilot (non-MMO) livrées

- **Backend** : `POST /v1/pilot/assistant/chat` + `/assistant/chat/stream` (`backend/api/v1/routes/pilot.py`)
- **Routage** : bypass classifieur → `project_pm` pour intents `pilot_chat` / `pilot_assistant`
- **Agent PM** : streaming + outils (`grep`, ssh, core3) — `agents/src/lbg_agents/{pm_llm,assistant_tools,repo_context,pm_http_app}.py`
- **Frontend** : `pilot_shell/` — `useAgentChat.ts`, `AgentChat.tsx`, modes Chat / Supervisé / Ops
- **Workflows** : `infra/scripts/dev_pilot_workflow.sh` (deploy core@140, front@110, dev WSL)
- **Infra** : `set_lan_hostnames.sh`, doc `fusion_env_lan.md`, `ops_vm_user.md`

### 3.3 Ce qui reste à faire sur 140 (pas encore exécuté)

- [ ] Resize Proxmox VM 140 : **16 GiB RAM**, **100+ GiB** disque
- [ ] `growpart` + `resize2fs` dans la VM
- [ ] `bash infra/scripts/bootstrap_claude_on_core140.sh`
- [ ] `claude login` (interactif, compte `lbg`)
- [ ] `git pull` branche à jour sur `/opt/LBG_IA_MMO`
- [ ] Deploy prod : `dev_pilot_workflow.sh --full` ou `deploy_vm.sh`
- [ ] Session tmux persistante : alias `lbg-tmux`, `claude-lbg`

---

## 4. Inventaire à compléter côté Windows (Claude : remplir § 8)

Avant migration, relever ce qui existe **localement** sur le poste Windows / WSL :

| Élément | Chemin typique Windows | Chemin typique WSL | Action migration |
|---------|------------------------|--------------------|------------------|
| Clone Git | `C:\Users\<user>\projects\LBG_IA_MMORPG` ou `\\wsl$\...\projects\LBG_IA_MMORPG` | `~/projects/LBG_IA_MMORPG` | **Ne pas** dupliquer : 140 = `/opt/LBG_IA_MMO` via `deploy_vm.sh` ou `git pull` |
| Secrets | `LBG_IA_MMO/infra/secrets/lbg.env` (local, **jamais** commité) | idem | `push_secrets_vm.sh` vers `/etc/lbg-ia-mmo.env` sur 140 |
| Agent desktop Windows | `C:\Agent_IA\` (sync depuis `windows_agent/Agent_IA/`) | — | **Reste sur Windows** — pas migrer vers 140 |
| PuTTY sessions | `.ppk` + sessions `lbg@192.168.0.140` | — | Conserver ; cible principale poste Claude |
| Claude Code auth | `~/.claude/` (Windows ou WSL) | `~/.claude/` | **Refaire** `claude login` sur 140 (compte `lbg`) |
| Builds npm locaux | `pilot_shell/node_modules/` | idem | Régénérer sur 140 : `npm install && npm run build` |
| Modifications non commitées | ? | ? | Commit/push **avant** deploy, ou patch manuel sur 140 |

---

## 5. Plan de migration (ordre recommandé)

### Phase A — Prérequis Proxmox (hors VM, console hyperviseur)

1. VM **140** arrêtée (ou resize à chaud selon stockage Proxmox).
2. **RAM** → 16384 MiB.
3. **Disque** → 100 GiB minimum (`local-lvm` ou `local-vm-930g`).
4. Redémarrer la VM.

### Phase B — Disque dans la VM 140

```bash
ssh lbg@192.168.0.140
lsblk
# Adapter si partition ≠ sda3 :
sudo growpart /dev/sda 3
sudo resize2fs /dev/sda3
df -h /
```

### Phase C — Synchroniser le code sur 140

**Option 1 — depuis WSL (recommandé si deploy habituel)**

```bash
cd ~/projects/LBG_IA_MMORPG/LBG_IA_MMO
git checkout feature/antigravity-tasks
git pull
LBG_DEPLOY_ROLE=core LBG_VM_HOST=192.168.0.140 bash infra/scripts/deploy_vm.sh
bash infra/scripts/push_secrets_vm.sh   # si lbg.env local à jour
```

**Option 2 — depuis 140 (si repo git déjà configuré)**

```bash
ssh lbg@192.168.0.140
cd /opt/LBG_IA_MMO
git fetch && git checkout feature/antigravity-tasks && git pull
# Puis restart services si besoin :
sudo systemctl restart lbg-backend lbg-orchestrator lbg-agent-pm
```

### Phase D — Bootstrap Claude Code sur 140

```bash
ssh lbg@192.168.0.140
cd /opt/LBG_IA_MMO
bash infra/scripts/bootstrap_claude_on_core140.sh
```

Puis **interactif** (obligatoire) :

```bash
sudo -u lbg -i
claude login
```

### Phase E — Session de travail persistante (PuTTY)

```bash
ssh lbg@192.168.0.140
lbg-tmux          # crée ou rattache session "lbg"
claude-lbg        # cd /opt/LBG_IA_MMO && claude work .
```

### Phase F — Publier l’UI sur 110

Depuis WSL (poste qui a Node + clé SSH) :

```bash
cd ~/projects/LBG_IA_MMORPG/LBG_IA_MMO
bash infra/scripts/dev_pilot_workflow.sh --full
# ou sans restart backend :
bash infra/scripts/dev_pilot_workflow.sh
```

### Phase G — Vérifications

```bash
# Depuis WSL ou 140
curl -sf http://192.168.0.140:8000/healthz && echo OK backend
curl -sf http://192.168.0.140:8010/healthz && echo OK orch
curl -sf http://192.168.0.140:8055/healthz && echo OK agent PM
curl -sf -o /dev/null -w "%{http_code}\n" http://192.168.0.110:8080/pilot/v2/
bash infra/scripts/smoke_vm_lan.sh   # si disponible depuis poste dev
```

Test chat : UI prod → mode **Chat** → message simple → réponse streamée + éventuels blocs outils.

---

## 6. Règles de cohabitation prod / dev sur 140

| Autorisé | Interdit |
|----------|----------|
| `claude work .` dans `/opt/LBG_IA_MMO` | Lancer une 2ᵉ stack FastAPI sur :8000 en parallèle de systemd |
| `npm run build` dans `pilot_shell/` (creux de charge) | `npm run dev` permanent sur 140 (réservé au WSL test :5175) |
| `systemctl restart lbg-*` après deploy | Modifier `/etc/lbg-ia-mmo.env` sans passer par `push_secrets_vm.sh` |
| Lecture logs : `journalctl -u lbg-backend -f` | Commiter des secrets ou `node_modules` |

**Variable clé sur 140** : `LBG_REPO_ROOT=/opt/LBG_IA_MMO` (grep / contexte assistant PM).

---

## 7. Fichiers de référence (dans le dépôt)

| Fichier | Rôle |
|---------|------|
| `docs/fusion_env_lan.md` | Topologie complète, variables env, deploy |
| `docs/ops_vm_user.md` | Compte `lbg`, SSH, PuTTY, hostnames |
| `infra/scripts/bootstrap_claude_on_core140.sh` | Node 20, Claude, tmux, alias |
| `infra/scripts/dev_pilot_workflow.sh` | Build + deploy UI + option `--full` |
| `infra/scripts/deploy_vm.sh` | Rsync + install core/mmo/front |
| `infra/scripts/push_secrets_vm.sh` | `lbg.env` → `/etc/lbg-ia-mmo.env` |
| `infra/secrets/lbg.env.example` | Template variables (pas de secrets réels) |
| `docs/ui_refactor_plan.md` | Vision `pilot_shell` type Cursor |
| `docs/desktop_hybride.md` | Agent Windows `C:\Agent_IA` — **reste sur PC** |

---

## 8. Journal d’inventaire local (à remplir par Claude Windows)

> Claude : complète cette section lors de la première session de migration.

### 8.1 Poste source

- [ ] OS Windows version : ___
- [ ] WSL installé ? oui / non — distro : ___
- [ ] Chemin clone Git local : ___
- [ ] Branche Git actuelle : ___
- [ ] Modifications non commitées (liste fichiers) : ___

### 8.2 Accès réseau

- [ ] `ssh lbg@192.168.0.140` OK sans mot de passe : oui / non
- [ ] PuTTY session 140 configurée (.ppk) : oui / non
- [ ] `curl http://192.168.0.140:8000/healthz` depuis Windows/WSL : ___

### 8.3 État VM 140 (avant migration)

```bash
# Coller sortie de :
ssh lbg@192.168.0.140 'hostname; free -h; df -h /; node -v 2>/dev/null; command -v claude; systemctl is-active lbg-backend lbg-orchestrator lbg-agent-pm'
```

### 8.4 Écarts détectés

| Écart | Action proposée | Statut |
|-------|-----------------|--------|
| | | |

---

## 9. Périmètre explicite (non-MMO)

**In scope** : backend 140, orchestrateur, agents, `pilot_shell`, deploy 110, Claude Code sur 140, scripts infra LAN.

**Out of scope** (sauf demande explicite) : Core3 245/246, `mmmorpg_server` WS :7733 (décommissionné), contenu monde MMO, World Editor IG.

---

## 10. Contacts / dépôt

- Dépôt : `https://github.com/Teome0245/LBG_IA_MMORPG.git`
- Branche active : `feature/antigravity-tasks`
- Proxmox : `https://192.168.0.201:8006/` (VMID 140)

---

*Document généré pour échange Cursor (WSL) → Claude Code (Windows) → exécution sur VM 140.*
