#!/usr/bin/env python3
"""Applique un layout Scrapaltai (JSON) → screenplay Lua + lost_heaven_hub.json."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LAYOUT = Path(__file__).resolve().parent / "layouts" / "scrapaltai_v7_default.json"
CATALOG = Path(__file__).resolve().parent / "scrapaltai_poi_catalog.json"
SCREENPLAY = ROOT / "content" / "core3" / "lua" / "lbg_lost_heaven_screenplay.lua"
HUB_JSON = ROOT / "content" / "core3" / "locations" / "lost_heaven_hub.json"


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def catalog_by_id(catalog: dict) -> dict[str, dict]:
    return {p["poi_id"]: p for p in catalog.get("pois", [])}


def validate_layout(layout: dict, catalog: dict) -> list[str]:
    errors: list[str] = []
    by_id = catalog_by_id(catalog)
    min_fp = catalog.get("min_center_spacing_m", layout.get("grid_spacing_m", 100))
    buildings = layout.get("buildings", [])
    seen: set[str] = set()
    for b in buildings:
        pid = b.get("poi_id", "")
        if pid in seen:
            errors.append(f"poi_id dupliqué: {pid}")
        seen.add(pid)
        if pid not in by_id:
            errors.append(f"poi_id inconnu du catalogue: {pid}")
    for i, a in enumerate(buildings):
        for j in range(i + 1, len(buildings)):
            b = buildings[j]
            dx = a["ox"] - b["ox"]
            dy = a["oy"] - b["oy"]
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < min_fp - 1:
                errors.append(
                    f"espacement insuffisant {dist:.0f}m < {min_fp}m: "
                    f"{a['poi_id']} vs {b['poi_id']}"
                )
    civic = layout.get("civic_center_poi")
    if civic:
        center = next((b for b in buildings if b["poi_id"] == civic), None)
        if center and (center.get("ox", 0) != 0 or center.get("oy", 0) != 0):
            errors.append(f"centre civique {civic} doit être @ ox=0 oy=0")
    return errors


def generate_build_plan_lua(layout: dict, catalog: dict) -> str:
    by_id = catalog_by_id(catalog)
    lines = ["local LH_BUILD_PLAN = {"]
    for b in layout.get("buildings", []):
        pid = b["poi_id"]
        meta = by_id.get(pid, {})
        tpl = meta.get("template", "object/building/tatooine/cantina_tatooine.iff")
        ox = int(b.get("ox", 0))
        oy = int(b.get("oy", 0))
        lines.append(
            f'\t{{ poi_id = "{pid}", template = "{tpl}", ox = {ox}, oy = {oy} }},'
        )
    lines.append("}")
    return "\n".join(lines)


def patch_screenplay(text: str, layout: dict, catalog: dict, bump_version: int | None) -> str:
    anchor = layout["anchor"]
    spacing = int(layout.get("grid_spacing_m", 100))
    civic = layout.get("civic_center_poi", "poi:lost_heaven_market")
    plateau = layout.get("plateau", {})

    text = re.sub(r"local LH_ANCHOR_X = -?\d+", f"local LH_ANCHOR_X = {int(anchor['x'])}", text, count=1)
    text = re.sub(r"local LH_ANCHOR_Y = -?\d+", f"local LH_ANCHOR_Y = {int(anchor['y'])}", text, count=1)
    text = re.sub(r"local LH_ANCHOR_Z = -?\d+", f"local LH_ANCHOR_Z = {int(anchor.get('z', 9))}", text, count=1)
    text = re.sub(r"local LH_GRID_SPACING = \d+", f"local LH_GRID_SPACING = {spacing}", text, count=1)
    text = re.sub(
        r'local LH_CIVIC_CENTER_POI = "[^"]+"',
        f'local LH_CIVIC_CENTER_POI = "{civic}"',
        text,
        count=1,
    )

    if plateau.get("theater_step_m") is not None:
        text = re.sub(
            r"local LH_THEATER_STEP_M = \d+",
            f"local LH_THEATER_STEP_M = {int(plateau['theater_step_m'])}",
            text,
            count=1,
        )
    if plateau.get("theater_half_cells") is not None:
        text = re.sub(
            r"local LH_THEATER_HALF_CELLS = \d+",
            f"local LH_THEATER_HALF_CELLS = {int(plateau['theater_half_cells'])}",
            text,
            count=1,
        )
    if plateau.get("terrain_mod_step_m") is not None:
        text = re.sub(
            r"local LH_TERRAIN_MOD_STEP_M = \d+",
            f"local LH_TERRAIN_MOD_STEP_M = {int(plateau['terrain_mod_step_m'])}",
            text,
            count=1,
        )
    if plateau.get("terrain_mod_half_cells") is not None:
        text = re.sub(
            r"local LH_TERRAIN_MOD_HALF_CELLS = \d+",
            f"local LH_TERRAIN_MOD_HALF_CELLS = {int(plateau['terrain_mod_half_cells'])}",
            text,
            count=1,
        )
    if plateau.get("lay_file"):
        text = re.sub(
            r'local LH_TERRAIN_LAY = "[^"]+"',
            f'local LH_TERRAIN_LAY = "{plateau["lay_file"]}"',
            text,
            count=1,
        )

    plan = generate_build_plan_lua(layout, catalog)
    text = re.sub(
        r"local LH_BUILD_PLAN = \{.*?\n\}",
        plan,
        text,
        count=1,
        flags=re.DOTALL,
    )

    if bump_version is not None:
        text = re.sub(r"local LH_BUILD_VERSION = \d+", f"local LH_BUILD_VERSION = {bump_version}", text, count=1)

    return text


def patch_hub_json(hub: dict, layout: dict, catalog: dict) -> dict:
    by_id = catalog_by_id(catalog)
    anchor = layout["anchor"]
    hub["world_anchor"] = {
        "x": int(anchor["x"]),
        "y": int(anchor["y"]),
        "z": int(anchor.get("z", 9)),
    }
    if "anchor_notes" in hub:
        hub["anchor_notes"]["ig_way"] = f"{int(anchor['x'])} {int(anchor['y'])}"

    starport = next(
        (b for b in layout.get("buildings", []) if b["poi_id"] == "poi:lost_heaven_starport"),
        None,
    )
    if starport and "new_player_spawn" in hub:
        hub["new_player_spawn"]["world"] = {
            "x": int(anchor["x"]) + int(starport.get("ox", 0)),
            "y": int(anchor["y"]) + int(starport.get("oy", 0)),
            "z": int(anchor.get("z", 9)),
            "heading": 0,
            "cell": 0,
        }

    offset_map = {b["poi_id"]: b for b in layout.get("buildings", [])}
    for poi in hub.get("poi_buildings", []):
        pid = poi.get("poi_id")
        if pid in offset_map:
            o = offset_map[pid]
            poi["world_offset"] = {"x": int(o.get("ox", 0)), "y": int(o.get("oy", 0)), "z": 0}
            if pid in by_id:
                poi["structure_template"] = by_id[pid]["template"]
        if pid == layout.get("civic_center_poi"):
            poi["world_offset"] = {"x": 0, "y": 0, "z": 0}

    if "auto_build" in hub:
        hub["auto_build"]["terrain"] = {
            "method": "scrapaltai_layout_editor",
            "layout_id": layout.get("layout_id", "custom"),
            "grid_spacing_m": layout.get("grid_spacing_m", 100),
            "civic_center_poi": layout.get("civic_center_poi"),
            **layout.get("plateau", {}),
        }
    return hub


def export_layout_from_screenplay(screenplay_path: Path) -> dict:
    text = screenplay_path.read_text(encoding="utf-8")
    anchor_x = int(re.search(r"local LH_ANCHOR_X = (-?\d+)", text).group(1))
    anchor_y = int(re.search(r"local LH_ANCHOR_Y = (-?\d+)", text).group(1))
    anchor_z = int(re.search(r"local LH_ANCHOR_Z = (-?\d+)", text).group(1))
    spacing = int(re.search(r"local LH_GRID_SPACING = (\d+)", text).group(1))
    civic_m = re.search(r'local LH_CIVIC_CENTER_POI = "([^"]+)"', text)
    civic = civic_m.group(1) if civic_m else "poi:lost_heaven_market"
    buildings = []
    for m in re.finditer(
        r'\{\s*poi_id\s*=\s*"([^"]+)"[^}]*ox\s*=\s*(-?\d+)[^}]*oy\s*=\s*(-?\d+)',
        text,
    ):
        buildings.append({"poi_id": m.group(1), "ox": int(m.group(2)), "oy": int(m.group(3))})
    local_tz = None
    if ZoneInfo is not None:
        try:
            local_tz = ZoneInfo(os.environ.get("LBG_LOCAL_TIMEZONE", "Europe/Paris"))
        except Exception:
            pass
    if local_tz is None:
        try:
            local_tz = datetime.now().astimezone().tzinfo or timezone.utc
        except Exception:
            local_tz = timezone.utc

    return {
        "schema_version": 1,
        "layout_id": "imported_from_screenplay",
        "label": "Import screenplay",
        "zone_id": "tatooine",
        "civic_center_poi": civic,
        "anchor": {"x": anchor_x, "y": anchor_y, "z": anchor_z},
        "grid_spacing_m": spacing,
        "plateau": {
            "theater_step_m": int(re.search(r"local LH_THEATER_STEP_M = (\d+)", text).group(1)),
            "theater_half_cells": int(re.search(r"local LH_THEATER_HALF_CELLS = (\d+)", text).group(1)),
            "terrain_mod_step_m": int(re.search(r"local LH_TERRAIN_MOD_STEP_M = (\d+)", text).group(1)),
            "terrain_mod_half_cells": int(re.search(r"local LH_TERRAIN_MOD_HALF_CELLS = (\d+)", text).group(1)),
            "lay_file": re.search(r'local LH_TERRAIN_LAY = "([^"]+)"', text).group(1),
        },
        "buildings": buildings,
        "exported_at": datetime.now(local_tz).isoformat(timespec="seconds"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Applique layout Scrapaltai → Lua + JSON hub")
    parser.add_argument("layout", nargs="?", type=Path, default=DEFAULT_LAYOUT)
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--screenplay", type=Path, default=SCREENPLAY)
    parser.add_argument("--hub", type=Path, default=HUB_JSON)
    parser.add_argument("--bump-version", type=int, default=None, help="ex. 8 pour forcer rebuild IG")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--export-from-screenplay",
        type=Path,
        metavar="OUT.json",
        help="Extraire layout actuel du screenplay vers JSON",
    )
    args = parser.parse_args()

    catalog = load_json(args.catalog)

    if args.export_from_screenplay:
        layout = export_layout_from_screenplay(args.screenplay)
        args.export_from_screenplay.write_text(
            json.dumps(layout, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"Exporté → {args.export_from_screenplay}")
        return 0

    layout = load_json(args.layout)
    errors = validate_layout(layout, catalog)
    if errors:
        print("Erreurs layout:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    sp_text = patch_screenplay(
        args.screenplay.read_text(encoding="utf-8"),
        layout,
        catalog,
        args.bump_version,
    )
    hub = patch_hub_json(load_json(args.hub), layout, catalog)

    if args.dry_run:
        print("=== LH_BUILD_PLAN (aperçu) ===")
        print(generate_build_plan_lua(layout, catalog))
        return 0

    args.screenplay.write_text(sp_text, encoding="utf-8")
    args.hub.write_text(json.dumps(hub, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK screenplay → {args.screenplay}")
    print(f"OK hub       → {args.hub}")
    if args.bump_version:
        print(f"LH_BUILD_VERSION = {args.bump_version}")
    print("Deploy: bash infra/scripts/deploy_core3_ia_bridge_vm.sh --restart")
    print("IG: lbg_we hub clean && lbg_we hub build")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
