# Assets monde — Client Godot Prime

Objectif : représenter **Tatooine Prime** (extérieur + intérieurs) sans charger les `.tre` SWG en runtime.

## Structure cible

```
assets/world/
  terrain/           # heightmap / mesh Tatooine (Mos Eisley)
  exteriors/         # GLB bâtiments zone (depuis world_poi / export WE)
  interiors/
    mos_eisley_cantina/   # cell 1082877 — priorité M0
  collisions/        # simplifications pour Godot StaticBody (v1)
```

## Repère

- Coords **monde** alignées gateway : `content/core3/locations/*.json` → `world_anchor`
- Intérieurs : coords **locales** cellule → conversion via `services/lbg_gateway/world_coords.py`

## M0 (en cours)

Cantina Mos Eisley : bloc placeholder (CSG ou GLB) pour remplacer le plan vert du POC.

Voir [`../../docs/plan_client_godot_prime_rendu.md`](../../docs/plan_client_godot_prime_rendu.md).

**Pipeline SWG → GLB (personnages, textures, cantina)** : [`../../docs/pipeline_assets_swg_godot.md`](../../docs/pipeline_assets_swg_godot.md).
