# Déploiement PNJ Core3 — profils, remplacement, routines, effectifs

**Contexte** : Phase C livrée (2 pilotes `[IA]` spawn + pont sidecar).  
**Objectif** : deux PNJ **référence parfaits**, puis généralisation par **profil** ; PNJ simples **remplacés** ; donneurs de quêtes / instructeurs avec **routine** ; **doublons de service** (pas des clones miroirs).

## Principes

| Principe | Détail |
|----------|--------|
| **Profil ≠ instance** | Un `profile_id` (persona LBG + règles LLM + actions Core3) s’applique à N mobiles. |
| **Monde quasi vide** | `ia_spawn_tag.lua` : **cull global** (toutes zones) — tout `spawnMobile` vanilla détruit sauf pilotes `ia_bridge`. Tag **`[No IA]`** désactivé ; repopulation décorative manuelle plus tard (`IA_WORLD_NO_IA_ENABLED`). |
| **Pilotes LBG** | Suffixe **`(PNJ IA)`** ; protégés du cull (`__IA_BRIDGE_SPAWNING_PILOT`). |
| **Simple → remplacer** | Civils / vendeurs sans quête vanilla : désactiver le spawn d’origine, spawn LBG contrôlé. |
| **Quête / instructeur → routine** | Horaires, poste, états (`idle`, `bark`, `offer_quest`, `train`) avant dialogue libre. |
| **Triplon de service** | **3 personnages passifs** distincts par métier (pas 2 clones) — un seul au poste en phase **travail**. |
| **Pas de clone** | Prénom, tenue, logement, ton, objectifs différents ; voir `docs/core3_ia_game_time_rosters.md`. |
| **Temps jeu** | 24 h réel = 4 jours jeu ; 1 jour jeu = 6 h réel ; par jour jeu : ~2 h travail, ~2 h repos (logement), ~2 h loisir. |

## Mos Eisley — centre d'entraînement (recon IG 2026-05-29)

Fichier coords : `content/core3/locations/mos_eisley_training_center.json`

| Image | Profession | Position (x, y, z) |
|-------|------------|-------------------|
| 1 | Brawler | 3462, -4660, 6 |
| 2 | Marksman | 3457, -4669, 6 |
| 3 | Scout | 3474, -4666, 6 |
| 4 | Medic | 3468, -4686, 6 *(X à confirmer)* |
| 5 | Entertainer | 3465, -4682, 6 *(approx., centre salle)* |
| 6 | Politician | 3463, -4678, 6 |
| 7 | Artisan | 3451, -4679, 6 |

Pilotes spaceport (`mos_eisley_starport_pilot_trainers.json`) :

| Image | Rôle | Position (x, y, z) |
|-------|------|-------------------|
| 1 | Alliance Starfighter Pilot | 3551, -4800, 5 |
| 2 | Imperial Navy Pilot | 3551, -4805, 5 |
| 3 | Freelance Pilot | 3570, -4801, 5 |

Skills space (conversation) : phase **3b** — mobiles visuels dès phase 2 si besoin.

**Éditeur monde (plan v1)** : placement Dev+ in-game + export Git — [`docs/world_editor_plan.md`](world_editor_plan.md). Résout notamment `cell` intérieur centre ME.

**Statut catalogue (2026-06-01)** : `core3_npc_catalog.json` — rosters actifs incluent :
`roster:mos_trainer_{brawler,marksman,scout,medic,politician,artisan}` (cells ME 1189634–1189639),
`roster:mos_entertainer_trainer` (poste ME + **loisir scène** cell `1105851`),
`roster:mos_eisley_cantina_barman` (bar cell `1082877`, y=1.15),
`roster:mos_pilot_{alliance,imperial,freelance}`.  
Cantina / théâtre : [`docs/mos_eisley_cantina_ia.md`](mos_eisley_cantina_ia.md) · World Editor : [`docs/world_editor_handoff_demain.md`](world_editor_handoff_demain.md).

## Schéma données (v2)

Fichier cible : `content/core3/core3_npc_catalog.json` (évolution de `core3_npc_pilots.json`).

```json
{
  "schema_version": 2,
  "zone": "tatooine",
  "profiles": {
    "profile:scribe_ref": {
      "lbg_npc_id": "npc:scribe",
      "tier": "reference",
      "actions": ["npc_say"],
      "llm": { "temperature": 0.3, "max_tokens": 120 }
    }
  },
  "entries": [],
  "rosters": [],
  "vanilla_replacements": []
}
```

### Champs `entries[]` (une instance pilotée)

| Champ | Rôle |
|-------|------|
| `pilot_id` | Clé pont / file `npc_say` |
| `profile_id` | Lien vers `profiles` |
| `display_name` | Nom affiché IG |
| `binding.mode` | `spawn` \| `static_bind` \| `replace_vanilla` |
| `binding.spawn` | Position si spawn |
| `binding.vanilla_ref` | Clé screenplay / spawn à couper si remplacement |
| `routine` | Optionnel — voir ci-dessous |
| `status` | `draft` \| `active` \| `retired` |

### `rosters[]` (triplons de service — préférer 3 slots)

Un **rôle métier** (ex. aubergiste Mos Eisley), **trois personnages** (triplons) décalés sur le cycle travail/repos/loisir :

