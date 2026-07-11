# Handoff — Équipe virtuelle studio (session 2026-07-07 → 2026-07-10)

**But** : reprendre la conversation et enchaîner phase A sans perdre le contexte infra / LLM / Claude.

**Documents canoniques** (à lire en premier) :

1. `docs/architecture_equipe_virtuelle_studio.md` — architecture cible
2. `docs/adr/0014-equipe-virtuelle-orchestrateur.md` — décisions
3. Ce fichier — état session + prochaines actions

---

## Résumé décision produit (validé « Go »)

L’orchestrateur **140** devient un **méta-orchestrateur** d’équipe virtuelle :

- **Ops** : infra Proxmox 201, VMs, disques, Ollama
- **Studio** : dev MMO, QA, PM, brief créatif
- **Monde** (plus tard) : compagnons / joueurs IA sur **245**

**Phase A** : rôles `ops`, `qa`, `pm` ; SQLite tâches ; API `/v1/team/*` ; Pilot `#/team` ; autonomie **L1**.

---

## État infra (dernière session connue)

### Proxmox 201 (`lbgr720`)

| VM | IP | RAM | CPU | Rôle |
|----|-----|-----|-----|------|
| 110 | .110 | 24 Go | 8 | Pilot, Ollama, front |
| 140 | .140 | 8 Go | 4 | Orchestrateur, agents |
| 245 | .245 | 16 Go | 4 | Serveur MMO |
| 246 | .246 | 16 Go | 4 | Prime |
| 250 | .250 | 4 Go | 2 | pfSense |
| 900 | — | 4 Go | 2 | Template |

- Stockages : `local-vm-930g` (disques VM), `Sauvegardes` → NAS iSCSI `/mnt/sauvegardes`
- Entrée Proxmox `NAS` (images iSCSI) **retirée** — sauvegardes uniquement sur LUN

### VM 110 — Ollama

- Version **0.31.1**
- Modèles : `gemma4:26b`, `gemma4:e2b`, `gemma4-claude` (Modelfile, ctx 8K)
- RAM VM montée à **24 Go**, **8 cœurs**
- `OLLAMA_NUM_THREADS=8`, `OLLAMA_HOST=0.0.0.0:11434`

### VM 140 — Dialogue / orchestration

- `LBG_DIALOGUE_LLM_MODEL=gemma4:26b`
- Routage : **Groq first**, failover → `gemma4:26b` local (`fast,local`)
- `LBG_DIALOGUE_TARGET_DEFAULT=auto`, `LBG_DIALOGUE_FAILOVER=1`
- Timeouts : agent 240s, orchestrateur 240s, Pilot invoke 300s

### Poste Windows `192.168.0.10`

- **Claude Code** 2.1.202 — config dans `C:\Users\sdesh\.claude\settings.json`
- **Infra ON** : `ANTHROPIC_BASE_URL=http://192.168.0.110:11434`, modèle `gemma4-claude`
- **Infra OFF** : Ollama local Windows ; forcer CPU : `OLLAMA_NO_GPU=1` (évite erreur CUDA)
- Script : `C:\Users\sdesh\claude-ollama-lan.ps1`
- **Cursor** : override `http://192.168.0.110:11434/v1` → erreur *« private networks forbidden »* (normal : passer par tunnel ou Claude Code)

### Claude Code par hôte

| Hôte | Rôle |
|------|------|
| **110** | Ollama seulement (pas Claude installé) |
| **140** | Claude Code `claude-lbg` — dev non-MMO, prompt `docs/prompt_claude_140_non_mmo.md` |
| **10** | Claude Code — dev local / attente infra OFF |

---

## Fichiers config importants (hors git)

- `LBG_IA_MMO/infra/secrets/lbg.env` — poussé via `push_secrets_vm.sh`
- `C:\Users\sdesh\.claude\settings.json` — Claude Code Windows
- `C:\Users\sdesh\.claude.json` — `hasCompletedOnboarding: true`

---

## Prompt pour reprendre dans Cursor / Claude

Coller en début de session :

