# C.4 — Roster instructeur Entertainer (triplon)

**Roster** : `roster:mos_entertainer_trainer`  
**Politique** : `exactly_one` au poste instructeur (centre ME).  
**Lifecycle** : `game_time_triplet` (voir [C.4b](core3_ia_phase_c4b_game_time.md)).

## Pilotes

| `pilot_id` | Nom IG | `shift_offset` | `lbg_npc_id` (legacy) |
|------------|--------|----------------|------------------------|
| `npc:core3_bige_coto` | Bige Coto | 0 | `npc:entertainer_trainer_mos` |
| `npc:core3_lyra_velo` | Lyra Velo | 1 | `npc:entertainer_trainer_relief` |
| `npc:core3_talen_ress` | Talen Ress | 2 | `npc:entertainer_trainer_relief2` |

## Poste travail (phase `work`)

| Champ | Valeur |
|-------|--------|
| cell | `1189634` |
| x / y / z | `0.18` / `-1.49` / `1.13` |
| heading | `348.38` |

Centre d’entraînement Mos Eisley — même cell que recon World Editor 2026-05-29.

## Loisir / show (phase `leisure`)

Présence **`cantina`** (danse IA) sur la **scène du théâtre**, pas la mezzanine vanilla.

| Champ | Valeur (dump Teome 2026-06-01) |
|-------|--------------------------------|
| cell | **`1105851`** (scène) |
| x / y / z | `0.34` / `51.19` / `2.13` |
| heading | `173.9` |

Chaque pilote a un léger décalage sur la scène + `leisure_patrol` (3 waypoints, `leisure_contain_m: 10`).

**Ne pas utiliser** `1105853` pour le show LBG — c’est la mezzanine (`theater_manager`).

## Repos (phase `rest`)

`rest_home` sur `binding.home` (même cell/scène que loisir). Le poste instructeur reste couvert par un autre membre du triplon en `work`.

## Cellules cantina (rappel global)

| Cell | Usage |
|------|--------|
| `1082877` | Bar cantina |
| `1105851` | Scène théâtre (entertainers loisir) |
| `1105853` | Mezzanine vanilla |

## Forcer reposition runtime

```text
/ia reset_pilot npc:core3_bige_coto
```

Ou World Editor : `lbg_we npc remove` → `dump` sur scène → `npc place` → `export` → deploy.

## Smoke

```bash
bash infra/scripts/smoke_core3_ia_phase_c4_entertainer_roster_lan.sh
```

## Déploiement

```bash
bash infra/scripts/deploy_core3_ia_bridge_vm.sh --restart
```
