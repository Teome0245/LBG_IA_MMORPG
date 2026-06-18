#!/usr/bin/env python3
"""Import coords IG (dump chat, session VM, export scrapaltai) → layout JSON v2."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_CATALOG = Path(__file__).resolve().parent / "scrapaltai_poi_catalog.json"


def parse_dump_text(text: str) -> dict | None:
    for line in text.splitlines():
        if "dump" in line.lower() or "x=" in line:
            m = dict(re.findall(r"(\w+)=([^\s]+)", line))
            if "x" in m:
                return {
                    "x": float(m["x"]),
                    "y": float(m.get("y", 0)),
                    "z": float(m.get("z", 0)),
                    "cell": int(m.get("cell", 0) or 0),
                    "heading": float(m.get("heading", 0)),
                    "zone": m.get("zone", "tatooine"),
                }
    text = text.strip()
    if text.startswith("{"):
        j = json.loads(text)
        if "x" in j:
            return j
        if "last_dump" in j:
            return j["last_dump"]
        if "world" in j:
            w = j["world"]
            return {"x": w["x"], "y": w["y"], "z": w.get("z", 0), "heading": w.get("heading", 0)}
    return None


def parse_session_text(text: str) -> dict:
    sess: dict = {"last_dump": None, "poi": {}}
    for line in text.splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if k == "last_x":
            sess.setdefault("last_dump", {})["x"] = float(v)
        elif k == "last_y":
            sess.setdefault("last_dump", {})["y"] = float(v)
        elif k == "last_z":
            sess.setdefault("last_dump", {})["z"] = float(v)
        elif k == "last_heading":
            sess.setdefault("last_dump", {})["heading"] = float(v)
        elif k.startswith("wpoi."):
            poi_id = k[5:]
            parts = v.split(",")
            if len(parts) >= 5:
                sess["poi"][poi_id] = {
                    "template": parts[0],
                    "x": float(parts[1]),
                    "y": float(parts[2]),
                    "z": float(parts[3]),
                    "heading": float(parts[4]),
                }
    return sess


def load_layout(path: Path | None) -> dict:
    if path and path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "schema_version": 2,
        "layout_id": "imported",
        "label": "Import IG",
        "zone_id": "tatooine",
        "civic_center_poi": "poi:lost_heaven_market",
        "anchor": {"x": 4809, "y": -802, "z": 9},
        "grid_spacing_m": 100,
        "plateau": {
            "theater_step_m": 48,
            "theater_half_cells": 6,
            "terrain_mod_step_m": 48,
            "terrain_mod_half_cells": 6,
            "lay_file": "terrain/poi_small.lay",
        },
        "buildings": [],
    }


def world_to_offset(wx: float, wy: float, anchor: dict) -> tuple[int, int]:
    return int(round(wx - anchor["x"])), int(round(wy - anchor["y"]))


def snap_val(v: int, g: int) -> int:
    return int(round(v / g) * g)


def apply_pois(layout: dict, pois: dict, snap_grid: bool) -> None:
    g = layout.get("grid_spacing_m", 100)
    by_id = {b["poi_id"]: b for b in layout.get("buildings", [])}
    for poi_id, p in pois.items():
        ox, oy = world_to_offset(p["x"], p["y"], layout["anchor"])
        if snap_grid:
            ox, oy = snap_val(ox, g), snap_val(oy, g)
        if poi_id in by_id:
            by_id[poi_id]["ox"] = ox
            by_id[poi_id]["oy"] = oy
        else:
            layout.setdefault("buildings", []).append({"poi_id": poi_id, "ox": ox, "oy": oy})
            by_id[poi_id] = layout["buildings"][-1]


def ensure_catalog_buildings(layout: dict, catalog_path: Path) -> None:
    if not catalog_path.is_file():
        return
    cat = json.loads(catalog_path.read_text(encoding="utf-8"))
    by_id = {b["poi_id"] for b in layout.get("buildings", [])}
    for p in cat.get("pois", []):
        pid = p["poi_id"]
        if pid not in by_id:
            layout.setdefault("buildings", []).append({"poi_id": pid, "ox": 0, "oy": 0})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path, help="Fichier dump/session/export JSON")
    ap.add_argument("-o", "--output", type=Path, help="Layout JSON de sortie")
    ap.add_argument("--layout", type=Path, help="Layout de base à patcher")
    ap.add_argument("--anchor-only", action="store_true", help="Met à jour uniquement l'ancre")
    ap.add_argument("--snap", action="store_true", help="Snap offsets sur la grille")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    raw = args.input.read_text(encoding="utf-8")
    layout = load_layout(args.layout)

    if args.input.suffix.lower() == ".json" and '"pois"' in raw:
        data = json.loads(raw)
        if "anchor" in data:
            layout["anchor"].update(data["anchor"])
        pois = {}
        for p in data.get("pois", []):
            w = p.get("world", p)
            pois[p["poi_id"]] = {"x": w["x"], "y": w["y"]}
        if not args.anchor_only:
            apply_pois(layout, pois, args.snap)
    elif "wpoi." in raw or raw.strip().startswith("active="):
        sess = parse_session_text(raw)
        if sess.get("last_dump"):
            layout["anchor"]["x"] = int(round(sess["last_dump"]["x"]))
            layout["anchor"]["y"] = int(round(sess["last_dump"]["y"]))
            if "z" in sess["last_dump"]:
                layout["anchor"]["z"] = sess["last_dump"]["z"]
        if not args.anchor_only and sess.get("poi"):
            apply_pois(layout, sess["poi"], args.snap)
    else:
        dump = parse_dump_text(raw)
        if dump is None:
            print("Format non reconnu", file=sys.stderr)
            return 1
        layout["anchor"]["x"] = int(round(dump["x"]))
        layout["anchor"]["y"] = int(round(dump["y"]))
        if "z" in dump:
            layout["anchor"]["z"] = dump["z"]

    ensure_catalog_buildings(layout, DEFAULT_CATALOG)
    layout["schema_version"] = 2

    out = args.output or args.input.with_suffix(".layout.json")
    if args.dry_run:
        print(json.dumps(layout, indent=2, ensure_ascii=False))
        return 0
    out.write_text(json.dumps(layout, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Écrit {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
