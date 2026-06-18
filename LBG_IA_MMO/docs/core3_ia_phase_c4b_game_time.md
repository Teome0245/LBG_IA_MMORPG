# C.4b — Moteur temps jeu (travail / repos / loisir) + triplon

**Statut** : implémenté (Lua + catalogue).  
**Prérequis** : [C.4 roster entertainer](core3_ia_phase_c4_entertainer_roster.md).

## Règles temps

| Paramètre | Valeur |
|-----------|--------|
| `real_hours_per_game_day` | 6 |
| `game_days_per_real_day` | 4 |
| Phases | 2 h réelles chacune : **work**, **rest**, **leisure** |

`getLifecyclePhase(shift_offset)` dans `ia_bridge_screenplay.lua` (basé sur `os.time()` UTC).  
Config : `content/core3/core3_planet_rules.json` → `game_time`.

## Triplon entertainer (`roster:mos_entertainer_trainer`)

| Pilote | `shift_offset` | Phase **work** | Phase **leisure** | Phase **rest** |
|--------|----------------|----------------|-------------------|----------------|
| `npc:core3_bige_coto` | 0 | Poste ME `1189634` | Show scène `1105851` | `rest_home` (scène) |
| `npc:core3_lyra_velo` | 1 | idem | idem (offset scène) | idem |
| `npc:core3_talen_ress` | 2 | idem | idem | idem |

### Présence par phase (`getRosterDesiredPresence`)

| Phase | Comportement |
|-------|----------------|
| **work** | `post` — instructeur statique au centre ME |
| **rest** | `rest_home` — linger sur `home` (scène théâtre si défini) |
| **leisure** | `cantina` si `binding.cantina` ; sinon `walk_patrol` sur `leisure_patrol` |

Couverture : un triplon en **work** par bloc de 2 h → poste couvert sur **6 h réelles** (1 jour IG).

### Patrouille intérieur (2026-06-01)

- Points `leisure_patrol` avec **`cell`** explicite (`1105851`).
- `assignRoamWalkPoint` passe la cellule à `setNextPosition`.
- `home_cell` chargé depuis `binding.home.cell` (téléport loisir/repos).

## Triplon barman (`roster:mos_eisley_cantina_barman`)

| Pilote | Rôle |
|--------|------|
| `npc:core3_barman_jax` | Jax Moro |
| `npc:core3_barman_sira` | Sira |
| `npc:core3_barman_torrik` | Torrik Fenn |

Poste bar : cell `1082877`, **y = 1.15** (bord client du comptoir).  
`peaceful_static` — conversation possible face au bar (évite spawn « derrière le bar » à y=2.8).

Shop : `shop:mos_cantina_bar` — voir `core3_economy.json`.

## Déploiement

```bash
bash infra/scripts/deploy_core3_ia_bridge_vm.sh --restart
```

## Smoke

```bash
bash infra/scripts/smoke_core3_ia_phase_c4b_game_time_lan.sh
bash infra/scripts/smoke_core3_ia_phase_c4_entertainer_roster_lan.sh
```

## Suite

- **C.5** — donneur de quête (`shift_offset` + poste).
- Barman : `vendor_sell`, quêtes journal (`quest:mos_gather_bar_*`).
