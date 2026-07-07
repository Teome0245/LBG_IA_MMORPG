#!/usr/bin/env python3
"""M8 — Patch starting_locations.iff pour spawn Lost Heaven (Scrapaltai)."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from datatable_iff import read_dtii, write_dtii

ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / "content/core3/scrapaltai_world.json"


def load_world() -> dict:
    return json.loads(WORLD.read_text(encoding="utf-8"))


def patch_rows(cols: list[str], types: list[str], rows: list[list], world: dict) -> list[list]:
    spawn = world["new_player_spawn"]
    sx = float(spawn["x"])
    sy = float(spawn["z"])  # hauteur datatable = colonne y
    sz = float(spawn["y"])  # plan horizontal datatable = colonne z
    heading = float(spawn.get("heading", 90))
    radius = 2.5

    loc_idx = cols.index("location") if "location" in cols else 0
    planet_idx = cols.index("planet") if "planet" in cols else 1
    x_idx = cols.index("x")
    y_idx = cols.index("y")
    z_idx = cols.index("z")
    cell_idx = cols.index("cell") if "cell" in cols else None
    image_idx = cols.index("image") if "image" in cols else None
    desc_idx = cols.index("description") if "description" in cols else None
    radius_idx = cols.index("radius") if "radius" in cols else None
    heading_idx = cols.index("heading") if "heading" in cols else None

    out: list[list] = []
    seen_lh = any(str(r[loc_idx]) == "lost_heaven" for r in rows)
    for row in rows:
        row = list(row)
        loc = str(row[loc_idx])
        planet = str(row[planet_idx])
        if planet != "tatooine":
            continue
        if loc in ("mos_eisley", "mos_espa", "bestine", "anchorhead"):
            continue
        if loc.startswith("tatooine_"):
            row[planet_idx] = "tatooine"
            row[x_idx] = sx
            row[y_idx] = sy
            row[z_idx] = sz
            if heading_idx is not None:
                row[heading_idx] = heading
            if radius_idx is not None:
                row[radius_idx] = radius
            if cell_idx is not None:
                row[cell_idx] = " "
            if image_idx is not None:
                row[image_idx] = "/styles.location.tatooine.mos_eisley"
            if desc_idx is not None:
                row[desc_idx] = "lost_heaven"
            out.append(row)
            continue
        out.append(row)

    if not seen_lh:
        new_row = list(rows[0]) if rows else [""] * len(cols)
        new_row[loc_idx] = "lost_heaven"
        new_row[planet_idx] = "tatooine"
        new_row[x_idx] = sx
        new_row[y_idx] = sy
        new_row[z_idx] = sz
        if cell_idx is not None:
            new_row[cell_idx] = " "
        if image_idx is not None:
            new_row[image_idx] = "/styles.location.tatooine.mos_eisley"
        if desc_idx is not None:
            new_row[desc_idx] = "lost_heaven"
        if radius_idx is not None:
            new_row[radius_idx] = radius
        if heading_idx is not None:
            new_row[heading_idx] = heading
        out.append(new_row)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Patch starting_locations.iff → Lost Heaven")
    parser.add_argument("source", type=Path, help="starting_locations.iff source (client ou Core3 bin)")
    parser.add_argument("-o", "--output", type=Path, help="Sortie (défaut: source + .patched)")
    parser.add_argument("--in-place", action="store_true", help="Écrase la source (backup .bak)")
    args = parser.parse_args()

    world = load_world()
    src = args.source.expanduser().resolve()
    if not src.is_file():
        raise SystemExit(f"Fichier introuvable: {src}")

    dst = args.output
    if args.in_place:
        backup = src.with_suffix(src.suffix + ".bak")
        shutil.copy2(src, backup)
        dst = src
    elif dst is None:
        dst = src.with_suffix(".patched.iff")

    cols, types, rows = read_dtii(str(src))
    patched = patch_rows(cols, types, rows, world)
    write_dtii(str(dst), cols, types, patched)
    spawn = world["new_player_spawn"]
    print(f"OK {len(patched)} lignes tatooine → {dst}")
    print(f"  spawn lost_heaven @ x={spawn['x']} z={spawn['y']} h={spawn['z']}")


if __name__ == "__main__":
    main()
