"""
Importeur minimal pour les exports Watabou (Village Generator).

Entrées attendues (export Watabou) :
- JSON (FeatureCollection) contenant des entrées "id": "earth", "buildings", "roads", "trees", "fields", ...

Sorties :
- une grille ASCII (tuiles) pour collisions et debug
- un layout JSON (objets en coordonnées monde)

Conventions :
- origine monde au centre (0,0) comme dans les exports Watabou
- axes : x vers la droite ; z vers le bas (top-down)
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class Bounds:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def w(self) -> float:
        return self.max_x - self.min_x

    @property
    def h(self) -> float:
        return self.max_y - self.min_y


def _load_watabou_feature_map(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
        raise ValueError("watabou json root must be a FeatureCollection object")
    feats = data.get("features")
    if not isinstance(feats, list):
        raise ValueError("watabou json: features must be a list")

    out: dict[str, dict[str, Any]] = {}
    for f in feats:
        if not isinstance(f, dict):
            continue
        fid = f.get("id")
        if isinstance(fid, str) and fid:
            out[fid] = f
    return out


def _polygon_area_units(ring: list[list[float]]) -> float:
    """Aire d'un polygone (unités Watabou²), anneau fermé ou non."""
    n = len(ring)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if p <= 0:
        return sorted_vals[0]
    if p >= 1:
        return sorted_vals[-1]
    k = (len(sorted_vals) - 1) * p
    f = int(math.floor(k))
    c = int(math.ceil(k))
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def _earth_bounds(feature_map: dict[str, dict[str, Any]]) -> Bounds:
    earth = feature_map.get("earth")
    if not earth or earth.get("type") != "Polygon":
        raise ValueError("missing earth polygon (id=earth, type=Polygon)")
    coords = earth.get("coordinates")
    if not (isinstance(coords, list) and coords and isinstance(coords[0], list)):
        raise ValueError("earth.coordinates invalid")
    ring = coords[0]
    xs: list[float] = []
    ys: list[float] = []
    for p in ring:
        if not (isinstance(p, list) and len(p) >= 2):
            continue
        xs.append(float(p[0]))
        ys.append(float(p[1]))
    if not xs or not ys:
        raise ValueError("earth polygon empty")
    return Bounds(min(xs), min(ys), max(xs), max(ys))


def _dist2_point_to_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    # projection of P onto AB
    abx = bx - ax
    aby = by - ay
    apx = px - ax
    apy = py - ay
    denom = abx * abx + aby * aby
    if denom <= 1e-12:
        dx = px - ax
        dy = py - ay
        return dx * dx + dy * dy
    t = (apx * abx + apy * aby) / denom
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    cx = ax + t * abx
    cy = ay + t * aby
    dx = px - cx
    dy = py - cy
    return dx * dx + dy * dy


def _point_in_poly(px: float, py: float, poly: list[list[float]]) -> bool:
    # Ray casting
    inside = False
    n = len(poly)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i][0], poly[i][1]
        xj, yj = poly[j][0], poly[j][1]
        intersects = ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi + 1e-12) + xi)
        if intersects:
            inside = not inside
        j = i
    return inside


def _iter_building_polys(feature_map: dict[str, dict[str, Any]]) -> Iterable[list[list[float]]]:
    b = feature_map.get("buildings")
    if not b or b.get("type") != "MultiPolygon":
        return []
    coords = b.get("coordinates")
    if not isinstance(coords, list):
        return []
    for poly in coords:
        # poly: [ [ [x,y]... ] ] ; we use outer ring only
        if not (isinstance(poly, list) and poly and isinstance(poly[0], list) and poly[0]):
            continue
        ring = poly[0]
        out_ring: list[list[float]] = []
        for p in ring:
            if isinstance(p, list) and len(p) >= 2:
                out_ring.append([float(p[0]), float(p[1])])
        if len(out_ring) >= 3:
            yield out_ring


def _iter_trees(feature_map: dict[str, dict[str, Any]]) -> Iterable[tuple[float, float]]:
    t = feature_map.get("trees")
    if not t or t.get("type") != "MultiPoint":
        return []
    coords = t.get("coordinates")
    if not isinstance(coords, list):
        return []
    for p in coords:
        if isinstance(p, list) and len(p) >= 2:
            yield (float(p[0]), float(p[1]))


