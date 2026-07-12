#!/usr/bin/env python3
"""Export Scrapaltai (World Editor + POI serveur) → assets Prime Client Godot."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Taille emprise bâtiment hub (m) — Godot HubBuildingsLayer
SIZE_M_BY_ROLE: dict[str, float] = {
    "starport_shuttle": 36.0,
    "shops": 48.0,
    "market": 48.0,
    "bank": 40.0,
    "terminal": 10.0,
    "blue_frog": 10.0,
    "cantina": 32.0,
    "inn": 32.0,
    "trainer_artisan": 28.0,
    "trainers_combat": 36.0,
    "clinic": 28.0,
    "mission_terminal": 24.0,
    "town_hall": 40.0,
    "npc_housing_block": 24.0,
    "city_gate": 64.0,
    "hub": 56.0,
}

ESSENTIAL_ROLES = frozenset({"starport_shuttle", "bank", "shops", "market", "hub", "spawn"})


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_prime_client() -> Path:
    import os

    raw = os.environ.get("LBG_PRIME_CLIENT_ROOT", "").strip()
    if raw:
        return Path(raw)
    new_mmo = os.environ.get("LBG_NEW_MMO_ROOT", "").strip()
    if new_mmo:
        candidate = Path(new_mmo) / "prime-client"
        if candidate.is_dir():
            return candidate
    for candidate in (
        Path("/home/sdesh/projects/new_mmo/prime-client"),
        Path("/opt/new_mmo/prime-client"),
    ):
        if candidate.is_dir():
            return candidate
    return Path("/home/sdesh/projects/new_mmo/prime-client")


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy_planet_texture(editor_root: Path, maps_out: Path, *, dry_run: bool) -> bool:
    src = editor_root / "assets/tatooine_map.svg"
    dst = maps_out / "tatooine.svg"
    if not src.is_file():
        print(f"WARN texture source absente: {src}", file=sys.stderr)
        return False
    if dry_run:
        print(f"DRY copy {src} -> {dst}")
        return True
    shutil.copy2(src, dst)
    print(f"OK texture -> {dst}")
    return True


def ensure_map_config(maps_out: Path, *, dry_run: bool) -> None:
    dst = maps_out / "tatooine_map_config.json"
    if dst.is_file():
        return
    payload = {
        "schema_version": 1,
        "planet": "tatooine",
        "display_name": "Scrapaltai",
        "hub_city": "Lost Heaven",
        "half_size": 6500.0,
        "bounds": {"minX": -6500, "maxX": 6500, "minY": -6500, "maxY": 6500},
        "north_up": True,
        "texture": "res://assets/maps/tatooine.svg",
        "projection_scale": 0.5,
        "flip_texture_y": False,
        "notes": "Généré export_scrapaltai_for_godot.py",
    }
    if dry_run:
        print(f"DRY write {dst}")
        return
    write_json(dst, payload)
    print(f"OK config -> {dst}")


def _hub_role_map(hub: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in hub.get("poi_buildings") or []:
        if not isinstance(item, dict):
            continue
        poi_id = str(item.get("poi_id") or "")
        if poi_id:
            out[poi_id] = item
    return out


def _swg_xz(world: dict[str, Any]) -> tuple[float, float]:
    return float(world.get("x", 0.0)), float(world.get("y", 0.0))


def _poi_from_hub_entry(poi_id: str, meta: dict[str, Any], x: float, z: float) -> dict[str, Any]:
    role = str(meta.get("role") or "poi")
    label = str(meta.get("label") or poi_id.split(":")[-1].replace("_", " ").title())
    essential = role in ESSENTIAL_ROLES or poi_id.endswith("_starport") or poi_id.endswith("_market")
    detail = not essential and role not in {"hub", "spawn"}
    return {
        "id": poi_id,
        "kind": role,
        "label": label,
        "x": x,
        "z": z,
        "detail": detail,
        "essential": essential,
        "active": True,
        "group": "lost_heaven",
    }


def build_godot_pois(
    scrapaltai: dict[str, Any],
    hub: dict[str, Any],
    existing_pois: dict[str, Any] | None,
) -> dict[str, Any]:
    role_map = _hub_role_map(hub)
    anchor = hub.get("world_anchor") or {}
    ax, az = float(anchor.get("x", 4749)), float(anchor.get("y", -737))

    pois: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Hub + spawn depuis location
    pois.append(
        {
            "id": "poi:lost_heaven",
            "kind": "hub",
            "label": str(hub.get("display_city") or "Lost Heaven"),
            "x": ax,
            "z": az,
            "detail": False,
            "essential": True,
            "active": True,
        }
    )
    seen.add("poi:lost_heaven")

    spawn = hub.get("new_player_spawn") or {}
    spawn_w = spawn.get("world") or {}
    if spawn_w:
        pois.append(
            {
                "id": "poi:player_spawn",
                "kind": "spawn",
                "label": str(spawn.get("label") or "Spawn joueur"),
                "x": float(spawn_w.get("x", ax)),
                "z": float(spawn_w.get("y", az)),
                "detail": False,
                "essential": True,
                "active": True,
                "group": "lost_heaven",
            }
        )
        seen.add("poi:player_spawn")

    for item in scrapaltai.get("pois") or []:
        if not isinstance(item, dict):
            continue
        poi_id = str(item.get("poi_id") or "")
        if not poi_id or poi_id in seen:
            continue
        world = item.get("world") or {}
        x, z = _swg_xz(world)
        meta = role_map.get(poi_id, {})
        pois.append(_poi_from_hub_entry(poi_id, meta, x, z))
        seen.add(poi_id)

    # Villes legacy deprecated (carte planète entière)
    if existing_pois:
        for old in existing_pois.get("pois") or []:
            if not isinstance(old, dict):
                continue
            if not old.get("deprecated"):
                continue
            oid = str(old.get("id") or "")
            if oid and oid not in seen:
                pois.append(old)
                seen.add(oid)

    return {
        "zone": str(scrapaltai.get("zone_id") or "tatooine"),
        "display_name": str(scrapaltai.get("display_zone") or "Scrapaltai"),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source": "content/core3/world_poi/scrapaltai.json",
        "pois": pois,
    }


def build_hub_buildings(scrapaltai: dict[str, Any], hub: dict[str, Any]) -> dict[str, Any]:
    role_map = _hub_role_map(hub)
    anchor = hub.get("world_anchor") or {}
    ax, az = float(anchor.get("x", 4749)), float(anchor.get("y", -737))

    buildings: list[dict[str, Any]] = []
    for item in scrapaltai.get("pois") or []:
        if not isinstance(item, dict):
            continue
        poi_id = str(item.get("poi_id") or "")
        meta = role_map.get(poi_id, {})
        world = item.get("world") or {}
        x, z = _swg_xz(world)
        role = str(meta.get("role") or "poi")
        label = str(meta.get("label") or poi_id.split(":")[-1].replace("_", " ").title())
        buildings.append(
            {
                "id": poi_id,
                "kind": role,
                "label": label,
                "x": x,
                "z": z,
                "size_m": SIZE_M_BY_ROLE.get(role, 32.0),
                "essential": role in ESSENTIAL_ROLES or poi_id.endswith("_starport"),
            }
        )

    return {
        "schema_version": 1,
        "hub": "lost_heaven",
        "anchor": {"x": ax, "z": az},
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "buildings": buildings,
    }


def sync_poi_to_godot(
    root: Path,
    maps_out: Path,
    *,
    dry_run: bool,
) -> dict[str, str]:
    scrapaltai_path = root / "content/core3/world_poi/scrapaltai.json"
    hub_path = root / "content/core3/locations/lost_heaven_hub.json"
    scrapaltai = load_json(scrapaltai_path)
    hub = load_json(hub_path)
    if not scrapaltai:
        raise FileNotFoundError(f"POI serveur absent: {scrapaltai_path}")
    if not hub:
        raise FileNotFoundError(f"Hub location absent: {hub_path}")

    existing = load_json(maps_out / "tatooine_pois.json")
    pois_payload = build_godot_pois(scrapaltai, hub, existing or None)
    buildings_payload = build_hub_buildings(scrapaltai, hub)

    pois_dst = maps_out / "tatooine_pois.json"
    bld_dst = maps_out / "lost_heaven_buildings.json"
    if dry_run:
        print(f"DRY write {pois_dst} ({len(pois_payload['pois'])} POI)")
        print(f"DRY write {bld_dst} ({len(buildings_payload['buildings'])} bâtiments)")
    else:
        write_json(pois_dst, pois_payload)
        write_json(bld_dst, buildings_payload)
        print(f"OK POI -> {pois_dst} ({len(pois_payload['pois'])} entrées)")
        print(f"OK bâtiments -> {bld_dst} ({len(buildings_payload['buildings'])} entrées)")

    return {"pois": str(pois_dst), "buildings": str(bld_dst)}


def run_export(
    *,
    root: Path,
    editor_root: Path,
    prime_client: Path,
    poi_only: bool,
    dry_run: bool,
) -> int:
    maps_out = prime_client / "assets/maps"
    if not poi_only:
        copy_planet_texture(editor_root, maps_out, dry_run=dry_run)
        ensure_map_config(maps_out, dry_run=dry_run)
    sync_poi_to_godot(root, maps_out, dry_run=dry_run)
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export Scrapaltai → Prime Client Godot (M9a)")
    p.add_argument("--repo-root", type=Path, default=repo_root(), help="Racine LBG_IA_MMO")
    p.add_argument(
        "--editor-root",
        type=Path,
        default=None,
        help="Racine world_editor (défaut: repo-root/tools/world_editor)",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Racine prime-client (défaut: LBG_PRIME_CLIENT_ROOT ou new_mmo/prime-client)",
    )
    p.add_argument("--poi-only", action="store_true", help="Sync POI/bâtiments sans copier la texture")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root: Path = args.repo_root
    editor_root: Path = args.editor_root or (root / "tools/world_editor")
    prime_client: Path = args.out or default_prime_client()
    try:
        return run_export(
            root=root,
            editor_root=editor_root,
            prime_client=prime_client,
            poi_only=args.poi_only,
            dry_run=args.dry_run,
        )
    except FileNotFoundError as exc:
        print(f"ERREUR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
