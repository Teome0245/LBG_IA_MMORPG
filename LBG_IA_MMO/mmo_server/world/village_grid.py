"""
Grille de village (collisions) — charge un export `watabou_grid_v1` produit par `world.tools.watabou_import`.

Coordonnées monde (x, z) en mètres, alignées sur `bounds_world_m` :
- origine coin haut-gauche de la tuile (0,0) = (min_x, min_z)
- x vers l’est, z vers le sud (axe « image » du visualiseur)
"""

from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Tuiles considérées franchissables (MVP). Arbres / bâtiments / eau = bloqués.
_WALKABLE = frozenset({".", "R"})


@dataclass(slots=True)
class VillageCollisionGrid:
    tile_m: float
    w: int
    h: int
    origin_x: float
    origin_z: float
    rows: tuple[str, ...]
    source_path: str | None

    @classmethod
    def load(cls, path: Path) -> VillageCollisionGrid:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("kind") != "watabou_grid_v1":
            raise ValueError("fichier doit être un watabou_grid_v1 (watabou_import.py)")
        scale = data.get("scale") or {}
        tile_m = float(scale.get("tile_m", 2.0))
        if tile_m <= 0:
            raise ValueError("tile_m invalide")
        bounds = data.get("bounds_world_m") or {}
        ox = float(bounds["min_x"])
        oz = float(bounds["min_z"])
        g = data.get("grid") or {}
        w = int(g["w"])
        h = int(g["h"])
        rows_raw = g.get("rows")
        if not isinstance(rows_raw, list) or len(rows_raw) != h:
            raise ValueError("grid.rows invalide")
        rows: list[str] = []
        for i, row in enumerate(rows_raw):
            if not isinstance(row, str) or len(row) != w:
                raise ValueError(f"grid.rows[{i}] longueur invalide")
            rows.append(row)
        return cls(
            tile_m=tile_m,
            w=w,
            h=h,
            origin_x=ox,
            origin_z=oz,
            rows=tuple(rows),
            source_path=str(path),
        )

    def world_to_tile(self, x: float, z: float) -> tuple[int, int] | None:
        gx = int(math.floor((x - self.origin_x) / self.tile_m))
        gz = int(math.floor((z - self.origin_z) / self.tile_m))
        if gx < 0 or gz < 0 or gx >= self.w or gz >= self.h:
            return None
        return gx, gz

    def terrain_at_world_m(self, x: float, z: float) -> tuple[str | None, int | None, int | None]:
        t = self.world_to_tile(x, z)
        if t is None:
            return None, None, None
        gx, gz = t
        return self.rows[gz][gx], gx, gz

    def is_walkable_world_m(self, x: float, z: float) -> bool:
        ch, _, _ = self.terrain_at_world_m(x, z)
        if ch is None:
            return False
        return ch in _WALKABLE


def resolve_village_grid_path() -> Path | None:
    """Chemin JSON grille : env `LBG_MMO_VILLAGE_GRID_JSON` ou `seed_data/pixie_seat.grid.json`."""
    raw = os.environ.get("LBG_MMO_VILLAGE_GRID_JSON", "").strip()
    if raw:
        p = Path(raw).expanduser()
        return p if p.exists() else None
    default = Path(__file__).resolve().parent / "seed_data" / "pixie_seat.grid.json"
    return default if default.exists() else None


def load_village_grid_optional() -> VillageCollisionGrid | None:
    p = resolve_village_grid_path()
    if p is None:
        logger.info("aucune grille village (fichier absent, collisions désactivées)")
        return None
    try:
        g = VillageCollisionGrid.load(p)
        logger.info("grille village chargée (%s) %d×%d tuiles %.2fm", p, g.w, g.h, g.tile_m)
        return g
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
        logger.warning("grille village invalide (%s) : %s", p, e)
        return None


def village_grid_meta(grid: VillageCollisionGrid) -> dict[str, Any]:
    return {
        "kind": "village_collision_meta_v1",
        "source_path": grid.source_path,
        "tile_m": grid.tile_m,
        "grid": {"w": grid.w, "h": grid.h},
        "bounds_world_m": {
            "min_x": grid.origin_x,
            "min_z": grid.origin_z,
            "max_x": grid.origin_x + grid.w * grid.tile_m,
            "max_z": grid.origin_z + grid.h * grid.tile_m,
        },
        "walkable_tiles": sorted(_WALKABLE),
    }
