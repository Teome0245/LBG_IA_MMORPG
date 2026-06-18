# Plan d'intégration — World Director + SysOps + Économie + Vie du monde

**Statut** : en cours (Phase 1.1 + 2.1–2.2 livrées 2026-06-04)  
**Date** : 2026-06-11  
**Périmètre** : infra Proxmox/LAN + fork SWGEmu (Prime 246, PreCU 245) + monde simulé (PNJ, économie, joueurs IA)

---

## 1. Vision produit

Un écosystème d'agents **local et open source** qui :

1. **Surveille et répare** l'infra (Proxmox, VMs, Core3, MariaDB, services systemd).
2. **Joue et progresse** via des personnages IA headless (Lia, Nix, Mira…).
3. **Anime le monde** (PNJ, économie, quêtes, factions) sans brûler le GPU en LLM par PNJ.

**Étoile du nord** (alignée `plan_de_route.md` rang 2–3) : même famille cognitive **assistant local** + **persona MMO**, avec séparation stricte réflexion / exécution (ADR 0004).

---

## 2. Ce qui existe déjà (ne pas reconstruire)

| Brique | État | Fichiers / services |
|--------|------|---------------------|
| Orchestrateur + planner ReAct | Actif | `orchestrator/`, `:8010` VM 140 |
| Jobs agentiques arrière-plan | Partiel | `router/agentic.py`, `LBG_CHAT_AGENTIC` |
| DevOps / selfcheck / SSH allowlist | Actif (SSH off par défaut) | `devops_executor.py`, `ssh_client.py` |
| Sonde mémoire VMs | Actif | `vm_memory_probe.py`, `watch_vm_memory_health.sh` |
| Pont Core3 IA (joueurs + PNJ) | Actif | sidecar `:8791` VM 246, `ia_bridge_screenplay.lua` |
| Joueurs IA (Lia, Nix, Mira brouillon) | Actif / en cours | `core3_ia_players.json`, autonomie population |
| Profils comportement partagés | Nouveau | `core3_behavior_profiles.json` |
| Simulation PNJ 3 niveaux | Défini | `core3_npc_simulation.json` (actif / semi / passif) |
| Économie data-driven MVP | Défini | `core3_economy.json`, `vendor_buy` / `vendor_sell` Lua |
| Catalogue PNJ + rosters | Actif | `core3_npc_catalog.json` |
| Ollama local | Actif | VM 110 `gemma4:e2b` |
| Topologie LAN | Validée | 140 core, 110 LLM/front, 245 PreCU+DB, 246 Prime+IA |

---

## 3. Architecture cible — Superviseur + spécialistes

```
                    ┌─────────────────────────────────────┐
                    │   WORLD DIRECTOR (superviseur)      │
                    │   Orchestrateur 140 + planner       │
                    │   Modèle : Ollama 110 / API lourd   │
                    └─────────────────┬───────────────────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        ▼                             ▼                             ▼
 ┌──────────────┐            ┌──────────────┐            ┌──────────────────┐
 │ AGENT SYSOPS │            │AGENT ÉCONOMIE│            │ AGENT CHRONIQUE  │
 │ infra/ops    │            │ marché/stocks│            │ vie PNJ/factions │
 └──────┬───────┘            └──────┬───────┘            └────────┬─────────┘
        │                           │                              │
        ▼                           ▼                              ▼
   MCP Proxmox                 MCP SQL + JSON              MCP Core3 + profils
   MCP SSH LAN                  lecture/écriture bornée      enqueue / npc_think
   MCP systemd/logs             règles macro (pas LLM/PJ)   scènes + GOAP lite
        │                           │                              │
        └───────────────────────────┴──────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
            Couche exécution                  Couche sandbox
         (jobs persistants 140)          (Docker / VM dédiée dev)
         Open Interpreter REPL              OpenHands workspace
```

### Règles d'or