def _iter_roads(feature_map: dict[str, dict[str, Any]]) -> Iterable[tuple[float, list[tuple[float, float]]]]:
    r = feature_map.get("roads")
    if not r or r.get("type") != "GeometryCollection":
        return []
    geoms = r.get("geometries")
    if not isinstance(geoms, list):
        return []
    for g in geoms:
        if not isinstance(g, dict) or g.get("type") != "LineString":
            continue
        width = float(g.get("width", 1.0))
        coords = g.get("coordinates")
        if not isinstance(coords, list) or len(coords) < 2:
            continue
        pts: list[tuple[float, float]] = []
        for p in coords:
            if isinstance(p, list) and len(p) >= 2:
                pts.append((float(p[0]), float(p[1])))
        if len(pts) >= 2:
            yield (width, pts)


def build_grid_from_watabou(
    *,
    watabou_json_path: Path,
    tile_m: float = 2.0,
    unit_m: float = 1.0,
    padding_tiles: int = 2,
) -> dict[str, Any]:
    """
    Construit une grille 2D de tuiles depuis le JSON Watabou.

    - tile_m : taille d'une tuile dans le monde (m)
    - unit_m : conversion des unités Watabou -> mètres (par défaut 1.0 = 1 unité = 1m)
    """
    if tile_m <= 0 or unit_m <= 0:
        raise ValueError("tile_m and unit_m must be > 0")

    fm = _load_watabou_feature_map(watabou_json_path)
    b = _earth_bounds(fm)

    # Convert bounds to meters
    min_x_m = b.min_x * unit_m
    max_x_m = b.max_x * unit_m
    min_z_m = b.min_y * unit_m
    max_z_m = b.max_y * unit_m

    w = int(math.ceil((max_x_m - min_x_m) / tile_m)) + 2 * padding_tiles
    h = int(math.ceil((max_z_m - min_z_m) / tile_m)) + 2 * padding_tiles
    w = max(w, 1)
    h = max(h, 1)

    # origin at earth.min with padding
    origin_x_m = min_x_m - padding_tiles * tile_m
    origin_z_m = min_z_m - padding_tiles * tile_m

    def tile_center_world(gx: int, gz: int) -> tuple[float, float]:
        return (origin_x_m + (gx + 0.5) * tile_m, origin_z_m + (gz + 0.5) * tile_m)

    grid: list[list[str]] = [["." for _ in range(w)] for _ in range(h)]

    # Buildings (fill 'H')
    building_polys = list(_iter_building_polys(fm))
    for gz in range(h):
        for gx in range(w):
            x_m, z_m = tile_center_world(gx, gz)
            x_u = x_m / unit_m
            z_u = z_m / unit_m
            for poly in building_polys:
                if _point_in_poly(x_u, z_u, poly):
                    grid[gz][gx] = "H"
                    break

    # Roads (draw 'R' where close to polyline)
    for width_u, pts in _iter_roads(fm):
        half_w_m = (width_u * unit_m) / 2.0
        thresh2 = half_w_m * half_w_m
        for gz in range(h):
            for gx in range(w):
                if grid[gz][gx] == "H":
                    continue
                x_m, z_m = tile_center_world(gx, gz)
                # compute distance in meters vs segment endpoints in meters
                hit = False
                for i in range(len(pts) - 1):
                    ax_m = pts[i][0] * unit_m
                    az_m = pts[i][1] * unit_m
                    bx_m = pts[i + 1][0] * unit_m
                    bz_m = pts[i + 1][1] * unit_m
                    if _dist2_point_to_segment(x_m, z_m, ax_m, az_m, bx_m, bz_m) <= thresh2:
                        hit = True
                        break
                if hit:
                    grid[gz][gx] = "R"

    # Trees (place 'T' if empty)
    for (tx_u, tz_u) in _iter_trees(fm):
        tx_m = tx_u * unit_m
        tz_m = tz_u * unit_m
        gx = int(math.floor((tx_m - origin_x_m) / tile_m))
        gz = int(math.floor((tz_m - origin_z_m) / tile_m))
        if 0 <= gx < w and 0 <= gz < h and grid[gz][gx] == ".":
            grid[gz][gx] = "T"

    return {
        "kind": "watabou_grid_v1",
        "source": {
            "generator": fm.get("values", {}).get("generator", "watabou"),
            "version": fm.get("values", {}).get("version", None),
            "path": str(watabou_json_path),
        },
        "scale": {
            "tile_m": float(tile_m),
            "unit_m": float(unit_m),
            "padding_tiles": int(padding_tiles),
        },
        "bounds_world_m": {
            "min_x": float(origin_x_m),
            "min_z": float(origin_z_m),
            "max_x": float(origin_x_m + w * tile_m),
            "max_z": float(origin_z_m + h * tile_m),
        },
        "grid": {"w": int(w), "h": int(h), "rows": ["".join(r) for r in grid]},
    }


