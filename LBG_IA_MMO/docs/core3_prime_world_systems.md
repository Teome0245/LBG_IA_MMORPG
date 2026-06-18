# Serveur Prime — systèmes monde (Core3)

Documentation des briques implémentées pour le plan « Prime Core3 » (Tatooine MVP).

## Fichiers data (`content/core3/`)

| Fichier | Rôle |
|---------|------|
| `core3_npc_catalog.json` | PNJ, rosters, cycle travail/repos/loisir |
| `core3_quest_templates.json` | 3 quêtes types (livraison, réparation, enquête) |
| `core3_economy.json` | 2 marchands pilotes + chaîne craft |
| `core3_factions.json` | 3 factions + langues + réputation |
| `core3_planet_rules.json` | Règles planètes (tatooine actif, dantooine / terre-plate planifiés) |
| `core3_npc_simulation.json` | 3 niveaux de simulation (actif / semi / passif) |

## Screenplay Lua

[`content/core3/lua/ia_bridge_screenplay.lua`](../content/core3/lua/ia_bridge_screenplay.lua) :

- Charge les JSON au boot (fallback hardcodé si absent).
- **GameTime** : `iaConfigureGameTime` / `iaGetGameTime` (C++, `DirectorManager`).
- **EventBus** : `iaPublishWorldEvent` + `events.jsonl` local.
- **Quêtes** : `offer_quest`, `quest_accept`, `quest_turnin` via `interact`.
- **Économie** : `vendor_buy|<pilot>|tatooine|0|0|0|<joueur>|<index>`.
- **Craft** : `craft_combine|Lia|tatooine|0|0|0|craft:mos_ration_pack`.
- **Housing MVP** : `housing_enter|Lia|tatooine|0|0|0|`.
- **PNJ passifs** : tick toutes les ~15 min → `ia_bridge/npc_passive_state.json`.

## C++ (`new_mmo/lbg-mmo/server-core3`)

`DirectorManager` : `iaConfigureGameTime`, `iaGetGameTime`, `iaGetDayPhase`, `iaPublishWorldEvent`, `iaPollWorldEvent`.

**Rebuild requis** après modification C++ :

```bash
bash LBG_IA_MMO/infra/scripts/build_core3_antigravity_vm.sh --sync
bash LBG_IA_MMO/infra/scripts/install_core3_clean_after_vm_build.sh
```

## Déploiement et validation

Runbook complet : [`core3_prime_runbook.md`](core3_prime_runbook.md)

```bash
bash LBG_IA_MMO/infra/scripts/deploy_core3_ia_bridge_vm.sh --restart
bash LBG_IA_MMO/infra/scripts/smoke_core3_prime_world_lan.sh --demo-pending
```

## Études

- Housing / nage / vol : [`core3_housing_swim_flight_study.md`](core3_housing_swim_flight_study.md)
