# Contenu Core3 — Serveur Prime

Catalogues data-driven consommés par `lua/ia_bridge_screenplay.lua` au boot.

## Fichiers

| Fichier | Lot plan | Rôle |
|---------|----------|------|
| `core3_npc_catalog.json` | 0 | PNJ, rosters, `game_time`, remplacements vanilla |
| `core3_npc_pilots.json` | 0 | Liste plate pilotes (legacy / sidecar) |
| `core3_quest_templates.json` | 0 | Quêtes MVP (livraison, réparation, enquête) |
| `core3_economy.json` | 0 | Marchands + chaîne craft |
| `core3_factions.json` | 3 | Factions, langues, réputation |
| `core3_planet_rules.json` | 4 | Règles par zone (tatooine actif) |
| `core3_npc_simulation.json` | 2 | 3 niveaux simulation PNJ |
| `world_poi/tatooine.json` | 1 | POI monde staff (centre ME) — voir `docs/world_editor_plan.md` |
| `core3_artisan_dispenser.json` | — | Hub artisan Mod+ (outils, stations) |
| `core3_resource_samples.json` | — | Ressources craft hub artisan |
| `lia_perform_catalog.json` | — | Gestes Lia (orchestrateur) |
| `lua/lbg_artisan_hub_screenplay.lua` | — | Distributeur artisan |
| `lua/ia_bridge_screenplay.lua` | — | Screenplay runtime Prime |

## Éditeur monde (planifié)

Placement in-game Dev+ (PNJ + POI centre ME) → export auto repo : [`docs/world_editor_plan.md`](../docs/world_editor_plan.md), ADR [`0008-world-editor-world-poi.md`](../docs/adr/0008-world-editor-world-poi.md).

## Déploiement VM

```bash
bash infra/scripts/deploy_core3_ia_bridge_vm.sh --restart
```

Chemins runtime sur VM :

- `/opt/LBG_IA_MMO/content/core3/*.json`
- `/opt/lbg-new-mmo-clean/MMOCoreORB/bin/ia_bridge/`
- Screenplay : `.../bin/scripts/custom_scripts/screenplays/ia_bridge_screenplay.lua`

## Documentation

- [`docs/core3_prime_world_systems.md`](../docs/core3_prime_world_systems.md)
- [`docs/core3_prime_runbook.md`](../docs/core3_prime_runbook.md)
