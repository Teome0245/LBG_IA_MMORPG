# C.5 — Donneur de quête (triplon Mos Eisley)

**Statut** : déployé (2026-05-24).  
**Poste** : informant outdoor vanilla ~`3488, -4782` (Tatooine Mos Eisley).

## Roster

| Slot | `pilot_id` | Nom IG | `shift_offset` |
|------|------------|--------|----------------|
| 0 | `npc:core3_vex_sorn` | Vex Sorn | 0 |
| 1 | `npc:core3_nira_kell` | Nira Kell | 1 |
| 2 | `npc:core3_daan_oth` | Daan Oth | 2 |

- `roster_id` : `roster:mos_eisley_quest_giver`
- `service_policy` : `exactly_one`
- Cycle : même moteur **game_time** que C.4b (2 h travail / repos / loisir)
- **Travail** : poste informant (`post`)
- **Repos** : despawn (`off`)
- **Loisir** : `walk_patrol` (jalons courts)

## Actions pont

| Action | Effet |
|--------|--------|
| `npc_say` | Spatial chat |
| `offer_quest` | Spatial chat + log `offer_quest stub` (pas encore journal quête SWG) |
| `noop` | Silence |

Profils : `profile:quest_giver_mos_v1` (+ relief v1 / relief2).  
Hook catalogue : `quest:mos_eisley_intro_stub`.

## Vanilla

Ligne screenplay : `informant_npc_lvl_1` @ 3488, -4782 dans `tatooine_mos_eisley.lua`.  
Si doublon IG : despawn GM du vanilla ou commenter la ligne.

## Smoke

```bash
bash infra/scripts/smoke_core3_ia_phase_c5_quest_giver_lan.sh
bash infra/scripts/smoke_core3_ia_phase_c5_quest_giver_lan.sh --with-think
```

Prérequis : Prime UP, sidecar actif ; `--with-think` : Lia en ligne + LLM.

## Suite

- C.4 inn : `roster:mos_eisley_innkeeper` (draft)
- C.6 : instructeur marksman (fenêtre + `train` stub)
- Brancher `quest:mos_eisley_intro_stub` au vrai système quêtes Core3
