# C.1 — PNJ référence « parfaits » (Archiviste + Garde)

**Statut** : validé par smoke automatisé + revue profil (2026-05-23).  
**Périmètre** : Serveur Prime, Tatooine, Mos Eisley (cobaye Lia).

## PNJ concernés

| `lbg_npc_id` | `pilot_id` | Nom IG | Profil catalogue |
|--------------|------------|--------|------------------|
| `npc:scribe` | `npc:core3_scribe` | `[IA] Archiviste` | `profile:scribe_ref` |
| `npc:guard` | `npc:core3_guard` | `[IA] Garde` | `profile:guard_ref` |

## Checklist C.1

### Profil LBG (`agents/src/lbg_agents/npc_registry.json`)

| Critère | Scribe | Garde |
|---------|--------|-------|
| `id`, `name`, `role`, `tone`, `summary` | OK | OK |
| `goals`, `constraints` | OK (Mos Eisley / spatial court) | OK |
| `race_id` | `race:murrik` | `race:sylven` |
| `core3_reference.pilot_id` | `npc:core3_scribe` | `npc:core3_guard` |
| `core3_reference.c1_status` | `reference_active` | `reference_active` |

### Pont Core3

| Critère | Validation |
|---------|------------|
| Registre spawn `core3_npc_pilots.json` | 2 entrées |
| Catalogue v2 `core3_npc_catalog.json` | 2 `entries` `status: active` |
| `GET /healthz` → `npc_pilot_count: 2` | smoke C.1 |
| `GET /v1/npc-pilots` → 2 online | smoke C.1 |
| `npc_snapshots.json` → 2 clés, `online: true` | smoke C.1 |
| Pas de troupeau (spawn log) | smoke C.1 |
| `POST /v1/npc-think` scribe + guard | `--with-think` |
| Intent `core3_bot_action` | manuel ou pilot 140 si `LBG_CORE3_IA_SIDECAR_URL` |

### UX (manuel en jeu)

| Critère | Note |
|---------|------|
| Exactement 2 PNJ tag `[IA]` près de Lia | Validé utilisateur |
| Spatial chat après think | À revérifier après chaque deploy Lua |
| Ronde locale sans traversee murs | `roam_mode: walk_patrol` + `roam_patrol` (jalons), `roam_contain_m: 22` — pas `AI_PATROLLING` outdoor |

## Smoke

```bash
bash infra/scripts/smoke_core3_ia_phase_c1_reference_lan.sh
bash infra/scripts/smoke_core3_ia_phase_c1_reference_lan.sh --with-think
```

## Modèle pour C.2+

Dupliquer la structure :

1. Copier un bloc `profiles.profile:*_ref` + `entries[]`.
2. Renseigner `npc_registry` + `core3_reference`.
3. Lancer le smoke C.1 adapté (ou généraliser le script).

Suite : **`docs/core3_ia_npc_rollout.md`** — étape **C.2** (sidecar lit `core3_npc_catalog.json`).