def build_layout_from_watabou(*, watabou_json_path: Path, unit_m: float = 1.0) -> dict[str, Any]:
    fm = _load_watabou_feature_map(watabou_json_path)
    b = _earth_bounds(fm)

    buildings: list[dict[str, Any]] = []
    for idx, poly in enumerate(_iter_building_polys(fm), start=1):
        buildings.append(
            {
                "id": f"b_{idx:04d}",
                "type": "building",
                "polygon_world_m": [{"x": float(x * unit_m), "z": float(y * unit_m)} for (x, y) in poly],
            }
        )

    roads: list[dict[str, Any]] = []
    for idx, (width_u, pts) in enumerate(_iter_roads(fm), start=1):
        roads.append(
            {
                "id": f"r_{idx:04d}",
                "type": "road",
                "width_m": float(width_u * unit_m),
                "polyline_world_m": [{"x": float(x * unit_m), "z": float(y * unit_m)} for (x, y) in pts],
            }
        )

    trees: list[dict[str, Any]] = []
    for idx, (x_u, y_u) in enumerate(_iter_trees(fm), start=1):
        trees.append({"id": f"t_{idx:05d}", "type": "tree", "x": float(x_u * unit_m), "z": float(y_u * unit_m)})

    return {
        "kind": "watabou_layout_v1",
        "source": {
            "generator": fm.get("values", {}).get("generator", "watabou"),
            "version": fm.get("values", {}).get("version", None),
            "path": str(watabou_json_path),
        },
        "scale": {"unit_m": float(unit_m)},
        "earth_bounds_units": {"min_x": float(b.min_x), "min_y": float(b.min_y), "max_x": float(b.max_x), "max_y": float(b.max_y)},
        "objects": {"buildings": buildings, "roads": roads, "trees": trees},
    }


def build_watabou_stats(*, watabou_json_path: Path, unit_m: float = 1.0) -> dict[str, Any]:
    """
    Statistiques pour valider l'échelle (surfaces bâtiments, emprise earth, routes, arbres).

    Hypothèse : 1 unité Watabou = ``unit_m`` mètres (défaut 1.0).
    Référence projet : bloc maison 4×4 tuiles à 2 m → 8 m × 8 m = 64 m².
    """
    if unit_m <= 0:
        raise ValueError("unit_m must be > 0")

    fm = _load_watabou_feature_map(watabou_json_path)
    b = _earth_bounds(fm)
    u2 = unit_m * unit_m
    earth_w_m = b.w * unit_m
    earth_h_m = b.h * unit_m

    areas_m2: list[float] = []
    for poly in _iter_building_polys(fm):
        areas_m2.append(_polygon_area_units(poly) * u2)
    areas_m2.sort()

    road_segments = 0
    road_length_m = 0.0
    road_linestrings = 0
    for _width_u, pts in _iter_roads(fm):
        road_linestrings += 1
        for i in range(len(pts) - 1):
            road_segments += 1
            ax, ay = pts[i]
            bx, by = pts[i + 1]
            dx = (bx - ax) * unit_m
            dy = (by - ay) * unit_m
            road_length_m += math.hypot(dx, dy)

    trees = list(_iter_trees(fm))

    def _bld_summary() -> dict[str, Any] | None:
        if not areas_m2:
            return None
        return {
            "count": len(areas_m2),
            "area_m2_min": round(areas_m2[0], 3),
            "area_m2_median": round(_percentile(areas_m2, 0.5), 3),
            "area_m2_p95": round(_percentile(areas_m2, 0.95), 3),
            "area_m2_max": round(areas_m2[-1], 3),
            "area_m2_mean": round(sum(areas_m2) / len(areas_m2), 3),
        }

    ref_house_m2 = 8.0 * 8.0  # 4 tuiles × 2 m (cf. docs/area_generation.md)

    return {
        "kind": "watabou_stats_v1",
        "source_path": str(watabou_json_path),
        "scale": {"unit_m": float(unit_m)},
        "earth": {
            "bbox_m": {
                "width": round(earth_w_m, 3),
                "height": round(earth_h_m, 3),
                "area_km2": round((earth_w_m * earth_h_m) / 1_000_000.0, 6),
            }
        },
        "buildings": _bld_summary(),
        "roads": {
            "linestrings": int(road_linestrings),
            "segments": int(road_segments),
            "total_length_m": round(road_length_m, 3),
        },
        "trees": {"count": len(trees)},
        "reference": {"doc_house_4x4tiles_at_2m_m2": ref_house_m2},
    }


