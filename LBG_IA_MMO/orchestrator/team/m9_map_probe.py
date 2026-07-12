"""Audit readiness jalon M9 — Scrapaltai planète + minimap + carte M (Prime Client 2D)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _prime_client_root() -> Path:
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


def _check_file(path: Path, *, gaps: list[str], label: str, checks: dict[str, Any]) -> bool:
    ok = path.is_file()
    checks[label] = ok
    if not ok:
        gaps.append(f"{label} absent ({path.name})")
    return ok


def audit_m9a_readiness() -> dict[str, Any]:
    """M9a — texture planète Scrapaltai, config carte, pipeline export/sync."""
    root = _repo_root()
    prime = _prime_client_root()
    gaps: list[str] = []
    checks: dict[str, Any] = {}

    jalon = root / "docs/jalon_m9_scrapaltai_map_minimap.md"
    _check_file(jalon, gaps=gaps, label="jalon_m9_doc", checks=checks)

    maps_dir = prime / "assets/maps"
    checks["maps_dir"] = maps_dir.is_dir()
    if not checks["maps_dir"]:
        gaps.append("assets/maps/ Prime Client absent")

    cfg = maps_dir / "tatooine_map_config.json"
    checks["map_config"] = cfg.is_file()
    if cfg.is_file():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            checks["scrapaltai_display_name"] = data.get("display_name") == "Scrapaltai"
            half = data.get("half_size")
            checks["planet_half_size_6500"] = half == 6500 or half == 6500.0
            if not checks["scrapaltai_display_name"]:
                gaps.append("tatooine_map_config.json sans display_name Scrapaltai")
        except (json.JSONDecodeError, OSError):
            checks["map_config_valid"] = False
            gaps.append("tatooine_map_config.json illisible")
    else:
        gaps.append("tatooine_map_config.json absent")

    svg = maps_dir / "tatooine.svg"
    png = maps_dir / "tatooine.png"
    checks["planet_texture"] = svg.is_file() or png.is_file()
    if not checks["planet_texture"]:
        gaps.append("texture planète tatooine.svg/png absente")

    export_py = root / "tools/map_export/export_scrapaltai_for_godot.py"
    sync_sh = root / "infra/scripts/sync_scrapaltai_poi_godot.sh"
    checks["export_pipeline"] = export_py.is_file()
    checks["poi_sync_script"] = sync_sh.is_file()
    if not checks["export_pipeline"]:
        gaps.append("export_scrapaltai_for_godot.py à créer (M9a-2)")
    if not checks["poi_sync_script"]:
        gaps.append("sync_scrapaltai_poi_godot.sh à créer (M9a-3)")

    poi_json = prime / "assets/maps/tatooine_pois.json"
    checks["poi_layer_data"] = poi_json.is_file()

    scrapaltai_srv = root / "content/core3/world_poi/scrapaltai.json"
    checks["server_scrapaltai_poi"] = scrapaltai_srv.is_file()
    if not checks["server_scrapaltai_poi"]:
        gaps.append("content/core3/world_poi/scrapaltai.json absent côté serveur")

    ok = len(gaps) == 0
    return {
        "track": "m9a_readiness",
        "ok": ok,
        "gaps": gaps,
        "checks": checks,
        "prime_client_root": str(prime),
        "hint": gaps[0] if gaps else None,
    }


def audit_m9b_readiness() -> dict[str, Any]:
    """M9b — minimap HUD coin écran."""
    prime = _prime_client_root()
    gaps: list[str] = []
    checks: dict[str, Any] = {}

    for rel, key in (
        ("scripts/minimap_hud.gd", "minimap_script"),
        ("scenes/ui/minimap_hud.tscn", "minimap_scene"),
    ):
        _check_file(prime / rel, gaps=gaps, label=key, checks=checks)

    cfg = prime / "config/minimap_config.json"
    checks["minimap_config"] = cfg.is_file()
    if not checks["minimap_config"]:
        gaps.append("config/minimap_config.json absent (M9b-5)")

    main_tscn = prime / "scenes/main.tscn"
    checks["main_scene"] = main_tscn.is_file()
    if main_tscn.is_file():
        text = main_tscn.read_text(encoding="utf-8", errors="ignore")
        checks["minimap_in_main"] = "minimap_hud" in text.lower() or "MinimapHud" in text
        if not checks["minimap_in_main"]:
            gaps.append("MinimapHud non branchée dans main.tscn (M9b-3)")
    else:
        gaps.append("scenes/main.tscn absent")

    smoke = _repo_root() / "infra/scripts/smoke_prime_client_minimap.sh"
    checks["smoke_minimap"] = smoke.is_file()
    if not checks["smoke_minimap"]:
        gaps.append("smoke_prime_client_minimap.sh à créer")

    ok = len(gaps) == 0
    return {
        "track": "m9b_readiness",
        "ok": ok,
        "gaps": gaps,
        "checks": checks,
        "prime_client_root": str(prime),
        "hint": gaps[0] if gaps else None,
    }


def audit_m9c_readiness() -> dict[str, Any]:
    """M9c — carte planétaire M + waypoints."""
    prime = _prime_client_root()
    gaps: list[str] = []
    checks: dict[str, Any] = {}

    for rel, key in (
        ("scripts/planet_map_panel.gd", "planet_map_script"),
        ("scenes/ui/planet_map_panel.tscn", "planet_map_scene"),
        ("scripts/waypoint_store.gd", "waypoint_store"),
        ("assets/maps/locations_tree.json", "locations_tree"),
    ):
        _check_file(prime / rel, gaps=gaps, label=key, checks=checks)

    wp_cfg = prime / "config/waypoints.json"
    checks["waypoints_config"] = wp_cfg.is_file()
    if not checks["waypoints_config"]:
        gaps.append("config/waypoints.json absent (M9c-3)")

    smoke = _repo_root() / "infra/scripts/smoke_prime_client_planet_map.sh"
    checks["smoke_planet_map"] = smoke.is_file()
    if not checks["smoke_planet_map"]:
        gaps.append("smoke_prime_client_planet_map.sh à créer")

    main_tscn = prime / "scenes/main.tscn"
    if main_tscn.is_file():
        text = main_tscn.read_text(encoding="utf-8", errors="ignore")
        checks["planet_map_in_main"] = "planet_map_panel" in text.lower() or "PlanetMapPanel" in text
        if not checks["planet_map_in_main"]:
            gaps.append("PlanetMapPanel non branchée dans main.tscn (M9c-3)")

    ok = len(gaps) == 0
    return {
        "track": "m9c_readiness",
        "ok": ok,
        "gaps": gaps,
        "checks": checks,
        "prime_client_root": str(prime),
        "hint": gaps[0] if gaps else None,
    }


def audit_m9_full_readiness() -> dict[str, Any]:
    """M9 complet — agrège M9a + M9b + M9c."""
    probes = [audit_m9a_readiness(), audit_m9b_readiness(), audit_m9c_readiness()]
    gaps: list[str] = []
    for p in probes:
        gaps.extend(p.get("gaps") or [])
    ok = all(p.get("ok") for p in probes)
    return {
        "track": "m9_full_readiness",
        "ok": ok,
        "gaps": gaps,
        "probes": probes,
        "hint": gaps[0] if gaps else None,
    }
