#!/usr/bin/env python3
"""M4 — Export carte Tatooine + POI vers prime-client Godot."""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EDITOR = ROOT / "tools/world_editor"
DEFAULT_OUT = (
    Path(os.environ.get("PRIME_CLIENT", Path.home() / "projects/new_mmo/prime-client"))
    / "assets/maps"
)

# M8 — villes vanilla Scrapaltai (mesh retail) : masquées carte Godot ; hub actif = Lost Heaven
CITY_POIS = [
    {"id": "poi:lost_heaven", "kind": "hub", "label": "Lost Heaven", "x": 4749.0, "z": -737.0, "detail": False, "essential": True, "active": True},
    {
        "id": "poi:player_spawn",
        "kind": "spawn",
        "label": "Spawn joueur",
        "x": 4749.0,
        "z": -537.0,
        "detail": False,
        "essential": True,
        "active": True,
        "group": "lost_heaven",
    },
    {"id": "poi:mos_eisley", "kind": "city", "label": "Mos Eisley (purge)", "x": 3520.0, "z": -4800.0, "detail": False, "deprecated": True},
    {"id": "poi:anchorhead", "kind": "city", "label": "Anchorhead (purge)", "x": -100.0, "z": -5400.0, "detail": False, "deprecated": True},
    {"id": "poi:bestine", "kind": "city", "label": "Bestine (purge)", "x": -4000.0, "z": -6000.0, "detail": False, "deprecated": True},
]


def load_map_config() -> dict:
    return json.loads((EDITOR / "tatooine_map_config.json").read_text(encoding="utf-8"))


ESSENTIAL_POI_IDS = {
    "poi:lost_heaven_market",
    "poi:lost_heaven_bank",
    "poi:lost_heaven_blue_frog",
    "poi:lost_heaven_starport",
    "poi:player_spawn",
    "poi:lost_heaven",
}


def load_scrapaltai_world() -> dict:
    path = ROOT / "content/core3/scrapaltai_world.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_hub_pois() -> list[dict]:
    hub_path = ROOT / "content/core3/locations/lost_heaven_hub.json"
    if not hub_path.is_file():
        return []
    hub = json.loads(hub_path.read_text(encoding="utf-8"))
    anchor = hub.get("world_anchor") or {}
    ax = float(anchor.get("x", 0))
    az = float(anchor.get("y", 0))  # offset Y hub = axe Z monde (layout éditeur)
    out: list[dict] = []
    for poi in hub.get("poi_buildings", []):
        if not isinstance(poi, dict):
            continue
        off = poi.get("world_offset") or {}
        poi_id = str(poi.get("poi_id", ""))
        out.append(
            {
                "id": poi_id,
                "kind": str(poi.get("role", "building")),
                "label": str(poi.get("label", "")),
                "x": ax + float(off.get("x", 0)),
                "z": az + float(off.get("y", 0)),
                "detail": poi_id not in ESSENTIAL_POI_IDS,
                "essential": poi_id in ESSENTIAL_POI_IDS,
                "group": "lost_heaven",
            }
        )
    world = load_scrapaltai_world()
    frog = world.get("blue_frog") or {}
    if frog.get("enabled", True):
        off = frog.get("offset_from_anchor") or {}
        out.append(
            {
                "id": "poi:lost_heaven_blue_frog",
                "kind": "terminal",
                "label": "Blue Frog",
                "x": ax + float(off.get("x", 50)),
                "z": az + float(off.get("y", -50)),
                "detail": False,
                "essential": True,
                "group": "lost_heaven",
            }
        )
    return out


def export_hub_buildings(out_dir: Path) -> None:
    world = load_scrapaltai_world()
    anchor = world.get("world_anchor") or {}
    ax = float(anchor.get("x", 4749))
    az = float(anchor.get("y", -737))
    buildings: list[dict] = [
        {
            "id": "poi:lost_heaven_market",
            "kind": "shops",
            "label": "Bazar",
            "x": ax,
            "z": az,
            "size_m": 48,
            "essential": True,
        },
        {
            "id": "poi:lost_heaven_bank",
            "kind": "bank",
            "label": "Banque",
            "x": ax - 200,
            "z": az,
            "size_m": 40,
            "essential": True,
        },
    ]
    frog = world.get("blue_frog") or {}
    if frog.get("enabled", True):
        off = frog.get("offset_from_anchor") or {}
        buildings.append(
            {
                "id": "poi:lost_heaven_blue_frog",
                "kind": "terminal",
                "label": "Blue Frog",
                "x": ax + float(off.get("x", 50)),
                "z": az + float(off.get("y", -50)),
                "size_m": 10,
                "essential": True,
            }
        )
    spawn = world.get("new_player_spawn") or {}
    buildings.append(
        {
            "id": "poi:lost_heaven_starport",
            "kind": "starport_shuttle",
            "label": "Starport",
            "x": float(spawn.get("x", ax)),
            "z": float(spawn.get("y", az + 200)),
            "size_m": 36,
            "essential": True,
        }
    )
    doc = {
        "schema_version": 1,
        "hub": "lost_heaven",
        "anchor": {"x": ax, "z": az},
        "buildings": buildings,
    }
    (out_dir / "lost_heaven_buildings.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def export_maps(out_dir: Path, include_hub: bool = True) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = load_map_config()
    bounds = cfg.get("bounds", {})
    half = max(
        abs(float(bounds.get("minX", -6500))),
        abs(float(bounds.get("maxX", 6500))),
        abs(float(bounds.get("minY", -6500))),
        abs(float(bounds.get("maxY", 6500))),
    )

    godot_cfg = {
        "schema_version": 1,
        "planet": "tatooine",
        "display_name": "Scrapaltai",
        "hub_city": "Lost Heaven",
        "half_size": half,
        "bounds": bounds,
        "north_up": bool(cfg.get("north_up", True)),
        "texture": "res://assets/maps/tatooine.svg",
        "projection_scale": 0.5,
        "flip_texture_y": False,
        "notes": "M8 — planète entière jouable ; contenu actif = Lost Heaven",
    }
    (out_dir / "tatooine_map_config.json").write_text(
        json.dumps(godot_cfg, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    src_svg = EDITOR / "assets/tatooine_map.svg"
    if src_svg.is_file():
        shutil.copy2(src_svg, out_dir / "tatooine.svg")
    else:
        raise FileNotFoundError(f"Carte source absente: {src_svg}")

    pois = list(CITY_POIS)
    if include_hub:
        pois.extend(load_hub_pois())

    export_hub_buildings(out_dir)

    (out_dir / "tatooine_pois.json").write_text(
        json.dumps({"zone": "tatooine", "pois": pois}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"OK → {out_dir}")
    print(f"  tatooine.svg + config (half_size={half}) + {len(pois)} POI")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export carte Tatooine pour prime-client")
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Dossier Godot (défaut: {DEFAULT_OUT})",
    )
    parser.add_argument("--no-hub", action="store_true", help="Exclure POI Lost Heaven")
    args = parser.parse_args()
    export_maps(args.out, include_hub=not args.no_hub)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