def _print_stats(stats: dict[str, Any]) -> None:
    print("== Watabou stats ==")
    print(f"source: {stats['source_path']}")
    print(f"unit_m: {stats['scale']['unit_m']}")
    eb = stats["earth"]["bbox_m"]
    print(f"earth bbox: {eb['width']} m × {eb['height']} m (aire ~ {eb['area_km2']} km²)")
    b = stats.get("buildings")
    if b:
        print(
            f"buildings: {b['count']}  aire m² min/med/p95/max/mean: "
            f"{b['area_m2_min']} / {b['area_m2_median']} / {b['area_m2_p95']} / {b['area_m2_max']} / {b['area_m2_mean']}"
        )
        ref = stats["reference"]["doc_house_4x4tiles_at_2m_m2"]
        print(f"référence doc (4×4 tuiles @ 2 m): {ref} m²")
    r = stats["roads"]
    print(f"roads: {r['linestrings']} polylines, {r['segments']} segments, longueur totale ~ {r['total_length_m']} m")
    print(f"trees: {stats['trees']['count']}")


def _write_grid_txt(out_path: Path, rows: list[str]) -> None:
    out_path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Import Watabou Village Generator export into grid/layout.")
    p.add_argument("--in", dest="input_path", required=True, help="Chemin vers l'export JSON Watabou (FeatureCollection).")
    p.add_argument(
        "--out-dir",
        dest="out_dir",
        default=None,
        help="Dossier de sortie (créé si absent). Requis sauf avec --stats-only.",
    )
    p.add_argument("--name", dest="name", default="watabou_world", help="Préfixe de fichiers de sortie.")
    p.add_argument("--tile-m", dest="tile_m", type=float, default=2.0, help="Taille d'une tuile (m) pour la grille collisions.")
    p.add_argument("--unit-m", dest="unit_m", type=float, default=1.0, help="Conversion unités Watabou -> mètres.")
    p.add_argument("--padding-tiles", dest="padding_tiles", type=int, default=2, help="Padding tuiles autour du bounds earth.")
    p.add_argument("--stats", dest="stats", action="store_true", help="Afficher des stats (échelle / surfaces) après import.")
    p.add_argument(
        "--stats-only",
        dest="stats_only",
        action="store_true",
        help="Afficher uniquement les stats (pas d'écriture grid/layout).",
    )
    p.add_argument("--stats-json", dest="stats_json", default=None, help="Optionnel : écrire les stats en JSON dans ce fichier.")

    args = p.parse_args(argv)
    in_path = Path(args.input_path).expanduser().resolve()

    if args.stats_only:
        stats = build_watabou_stats(watabou_json_path=in_path, unit_m=args.unit_m)
        _print_stats(stats)
        if args.stats_json:
            Path(args.stats_json).expanduser().resolve().write_text(
                json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return 0

    if not args.out_dir:
        p.error("--out-dir est requis (ou utilise --stats-only)")

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    grid = build_grid_from_watabou(watabou_json_path=in_path, tile_m=args.tile_m, unit_m=args.unit_m, padding_tiles=args.padding_tiles)
    layout = build_layout_from_watabou(watabou_json_path=in_path, unit_m=args.unit_m)

    (out_dir / f"{args.name}.grid.json").write_text(json.dumps(grid, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_grid_txt(out_dir / f"{args.name}.grid.txt", grid["grid"]["rows"])
    (out_dir / f"{args.name}.layout.json").write_text(json.dumps(layout, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.stats:
        stats = build_watabou_stats(watabou_json_path=in_path, unit_m=args.unit_m)
        _print_stats(stats)
        if args.stats_json:
            Path(args.stats_json).expanduser().resolve().write_text(
                json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

