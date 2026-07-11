# Audit réunification projet LBG — juillet 2026

**Date** : 2026-07-11  
**Objectif** : réunifier les fils de conversation parallèles sous la supervision **orchestrateur 140 + équipe virtuelle**.

---

## Cible produit (validée)

| Couche | Cible | VM / artefact |
|--------|--------|----------------|
| **Serveur jeu** | Core3 Prime | **246** — sidecar IA `:8791` |
| **Joueurs IA** | Lia, Nix, Mira, Kael… | **246** (comptes dédiés) |
| **Client** | **Godot LBG** (dégel juillet 2026) + SWGEmu launchpad en parallèle | `lbg_client_godot/` |
| **Studio IA** | Équipe virtuelle + Assistant | **140** orchestrateur, **110** Pilot |
| **Legacy** | Bac à sable Python WS | **245** — **gelé** (ADR sandbox) |

### Dégel Godot

Le client Godot phase 0 n’est plus considéré comme abandonné : conversations parallèles (Infographiste IA, pipeline `.glb`, drone steampunk) en font une **cible client active**, coexistante avec SWGEmu le temps de la transition.  
Le bac à sable **Python** (`mmmorpg_server`, `web_client`) reste gelé — voir [`ARCHIVED_mmmorpg_sandbox.md`](ARCHIVED_mmmorpg_sandbox.md) (amendement Godot ci-dessous).

---

## Équipe virtuelle — alias personas

Les rôles techniques gardent leur id (`ops`, `qa`…) ; l’UI et `/v1/team/meta` exposent des **alias** personnalisables (`LBG_TEAM_ROLE_ALIASES_JSON`) :

| Rôle | Alias défaut | Mission |
|------|--------------|---------|
| `ops` | **Héphaïstos** | Infra, Proxmox, stockage |
| `qa` | **Argus** | Smokes, qualité LAN |
| `pm` | **Thémis** | Roadmap, réunification sous-projets |
| `dev_game` | **Dédale** | Gameplay Core3, Godot, forge OpenGame |
| `player_ia` | **Chœur du monde** | Joueurs IA Prime 246 |

---

## Sous-projets supervisés

Registre machine : `orchestrator/team/subprojects.py` — exposé via `GET /v1/team/meta`.

| Id | Label | Rôle owner | Statut |
|----|-------|------------|--------|
| `core3_prime` | Core3 Prime 246 | player_ia | prod |
| `client_godot` | Client Godot | dev_game | **actif** |
| `client_swgemu` | SWGEmu launchpad | dev_game | prod parallèle |
| `equipe_virtuelle` | Méta-orchestrateur | pm | actif |
| `assistant_pilot` | Assistant + Pilot | pm | actif |
| `infra_ops` | Infra LAN | ops | actif |
| `infographiste_ia` | Assets 3D (Pygmalion) | dev_game | **en_cours** |
| `sandbox_python` | MMO Python 245 | qa | gelé |

---

## Fils de conversation Cursor (repères)

| Sujet | Transcript / thème | Rôle équipe |
|-------|-------------------|-------------|
| Équipe virtuelle phases A–D | `f7dd94d7-…` | pm + tous |
| Godot / Infographiste 3D | `053aacd8-…` | dev_game |
| Core3 / Prime / bots | runbooks + sidecar | player_ia |

**Action** : le rôle **pm (Thémis)** + endpoint `/v1/team/meta` servent de **tableau de bord** ; les playbooks L1 (smoke, ops, player_ia) automatisent la supervision.

---

## Phase D — think/tick (L2)

- Sonde L1 : `player_ia` mode probe (défaut)
- **Think/tick** : `player_ia_mode=think_tick` ou objectif contenant *think/tick/autonomie* → **L2 obligatoire** (`LBG_TEAM_PLAYER_IA_THINK_REQUIRES_APPROVAL=1`)
- Exécution : `player_autonomy_tick` via `lbg_agents.core3_player_autonomy`

---

## Prochaines étapes

1. [x] Alias rôles + `/v1/team/meta`
2. [x] Think/tick L2 via équipe
3. [x] PM périodique : brief réunification (tâche `pm` + timer `lbg-team-pm-reunification-job`)
4. [x] Promotion prototype → Core3 — [`runbook_promotion_prototype_core3.md`](runbook_promotion_prototype_core3.md)
5. [x] Godot jalon M1 : miroir sidecar 246 — [`jalon_client_godot_sidecar_246.md`](jalon_client_godot_sidecar_246.md)
6. [ ] Godot M3/M5 : SOE live + `lbg-ws/2` C++ (client autoritaire) — **équipe autonome** [`jalon_godot_client_live_team.md`](jalon_godot_client_live_team.md)
7. [x] Équipe autonome Godot — superviseur 6h + followups — [`equipe_autonome_godot.md`](equipe_autonome_godot.md)
8. [x] Infographiste IA intégré — piste dev_game Pygmalion + timer 12h — [`jalon_infographiste_ia.md`](jalon_infographiste_ia.md)

---

*Références : `architecture_equipe_virtuelle_studio.md`, `handoff_equipe_virtuelle_2026-07-10.md`, `plan_de_route.md`*