| Règle | Pourquoi |
|-------|----------|
| **Le LLM ne pilote pas chaque PNJ** | Coût + latence ; il fixe des **objectifs de faction/roster** |
| **Scripts/Lua/GOAP exécutent** | Danse, spawn, prix, pathing = déterministe |
| **SysOps n'écrit pas le lore** | Capability séparée, allowlist stricte |
| **Tout infra sensible → job + approbation** | `restart Prime`, `systemctl`, SQL write |
| **Contexte massif filtré en local** | MCP/scripts résument logs et tables avant le LLM |

---

## 4. Couche « Cowork local » (mix Open Interpreter + OpenHands)

| Mode | Outil | Usage LBG |
|------|-------|-----------|
| REPL interactif | Open Interpreter CLI | Proto scripts, tri logs, debug one-shot |
| Sandbox repo | Docker + volume `/workspace` | Refactor agents, tests, sans toucher l'hôte |
| Tâches longues | Jobs orchestrateur existants | Deploy 246, boucle smoke Lia, remediation |
| Outils stables | Serveurs **MCP** | Proxmox, SSH, Core3, git, SQL read-only |

**Inférence** : Ollama 110 par défaut ; Groq/API pour plans World Director complexes.

---

## 5. Les quatre agents métier

### 5.1 World Director (superviseur)

- **Rôle** : objectifs macro, priorisation, délégation, synthèse.
- **Implémentation** : extension du `planner.py` + registry capabilities (pas un 2ᵉ orchestrateur).
- **Entrées** : alertes SysOps, KPI économie, événements monde (`events.jsonl`), état joueurs IA.
- **Sorties** : plans multi-étapes (`devops_probe` → `core3_bot_action` → `npc_dialogue`), jobs agentiques.

### 5.2 Agent SysOps

- **Mission** : santé Proxmox + VMs + Core3 + MariaDB + systemd + disque/RAM.
- **Autonomie** : boucle 5 min (déjà `lbg-core3-ia-bots-ensure.timer`, `vm_memory_watchdog`) ; escalade si seuil dépassé.
- **Outils MCP cibles** :
  - `get_vm_status(node, vmid)`
  - `get_vm_metrics(cpu, mem, disk)`
  - `get_service_status(host, unit)` via `ssh_run` allowlisté
  - `get_server_logs(host, unit, tail)`
  - `restart_service(host, unit)` — **approbation obligatoire**
- **Premier livrable** : script Python `tools/mcp_proxmox_server/` (voir phase 2).

### 5.3 Agent Économie

- **Mission** : régulateur macro — stocks bazar, prix, rareté ressources, quêtes d'injection.
- **Données** : `core3_economy.json`, tables SWG (vendor, resources) en **lecture** ; écritures via actions jeu (`vendor_sell`, quêtes, spawn récolteurs) pas SQL brut sauf sandbox.
- **Décisions types** :
  - « Acier rare → quête `mos_gather_*` + bump stock PNJ forager »
  - « Inflation cantina → baisser prix `shop:mos_cantina_bar` »
- **Pas de LLM par transaction** : règles + LLM pour arbitrage hebdo.

### 5.4 Agent Chroniqueur (vie du monde)

- **Mission** : objectifs de **factions / rosters / joueurs IA**, pas micro-PNJ.
- **Pont existant** : `core3_behavior_profiles.json`, `core3_npc_autonomy.py`, `npc_think`, screenplay Lua (`npc_perform`, `npc_path`, routines roster).
- **Niveaux simulation** (`core3_npc_simulation.json`) :
  - **Actif** (≤12) : LLM + scènes profil (Jax, instructeur artisan)
  - **Semi-actif** (≤30) : routines scriptées
  - **Passif** (200 virtuel) : stats naissance/mort/métier
- **GOAP lite** : objectifs JSON par faction → traduits en `pending.jsonl` par worker Python (phase 5).

### 5.5 Agent Joueurs IA (sous-ensemble Chroniqueur)

