# ADR 0008 — Éditeur monde Prime (world_poi + export repo)

**Statut** : accepté (2026-05-30)  
**Contexte** : placement PNJ IA (catalogue `core3_npc_catalog.json`) et POI monde (centre d’entraînement Mos Eisley) nécessitent coords + **cellule** fiables. L’édition manuelle JSON + recon IG est lente et source d’erreurs (PNJ invisibles en intérieur).

**Plan détaillé** : [`docs/world_editor_plan.md`](../world_editor_plan.md)

---

## Décisions actées

| Sujet | Choix |
|-------|--------|
| Périmètre v1 | **PNJ** (catalogue / rosters) + **un POI bâtiment** pilote : centre d’entraînement Mos Eisley |
| Persistance structures | Table SQL dédiée **`world_poi`** — **pas** `playerstructures` ni propriété joueur |
| Droits | **Dev+ uniquement** (`admin_level >= 3` compte **et** perso effectif) |
| Export vers repo | **Automatique** via **agent côté VM** (JSON versionné sous `content/core3/world_poi/`) |
| Moteur bâtiment | Réutiliser **`StructureManager::placeStructure`** (templates `object/building/...`) — **sans** parcours deed / ville joueur |
| Moteur PNJ | Réutiliser **`ia_bridge`** + `core3_npc_catalog.json` (posts avec `cell`) |
| Monde Pixie Seat / Watabou | **Hors scope v1** — stack 2D séparée (`mmo_server`), pas substitut Tatooine 3D |

---

## Règles

1. **`world_poi`** = POI staff (structures fixes, décor admin, annexes). Jamais confondu avec housing joueur ou `CityRegion`.
2. Propriétaire structure POI = compte système **`LBG_WORLD`** (OID fixe), pas le perso Dev qui pose.
3. Toute modification IG validée en session produit un **export JSON** + entrée **audit** (`world_editor_audit.jsonl`).
4. L’agent VM pousse vers le dépôt Git (branche dédiée ou commit direct selon politique CI) — **pas** d’édition manuelle obligatoire sur la VM.
5. GM (1) et Moderator (2) **n’accèdent pas** à l’éditeur, même avec god activé.

---

## Conséquences

- Migration SQL + chargement au boot (`LbgWorldPoiScreenPlay` ou extension `ia_bridge`).
- Nouvelles commandes staff `/lbg_we_*` (place, remove, dump, export).
- Dépendance : résolution **cell ID** bâtiment pour les 7 rosters trainers ME.
- Navmesh / restart zone : documenter dans le runbook si placement structure l’exige.

---

## Non-objectifs v1

- Éditeur visuel drag-and-drop client SWG.
- Placement libre de city halls / villes joueur sur le monde vanilla.
- Décoration intérieure libre (items meuble).
- Sync bidirectionnelle Git → serveur sans restart screenplay.
