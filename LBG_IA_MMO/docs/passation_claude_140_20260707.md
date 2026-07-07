# Passation opérateur → Claude 140 (VM `lbg-backend`)

**Date** : 7 juillet 2026  
**Branche active** : `feature/antigravity-tasks`  
**Racine prod** : `/opt/LBG_IA_MMO`  
**Dépôt** : `https://github.com/Teome0245/LBG_IA_MMORPG.git`

---

## 1. Contexte en une phrase

Le monorepo `LBG_IA_MMO` a livré en juillet 2026 une **UI pilot type Cursor** (`pilot_shell` → `/pilot/v2/`), un **agent PM LLM** avec chat SSE, et la **décision ADR 0013** : la VM **140** devient le **poste Claude Code permanent** (Ollama sur 110, modèle `gemma4-claude`), en cohabitation avec la prod systemd.

---

## 2. Topologie LAN

| IP | Rôle | Périmètre Claude 140 |
|----|------|----------------------|
| **110** | Nginx `:8080`, Ollama `:11434`, UI prod | Deploy front uniquement |
| **140** | Backend `:8000`, orchestrateur `:8010`, agents `:8020–8055` | **Poste de travail** |
| **245** | Core3 PreCU | **Interdit** phase 1 |
| **246** | Core3 Prime | **Interdit** phase 1 |

**URLs opérateur**

| Contexte | UI | API |
|----------|-----|-----|
| Prod LAN | `http://192.168.0.110:8080/pilot/v2/` | `http://192.168.0.140:8000` |
| Poste Claude sur 140 | Navigateur local ou 110 | `http://127.0.0.1:8000` (prod locale) |
| Ollama (LLM) | — | `http://192.168.0.110:11434` (`gemma4-claude`) |

**Compte SSH** : `lbg` (sudo) sur 110/140 — pas `sdesharches`.

---

## 3. Sujets ouverts par fil de travail

### A. Migration poste Claude → VM 140 — priorité immédiate

| Statut | Élément |
|--------|---------|
| ✅ Fait (WSL/Cursor) | ADR 0013, `CLAUDE.md`, `handoff_windows_vers_vm140.md`, `prompt_claude_140_non_mmo.md/.txt`, scripts `claude_ollama_lan.sh`, `verify_claude_alignment.sh`, `bootstrap_claude_on_core140.sh` |
| ✅ Fait | Fix `claude_140_inject_context.sh` (`REMOTE_DIR=/opt/LBG_IA_MMO`) |
| ❌ Pas encore fait sur 140 | Resize Proxmox (16 GiB RAM, 100+ GiB disque), `growpart`/`resize2fs`, `bootstrap_claude_on_core140.sh`, `claude login` interactif, `git pull` branche à jour, deploy `--full`, session tmux `lbg-tmux` / `claude-lbg` |
| ❌ À compléter | Section §8 du handoff (inventaire local Windows/WSL) |

**Docs pivot** : `docs/handoff_windows_vers_vm140.md`, `docs/adr/0013-claude-code-vs-hermes-openclaw.md`, `docs/fusion_env_lan.md`

---

### B. pilot_shell / UI opérateur — largement livré, polish restant

| Phase | Contenu | Statut |
|-------|---------|--------|
| 0–6 | Coquille IDE, chat, vues métier, Monaco/xterm, bascule `/pilot/` → v2 | ✅ Terminé (6–7 juil.) |
| Suite suggérée | Polish streaming, visibilité outils PM, modes Chat/Supervisé/Ops, stabilité deploy | 🟡 À faire |

**Livrables juillet 2026**

- `pilot_shell/` React + TypeScript
- `POST /v1/pilot/assistant/chat` + `/stream`
- Agent PM (`pm_llm.py`, `assistant_tools.py`)
- `dev_pilot_workflow.sh` (deploy core@140 + front@110)

**Doc** : `docs/ui_refactor_plan.md`, ADR 0011

---

### C. Assistant Core / Jobs « Cowork » — implémenté, validation ops

Session du 4 juin 2026 : moteur de jobs autonomes avec approbation, replan, mémoire d'expériences, mode agentique, SSH multi-VM, remédiation.

| Composant | Fichiers clés |
|-----------|---------------|
| Jobs runner | `orchestrator/services/jobs.py`, `planner.py` |
| UI | Pilot `#/jobs`, toggle « Mode agentique » |
| Env | `LBG_JOBS_*` dans `lbg.env.example` |

**Statut** : code mergé ; smoke LAN et parcours opérateur réels à valider sur 140.

---

### D. MMO / Core3 — hors scope Claude 140 phase 1