- Lia / Nix / Mira : **citoyens jouables** via `core3_ia_players.json`.
- Reconnexion auto, progression métier, commerce débutant — déjà amorcé.
- World Director peut leur assigner des **missions macro** (« Lia : stabiliser commerce cantina cette semaine »).

---

## 6. Topologie LAN (rappel)

| IP | Rôle | Agents qui y touchent |
|----|------|------------------------|
| **140** | Orchestrateur, jobs, MCP hub | World Director, workers |
| **110** | Ollama, front | Inférence |
| **245** | PreCU, MariaDB, mmo_server | Économie (SQL), backups |
| **246** | Prime, sidecar, bots, PNJ | Chroniqueur, joueurs IA, SysOps cible |

---

## 7. Plan d'exécution par phases

### Phase 0 — Cadrage (0,5 j) ✅ ce document

- [x] Plan fusionné Cowork local + World Director
- [x] Validation priorités avec opérateur

### Phase 1 — Fondations MCP + jobs (semaine 1)

| # | Livrable | Détail |
|---|----------|--------|
| 1.1 | `mcp-lbg-core3` | ✅ `tools/mcp_lbg_core3_server/` — health, snapshots, events (read-only) |
| 1.2 | `mcp-lbg-ssh` | ✅ `tools/mcp_lbg_ssh_server/` — ssh_run allowlist (systemctl, free, uptime) |
| 1.3 | Enregistrement Cursor + orchestrateur | descriptors MCP |
| 1.4 | Job runner durci | persistance état, logs structurés |

### Phase 2 — Agent SysOps + Proxmox (semaine 2)

| # | Livrable | Détail |
|---|----------|--------|
| 2.1 | **`tools/mcp_proxmox_server/`** | ✅ Python MCP : `proxmox_cluster_status`, `proxmox_list_vms`, `proxmox_vm_status`, `proxmox_lan_vms` |
| 2.2 | Capability `devops_probe` étendue | ✅ kind `proxmox_status` + planner ; `vm_memory_probe` (existe) |
| 2.3 | Timer `lbg-infra-watchdog` | ✅ light sur **140** (Proxmox + 140/245/110) ; Prime exclu (`EXCLUDE_PRIME=1`) — complet après rebuild |
| 2.4 | Playbook remediation | RAM Prime > seuil → log + option restart (approbation) |
| 2.5 | Open Interpreter sandbox | conteneur dev, volume repo, Ollama 110 |

**Script SysOps minimal (spec)** :

```python
# tools/mcp_proxmox_server/server.py — fonctions MCP
get_cluster_status() -> dict
get_vm_status(vmid: int) -> dict  # cpu, mem, disk, state
get_vm_config(vmid: int) -> dict
# PAS de start/stop VM sans capability séparée + approbation
```

Secrets : `PROXMOX_HOST`, `PROXMOX_TOKEN` dans `lbg.env` (jamais versionnés).

### Phase 3 — Consolidation MMO joueurs IA (semaine 2–3)

| # | Livrable | Détail |
|---|----------|--------|
| 3.1 | Mira : perso + OID + service `@mira` | `sync_ia_player_oid_vm.sh` |
| 3.2 | Barman Jax + artisan trainer online | spawn intérieur ME/cantina |
| 3.3 | `vendor_sell` + économie MVP validée en jeu | |
| 3.4 | Population autonomie stable | Lia + Nix + PNJ pilotes |

### Phase 4 — Agent Économie (semaine 3–4)

| # | Livrable | Détail |
|---|----------|--------|
| 4.1 | **`agents/src/lbg_agents/economy_director.py`** | lecture `core3_economy.json` + snapshots |
| 4.2 | **`mcp-lbg-sql`** | requêtes read-only allowlistées (stocks, bazaar) |
| 4.3 | Capability `economy_regulate` | registry orchestrateur |
| 4.4 | Règles v1 | 5 seuils (rareté, inflation, stock vide…) → actions JSON |
| 4.5 | Job quotidien | tick économie → enqueue quêtes / ajuster prix JSON |

**Modèle décision (spec)** :

