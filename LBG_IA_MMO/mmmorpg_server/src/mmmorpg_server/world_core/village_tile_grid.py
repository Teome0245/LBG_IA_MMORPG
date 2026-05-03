"""
Grille de collisions « village » (export `watabou_grid_v1` du même format que `mmo_server.world.village_grid`).

Chemins de chargement (dans l’ordre) :

1. `MMMORPG_VILLAGE_GRID_JSON` — chemin absolu ou relatif vers un JSON `watabou_grid_v1` (prioritaire pour ce serveur WS).
2. `LBG_MMO_VILLAGE_GRID_JSON` — même format ; partagé avec `mmo_server` si tu veux un seul fichier pour HTTP + WS.
3. Sinon résolution automatique vers `mmo_server/world/seed_data/pixie_seat.grid.json` (chemins relatifs au CWD ou au monorepo `LBG_IA_MMO/`).
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

_WALKABLE = frozenset({".", "R"})


@dataclass(slots=True)
class VillageTileGrid:
    tile_m: float
    w: int
    h: int
    origin_x: float
    origin_z: float
    rows: tuple[str, ...]
    source_path: str | None

    @classmethod
    def load(cls, path: Path) -> VillageTileGrid:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("kind") != "watabou_grid_v1":
            raise ValueError("attendu watabou_grid_v1")
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
                raise ValueError(f"grid.rows[{i}] invalide")
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

    def is_walkable_tile(self, gx: int, gz: int) -> bool:
        if gx < 0 or gz < 0 or gx >= self.w or gz >= self.h:
            return False
        return self.rows[gz][gx] in _WALKABLE

    def _iter_spiral_tiles(self, cx: int, cz: int):
        """Couches de Chebyshev r=0,1,2,… autour de (cx,cz), bornées à la grille."""
        max_r = max(self.w, self.h) + 1
        for r in range(max_r):
            if r == 0:
                if 0 <= cx < self.w and 0 <= cz < self.h:
                    yield cx, cz
                continue
            gz_top = cz - r
            if 0 <= gz_top < self.h:
                for gx in range(cx - r, cx + r + 1):
                    if 0 <= gx < self.w:
                        yield gx, gz_top
            gz_bot = cz + r
            if 0 <= gz_bot < self.h:
                for gx in range(cx - r, cx + r + 1):
                    if 0 <= gx < self.w:
                        yield gx, gz_bot
            gx_left = cx - r
            if 0 <= gx_left < self.w:
                for gz in range(cz - r + 1, cz + r):
                    if 0 <= gz < self.h:
                        yield gx_left, gz
            gx_right = cx + r
            if 0 <= gx_right < self.w:
                for gz in range(cz - r + 1, cz + r):
                    if 0 <= gz < self.h:
                        yield gx_right, gz

    def first_walkable_spawn_world_m(self) -> tuple[float, float] | None:
        """
        Point d'apparition joueur (x, z) au centre d'une tuile franchissable.
        Spirale (couches Chebyshev) depuis la tuile sous (0, 0), ou depuis le centre de la grille
        si (0, 0) est hors bounds.
        """
        t = self.world_to_tile(0.0, 0.0)
        if t is not None:
            cx, cz = t
        else:
            cx, cz = self.w // 2, self.h // 2
        return self._first_walkable_from_tile_origin(cx, cz)

    def nearest_walkable_tile_center_world_m(self, x: float, z: float) -> tuple[float, float] | None:
        """
        Centre monde de la tuile franchissable la plus proche en « spirale » (couches Chebyshev)
        depuis la tuile sous (x, z). Si (x, z) est hors grille, part du centre de la grille puis
        `first_walkable_spawn_world_m`.
        """
        t = self.world_to_tile(float(x), float(z))
        if t is None:
            return self.first_walkable_spawn_world_m()
        cx, cz = t
        return self._first_walkable_from_tile_origin(cx, cz)

    def _first_walkable_from_tile_origin(self, cx: int, cz: int) -> tuple[float, float] | None:
        for gx, gz in self._iter_spiral_tiles(cx, cz):
            if self.is_walkable_tile(gx, gz):
                wx = self.origin_x + (gx + 0.5) * self.tile_m
                wz = self.origin_z + (gz + 0.5) * self.tile_m
                return wx, wz
        return None


def _candidate_paths() -> list[Path]:
    out: list[Path] = []
    for key in ("MMMORPG_VILLAGE_GRID_JSON", "LBG_MMO_VILLAGE_GRID_JSON"):
        raw = os.environ.get(key, "").strip()
        if raw:
            out.append(Path(raw).expanduser())
    here = Path(__file__).resolve()
    # .../LBG_IA_MMO/mmmorpg_server/src/mmmorpg_server/world_core/ -> parents[4] = LBG_IA_MMO
    repo_mmo = here.parents[4] / "mmo_server" / "world" / "seed_data" / "pixie_seat.grid.json"
    out.extend(
        [
            repo_mmo,
            Path("../mmo_server/world/seed_data/pixie_seat.grid.json"),
            Path("../../mmo_server/world/seed_data/pixie_seat.grid.json"),
        ]
    )
    return out


def try_load_village_tile_grid() -> VillageTileGrid | None:
    for p in _candidate_paths():
        try:
            if p.exists():
                g = VillageTileGrid.load(p)
                logger.info("grille village tuilée chargée %s (%d×%d, %.2fm/tuile)", p, g.w, g.h, g.tile_m)
                return g
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
            logger.warning("grille village ignorée (%s) : %s", p, e)
    logger.info("pas de grille village tuilée (mouvements : obstacles seed + wrap seulement)")
    return None