| Track | Sujet | Statut | Où |
|-------|-------|--------|-----|
| World Director | Lia gameplay (forage→craft→vente→quête) | 🟡 En cours | VM 246 |
| World Director | economy_director, world_chronicler, Jax, Lost Heaven | ✅ Fait (28 juin) | |
| Core3 Prime | Systèmes monde (quêtes, économie, factions) | Plan mai 2026 | `docs/core3_prime_world_systems.md` |
| Client SWG | Launchpad dual PreCU/Prime, deploy nouveau PC | ✅ P0–P3 faits | `docs/client_dual_launchpad.md` |
| new_mmo | Client Godot Prime (Lost Heaven, handshake SOE) | Actif sur `main` | Dépôt séparé `~/projects/new_mmo` |
| Sandbox Python | `mmmorpg_server` WS `:7733` | ❌ Décommissionné | ADR 0012 |

**Règle** : Claude 140 ne touche **pas** 245/246 sauf demande explicite opérateur.

---

### E. Étoile du nord produit (ordre exécutoire)

1. **Assistant poste/infra** (desktop, mail, web, jobs) — rang 1
2. **Persona MMO / pont Core3** — rang 2
3. **Évolution monde par l'IA** — rang 3 (secondaire tant que rang 1 pas fiable)

Réf. : `docs/plan_de_route.md` § *Étoile du nord*

---

## 4. État Git (au moment de la passation)

**Branche** : `feature/antigravity-tasks`

**Commits récents**

- `docs(claude)` : prompt opérateur non-MMO VM 140
- `docs(adr)` : Claude Code vs Hermes/OpenClaw
- `feat(infra)` : `verify_claude_alignment`
- `chore(pilot)` : republier build `pilot_shell` v2

---

## 5. Démarrage session Claude 140

### Étape 0 — Lire (ordre obligatoire)

1. `/opt/LBG_IA_MMO/CLAUDE.md`
2. `docs/adr/0013-claude-code-vs-hermes-openclaw.md`
3. `docs/fusion_env_lan.md`
4. `docs/plan_de_route.md` (historique juillet 2026)
5. `docs/handoff_windows_vers_vm140.md`
6. **Ce fichier** (`docs/passation_claude_140_20260707.md`)

### Étape 1 — Inventaire prod locale

```bash
systemctl is-active lbg-backend lbg-orchestrator lbg-agent-pm
curl -s http://127.0.0.1:8000/healthz
curl -s http://127.0.0.1:8010/healthz
curl -s http://127.0.0.1:8055/healthz
df -h / && free -h
```

### Étape 2 — Trois tâches non-MMO suggérées (attendre choix opérateur)

| # | Tâche | Fichiers |
|---|-------|----------|
| 1 | Finaliser bootstrap Claude 140 + `verify_claude_alignment.sh` | `infra/scripts/bootstrap_claude_on_core140.sh` |
| 2 | Polish `pilot_shell` : streaming chat, outils PM visibles | `pilot_shell/src/agent/`, `useAgentChat.ts` |
| 3 | Stabiliser deploy `dev_pilot_workflow.sh --full` + smoke LAN | `infra/scripts/smoke_vm_lan.sh` |

### Règles de cohabitation

| Autorisé | Interdit |
|----------|----------|
| Éditer code sous `/opt/LBG_IA_MMO` | Deuxième stack FastAPI sur `:8000` |
| `npm run build` dans `pilot_shell/` | `npm run dev` permanent sur 140 |
| `systemctl restart lbg-*` **après accord** | Deploy 245/246, reset MMO, Core3 |
| Tests `curl`, `journalctl`, lectures SSH 110 | Commiter `infra/secrets/lbg.env` |

---

## 6. Lancer Claude 140

**Session interactive** (recommandé — `gemma4-claude` est lent en mode `-p`) :

```bash
ssh lbg@192.168.0.140
lbg-tmux
claude-lbg
```

**Variante courte** (à coller après ouverture) :

```
Lis CLAUDE.md, docs/adr/0013-claude-code-vs-hermes-openclaw.md, docs/fusion_env_lan.md § topologie et docs/passation_claude_140_20260707.md. Scope non-MMO uniquement. Inventorie l'état prod locale (healthz, systemd), propose les 3 prochaines tâches prioritaires pilot_shell/backend/infra, et attends mon choix avant toute modification ou restart.
```

**Injection depuis WSL** :

```bash
cd ~/projects/LBG_IA_MMORPG/LBG_IA_MMO
bash infra/scripts/claude_140_inject_context.sh
```

Prompt complet : `docs/prompt_claude_140_non_mmo.txt`

---

## 7. Fichiers de référence

| Besoin | Fichier |
|--------|---------|
| Topologie complète | `docs/fusion_env_lan.md` |
| Compte SSH / PuTTY | `docs/ops_vm_user.md` |
| Handoff Windows→140 | `docs/handoff_windows_vers_vm140.md` |
| Prompt non-MMO | `docs/prompt_claude_140_non_mmo.md` |
| UI pilot_shell | `docs/ui_refactor_plan.md` |
| Desktop Windows (hors 140) | `docs/desktop_hybride.md` |
| Décision Claude vs Hermes | `docs/adr/0013-claude-code-vs-hermes-openclaw.md` |

---

*Généré pour le poste Claude Code sur lbg-backend — juillet 2026.*