```json
{
  "signal": "resource_scarcity",
  "resource": "foraged_fruit_s1",
  "action": "offer_quest",
  "quest_id": "mos_gather_bar_fruit",
  "giver_pilot_id": "npc:core3_barman_jax"
}
```

### Phase 5 — Agent Chroniqueur + factions (semaine 4–6)

| # | Livrable | Détail |
|---|----------|--------|
| 5.1 | **`content/world/faction_goals.json`** | objectifs par faction/zone |
| 5.2 | **`agents/src/lbg_agents/world_chronicler.py`** | tick → objectifs roster → scènes profil |
| 5.3 | Capability `world_direct` | orchestrateur |
| 5.4 | Passage semi-actif/passif | tick 20s / 900s selon `core3_npc_simulation.json` |
| 5.5 | LangGraph optionnel | boucles état faction si planner linéaire insuffisant |

### Phase 6 — World Director unifié (semaine 6–8)

| # | Livrable | Détail |
|---|----------|--------|
| 6.1 | Planner multi-capability | enchaînement SysOps → Économie → Chroniqueur |
| 6.2 | Dashboard Pilot | pastilles infra + monde + bots |
| 6.3 | OpenHands Docker CI | refactor sécurisé sur repo |
| 6.4 | Doc opérateur | runbooks alertes |

---

## 8. Matrice capabilities orchestrateur (cible)

| Capability | Agent | Mode | Approbation |
|------------|-------|------|-------------|
| `devops_probe` | SysOps | read + job | non (read) |
| `proxmox_status` | SysOps | read | non |
| `ssh_run` | SysOps | exec allowlist | oui si write |
| `remediation_apply` | SysOps | exec | oui |
| `core3_bot_action` | Joueurs IA | jeu | non (borné) |
| `economy_regulate` | Économie | macro | oui si SQL write |
| `world_direct` | Chroniqueur | monde | non (enqueue borné) |
| `npc_dialogue` | PNJ actifs | LLM | non |
| `project_pm` | Meta | planning | selon action |

---

## 9. Sécurité et coûts

- **Proxmox** : token read-only pour sonde ; token write séparé + jamais dans Interpreter nu.
- **MariaDB** : économie en read-only MCP ; mutations via gameplay bridge.
- **Prime** : pas de `systemctl` libre depuis LLM — scripts `infra/scripts/` uniquement.
- **Tokens** : résumés locaux (MCP) avant LLM ; PNJ passifs sans LLM.
- **Isolation** : Interpreter/OpenHands dans conteneur ; agents prod sur 140.

---

## 10. Critères de succès (MVP intégré)

1. **SysOps** : alerte automatique si VM 246 RAM > seuil + lien Proxmox visible dans Pilot.
2. **Joueurs IA** : Lia + Nix + Nix online > 95 %/semaine sans intervention manuelle.
3. **Économie** : 1 régulation automatique/semaine visible en jeu (quête ou prix).
4. **Chroniqueur** : barman + 1 instructeur artisan avec scènes profil autonomes.
5. **World Director** : 1 plan multi-étapes réussi (« sonde infra → reconnect bots → tick cantina »).

---

## 11. Prochaine action (après validation du plan)

**Ordre d'exécution recommandé** :

1. **Phase 2.1** — script MCP Proxmox (`tools/mcp_proxmox_server/`)
2. **Phase 1.1** — MCP Core3 (sidecar)
3. **Phase 3** — finaliser Mira + Jax cantina (déjà amorcé)
4. **Phase 4.1** — `economy_director.py` squelette

Ne pas démarrer LangGraph avant phases 1–3 stables.

---

## Références

- `docs/plan_de_route.md` — étoile du nord, jobs agentiques
- `docs/plan_mmorpg.md` — PNJ vivants, GOAP
- `docs/core3_ia_behavior_profiles_implementation.md` — profils partagés
- `docs/core3_ia_phase_g_ai_players_population.md` — joueurs IA
- `orchestrator/README.md` — capabilities actuelles