```
Contexte LBG — équipe virtuelle studio (phase A).

Lis dans l'ordre :
- LBG_IA_MMO/docs/handoff_equipe_virtuelle_2026-07-10.md
- LBG_IA_MMO/docs/architecture_equipe_virtuelle_studio.md
- LBG_IA_MMO/docs/adr/0014-equipe-virtuelle-orchestrateur.md

Objectif immédiat : implémenter phase A sur VM 140 :
- module orchestrator/team/ (SQLite, routes /v1/team/*)
- rôles ops, qa, pm
- tests + entrée plan_de_route Historique

Infra LAN : 201 Proxmox, 110 Pilot+Ollama, 140 orchestrateur, 245 MMO, 10 poste dev.
Ne pas toucher au gel sandbox mmmorpg (ADR 0005) sans demande explicite.
```

---

## Prochaines actions (ordre)

### Immédiat (doc — fait si ce commit est poussé)

- [x] Architecture + ADR + handoff
- [x] Ligne Historique `plan_de_route.md`

### Phase A code (cette branche)

1. [x] `orchestrator/team/store.py` — SQLite schema + CRUD
2. [x] `orchestrator/team/roles.py` — mapping ops→devops_probe, qa→smoke, pm→project_pm
3. [x] `orchestrator/router/routes/team.py` — endpoints § API
4. [x] `orchestrator/tests/test_team.py`
5. [x] Backend proxy `pilot.py` + vue `#/team` (minimal)
6. [x] Smoke LAN : créer tâche `qa` + `POST .../run` → `smoke_vm_lan.sh` (validé LAN 2026-07-11)

### Phase B (en cours — 2026-07-11)

1. [x] Playbook L1 : `spawn_team_qa_smoke_job` + timer systemd `lbg-team-qa-smoke-job`
2. [x] Activer timer sur 140 (`install_team_qa_smoke_job_vm.sh` + vars `LBG_TEAM_QA_SMOKE_JOB_*`)
3. [x] Playbooks ops disque (`spawn_team_ops_storage_job`) + Ollama (`spawn_team_ops_ollama_job`)
4. [x] Activer timers ops sur 140 (`install_team_ops_jobs_vm.sh`)

### Phase C (début — 2026-07-11)

1. [x] QA échouée → suivi auto `pm` (+ `ops` + `dev_game` si smoke KO) — `orchestrator/team/qa_followup.py`
2. [x] UI `#/team` : filtres role/status/actor, L2 + token (repli `LBG_DEVOPS_APPROVAL_TOKEN`)
3. [x] Rôle `dev_game` — exécuteur phase C (`dev_game_brief` via agent.pm, hors sandbox mmmorpg)
4. [x] Auto-run L1 des tâches PM de suivi (`LBG_TEAM_QA_FOLLOWUP_AUTO_RUN_PM=1`)
5. [x] Assistant — `POST /v1/pilot/assistant/session-summary/mmo-bridge` + bouton « Appliquer pont MMO (API) »
6. [ ] Workflow dev_game complet (forge / action_proposal gameplay)

### Vérifications infra (quand LAN up)

```bash
# Depuis poste ou WSL
curl -s http://192.168.0.140:8010/healthz
curl -s http://192.168.0.110:11434/api/tags
curl -s http://192.168.0.140:8020/healthz
bash LBG_IA_MMO/infra/scripts/smoke_vm_lan.sh
```

### Optionnel infra

- [x] Playbook B (code) : job quotidien smoke → tâche team `qa` (`spawn_team_qa_smoke_job`, timer systemd)
- [x] Déploiement timer sur 140 en prod
- [x] `LBG_TEAM_APPROVAL_TOKEN` documenté (repli devops/jobs) dans `lbg.env.example`

---

## Ce qui n’est PAS dans le scope immédiat

- Merge git automatique
- Restart VM sans approbation
- Cursor Agent → Ollama LAN (bloqué cloud)
- Joueurs IA autonomes (phase D)
- GPU VM 110 (M2090 retiré du passthrough)

---

## Branche git suggérée

`cursor/equipe-virtuelle-phase-a-64b4` — docs puis code phase A.

---

*Dernière mise à jour : 2026-07-11 — phase A validée LAN, phase B smoke quotidien codé.*