```json
{
  "roster_id": "roster:mos_eisley_innkeeper",
  "profile_id": "profile:innkeeper_v1",
  "service_policy": "at_least_one",
  "slots": [
    {
      "pilot_id": "npc:core3_inn_day",
      "display_name": "Mara l'aubergiste",
      "shift": "day",
      "binding": { "mode": "spawn", "spawn": { "x": 0, "y": 0, "z": 0 } }
    },
    {
      "pilot_id": "npc:core3_inn_night",
      "display_name": "Jor le veilleur",
      "shift": "night",
      "binding": { "mode": "spawn", "spawn": { "x": 0, "y": 0, "z": 0 } }
    }
  ]
}
```

**Politiques** (implémentation progressive) :

- `at_least_one` : au moins un slot spawn / actif dans la fenêtre courante.
- `exactly_one` : un seul visible, les autres despawn ou `noop` + hors zone.
- `overlap_ok` : deux présents (foule) mais barks dédupliqués côté sidecar.

### `routine` (quête / instructeur)

```json
{
  "kind": "quest_giver",
  "schedule": [
    {
      "id": "morning_counter",
      "window_utc": "06:00-14:00",
      "location_id": "mos_eisley_cantina",
      "states": ["idle", "bark", "offer_quest"]
    },
    {
      "id": "afternoon_archives",
      "window_utc": "14:00-22:00",
      "location_id": "mos_eisley_archives",
      "states": ["idle", "bark"]
    }
  ],
  "quest_hooks": ["quest:intro_tatooine_01"]
}
```

```json
{
  "kind": "trainer",
  "schedule": [
    {
      "window_utc": "08:00-20:00",
      "location_id": "mos_eisley_skill_terminal",
      "states": ["train", "bark"]
    }
  ],
  "skill_trainer_type": "marksman"
}
```

États = whitelist d’actions sidecar / screenplay (phase ultérieure : `npc_bark`, `npc_offer_quest`, `npc_train`).

### `vanilla_replacements[]`

Déclare ce qu’on **retire** du monde statique :

```json
{
  "vanilla_ref": "tatooine_mos_espa:innkeeper_spawn_3",
  "action": "disable_spawn",
  "replaced_by": "roster:mos_eisley_innkeeper",
  "notes": "Ne pas spawn le PNJ vanilla ; roster LBG assure le service"
}
```

`action` : `disable_spawn` (commentaire + patch screenplay ville) \| `hide` (despawn au boot si déjà là).

## Phases d’implémentation

| Étape | Livrable | Jeu |
|-------|----------|-----|
| **C.1 — Référence** | 2 profils figés + smoke `smoke_core3_ia_phase_c1_reference_lan.sh` — **terminé** (`docs/core3_ia_phase_c1_reference.md`) | OK |
| **C.2 — Catalog v2** | Sidecar lit `core3_npc_catalog.json` (profils LLM) — **terminé** (`docs/core3_ia_phase_c2_catalog.md`) | OK |
| **C.3 — Remplacement simple** | Kisreudi Teste (scientist, poste fixe) — **terminé** (`docs/core3_ia_phase_c3_replace.md`) | OK |
| **C.4 — Roster service** | Entertainer Bige/Lyra (`exactly_one` poste + show cantina) — **terminé** (`docs/core3_ia_phase_c4_entertainer_roster.md`) | OK |
| **C.4b — Temps jeu** | Moteur phases + triplon entertainer (Bige/Lyra/Talen) — **terminé** (`docs/core3_ia_phase_c4b_game_time.md`) | OK |
| **C.5 — Routine quête** | Triplon `roster:mos_eisley_quest_giver` + `offer_quest` stub — **terminé** (`docs/core3_ia_phase_c5_quest_giver.md`) | OK |
| **C.6 — Instructeur** | 1 trainer : fenêtre + lieu fixe | Train + barks |
| **C.7 — Scale** | Copier profils sur N rôles Tatooine | Extension planète par planète |

## Checklist « PNJ parfait » (C.1)

**Profil LBG** (`npc_registry.json`) :

- [ ] `id`, `name`, `role`, `tone`, `summary`, `goals`, `constraints`
- [ ] `race_id` + world-content si besoin

**Pont Core3** :

- [ ] `pilot_id` ↔ `lbg_npc_id`
- [ ] Nom `[IA]` ou nom diegetique cohérent
- [ ] Snapshot fiable (`npc_snapshots.json`)
- [ ] `POST /v1/npc-think` → `npc_say` visible (spatial chat)
- [ ] Pas de doublon spawn (object id persistant)
- [ ] Orchestrateur `core3_bot_action` avec `npc_id` LBG

**UX** :

- [ ] Distance lisible près du point d’intérêt
- [ ] Comportement prévisible (pas de téléport agressif sauf policy)

## Lien stacks

| Stack | Rôle |
|-------|------|
| `npc_registry.json` | Persona / intention orchestrateur |
| `core3_npc_catalog.json` | Instances, rosters, remplacements, routines |
| `ia_bridge_screenplay.lua` | Spawn, bind, routine tick, actions file |
| Sidecar `:8791` | LLM + enqueue |
| Screenplays ville | Cibles `vanilla_replacements` |

## Suite immédiate proposée

1. Valider **C.1** sur les 2 PNJ actuels (checklist ci-dessus).
2. Créer **`core3_npc_catalog.json`** v2 avec les 2 entrées en `status: active` + profils `profile:scribe_ref` / `profile:guard_ref`.
3. Choisir **un** PNJ vanilla simple à remplacer (ex. un commoner redondant près de la cantine) pour **C.3**.

Voir aussi : `docs/core3_ia_phase_c_npc_pilots.md`, ADR 0007.
