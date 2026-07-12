# Props 3D — décor, drones, objets interactifs

## Drones

| Fichier | Scène wrapper | Source |
|---------|---------------|--------|
| `drones/robot01_round_godot.glb` | `scenes/props/Robot01Drone.tscn` | Infographiste_IA / TripoSR |

### Pivot et échelle

- **Pivot racine** (`Robot01Drone`) = point d’ancrage au sol (projection).
- **Vol** : `HoverOffset.position.y` ≈ **0,75 m** (export `hover_height_m`).
- **Taille** : envergure max ≈ **0,55 m** (`target_span_m`), ajustée auto au `_ready()` via AABB du GLB.
- **Collision** : sphère rayon 0,28 m sur `HoverOffset` (corps en vol).

### Prévisualiser

1. Ouvrir `lbg_client_godot` dans Godot 4.6.
2. Laisser importer `assets/props/drones/robot01_round_godot.glb` (premier scan).
3. Ouvrir `scenes/dev/Robot01Preview.tscn` → **F6** (Play Scene).
4. Ajuster `yaw_degrees` / `hover_height_m` sur l’instance si besoin.

### Cantina

Un drone décoratif est instancié dans `CantinaInterior` (coin vats, cell 1082877).
