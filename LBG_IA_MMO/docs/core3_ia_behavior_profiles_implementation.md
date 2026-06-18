# Plan d’implémentation — profils comportementaux & population vivante

**Objectif** : un moteur unique (profils + scènes) pour joueurs IA et PNJ pilotes, extensible à N personnages.

## Phases

| # | Lot | Livrables | Dépendances |
|---|-----|-----------|-------------|
| 1 | **Profils partagés** | `core3_behavior_profiles.json`, `core3_behavior_profiles.py` | — |
| 2 | **Refactor prompts** | `core3_player_autonomy.py`, `lia_orchestrator.py` lisent les profils | 1 |
| 3 | **Registre joueurs** | `behavior_profile_id` sur Lia/Nix ; brouillon `mira` (`enabled: false`) | 1 |
| 4 | **Actions Lua PNJ** | `npc_perform`, `npc_path`, `vendor_sell` dans `ia_bridge_screenplay.lua` | — |
| 5 | **Sidecar** | `normalize_npc_action`, prompts LLM PNJ, `vendor_buy`/`vendor_sell` joueurs | 4 |
| 6 | **Autonomie population** | `core3_population_autonomy.py` + `core3_npc_autonomy.py` ; service systemd | 1–5 |
| 7 | **PNJ cantina** | Profil barman → `profile:cantina_vendor_v1` + autonomie Jax | 1, 4, 6 |

## Architecture cible

```
core3_behavior_profiles.json
        │
        ├── joueurs (core3_ia_players.json → behavior_profile_id)
        │     └── core3_player_autonomy / lia_orchestrator
        │
        └── PNJ (core3_npc_catalog.json → behavior_profile_id)
              └── core3_npc_autonomy → POST /v1/npc-think
                    └── pending.jsonl → npc_say | npc_perform | npc_path | vendor_sell
```

## Hors scope immédiat

- Bazar listing complet (vendre au marché SWG vanilla)
- Radials trade/groupe/duel natifs
- Activation du perso `mira` (compte Core3 à créer)

## Déploiement Prime (246)

```bash
bash infra/scripts/deploy_core3_ia_bridge_vm.sh --restart
bash infra/scripts/install_core3_ia_player_vm.sh mira
# Apres creation perso Mira Bot en jeu :
bash infra/scripts/sync_ia_player_oid_vm.sh mira
ssh lbg@192.168.0.246 'sudo systemctl enable --now lbg-core3-ia-player@mira.service'
```
