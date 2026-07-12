"""Audit readiness lbg-ws/2 (schémas, gateway, spec) — sans réseau obligatoire."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _new_mmo_root() -> Path:
    raw = os.environ.get("LBG_NEW_MMO_ROOT", "").strip()
    if raw:
        return Path(raw)
    for candidate in (Path("/opt/new_mmo"), Path("/home/sdesh/projects/new_mmo")):
        if candidate.is_dir():
            return candidate
    return Path("/home/sdesh/projects/new_mmo")


def _zb0_header_paths() -> list[Path]:
    root = _new_mmo_root()
    return [
        root / "lbg-mmo/server-core3/server/lbg/LbgZoneBridge.h",
        root / "lbg-mmo/server-core3/server/lbg/LbgZoneBridge.cpp",
        root / "lbg-mmo/server-core3/server/lbg/LbgZoneBridgeReadOnly.cpp",
        root / "lbg-mmo/server-core3/server/lbg/LbgZoneBridgeTickTask.h",
        root / "lbg-mmo/server-core3/server/lbg/LbgZoneBridgeInit.cpp",
    ]


def audit_zb0_readiness() -> dict[str, Any]:
    """Audit ZB-0 — header LbgZoneBridge + spec (sans build C++ obligatoire)."""
    root = _repo_root()
    gaps: list[str] = []
    checks: dict[str, Any] = {}

    spec = root / "docs/core3_zone_bridge_spec.md"
    checks["spec_zone_bridge"] = spec.is_file()

    header_paths = _zb0_header_paths()
    for i, hp in enumerate(header_paths):
        checks[f"zb0_file_{i}"] = hp.is_file()
    checks["zb0_header"] = header_paths[0].is_file() if header_paths else False
    checks["zb0_impl"] = header_paths[1].is_file() if len(header_paths) > 1 else False
    checks["zb0_readonly_impl"] = header_paths[2].is_file() if len(header_paths) > 2 else False
    checks["zb0_tick_task"] = header_paths[3].is_file() if len(header_paths) > 3 else False
    checks["zb0_init"] = header_paths[4].is_file() if len(header_paths) > 4 else False

    cmake = _new_mmo_root() / "lbg-mmo/server-core3/CMakeLists.txt"
    checks["cmake_lbg_sources"] = False
    if cmake.is_file():
        cmake_text = cmake.read_text(encoding="utf-8", errors="ignore")
        checks["cmake_lbg_sources"] = "server/lbg/*.cpp" in cmake_text

    if not checks["spec_zone_bridge"]:
        gaps.append("spec core3_zone_bridge_spec.md manquante")
    if not checks.get("zb0_header"):
        gaps.append("LbgZoneBridge.h absent (ZB-0)")
    if checks.get("zb0_header") and not checks.get("zb0_impl"):
        gaps.append("LbgZoneBridge.cpp absent (ZB-0 squelette)")
    if checks.get("zb0_header") and not checks.get("zb0_readonly_impl"):
        gaps.append("LbgZoneBridgeReadOnly.cpp absent (ZB-0 lecture seule)")
    if checks.get("zb0_header") and not checks.get("zb0_tick_task"):
        gaps.append("LbgZoneBridgeTickTask absent (ZB-0 tick 20 Hz)")
    if checks.get("zb0_header") and not checks.get("cmake_lbg_sources"):
        gaps.append("CMakeLists.txt sans server/lbg/*.cpp")

    zone_server = _new_mmo_root() / "lbg-mmo/server-core3/server/zone/ZoneServerImplementation.cpp"
    checks["zone_server_impl_path"] = zone_server.is_file()
    if zone_server.is_file():
        text = zone_server.read_text(encoding="utf-8", errors="ignore")
        checks["zone_server_zb_hook"] = "startZoneBridgeTick" in text
        if not checks["zone_server_zb_hook"]:
            gaps.append("hook ZoneServer startManagers sans startZoneBridgeTick (ZB-0)")

    hook_ok = bool(checks.get("zone_server_zb_hook"))
    files_ok = bool(checks.get("zb0_header")) and bool(checks.get("zb0_readonly_impl")) and bool(
        checks.get("zb0_tick_task")
    )
    ok = bool(checks.get("spec_zone_bridge")) and files_ok and hook_ok and bool(checks.get("cmake_lbg_sources"))

    next_actions: list[str] = []
    if not checks.get("zb0_header"):
        next_actions.append("Créer server/lbg/LbgZoneBridge.h (interface lecture seule)")
    elif not hook_ok:
        next_actions.append("Hook startZoneBridgeTick dans ZoneServerImplementation::startManagers")
    elif not checks.get("cmake_lbg_sources"):
        next_actions.append("Ajouter server/lbg/*.cpp au CMakeLists server-core3")
    elif ok:
        next_actions.append("Compiler Core3 (Vulcan) puis ZB-1 : export JSON/SHM 20 Hz vers lbg_gateway")
    else:
        next_actions.append("Compléter LbgZoneBridgeReadOnly + LbgZoneBridgeTickTask (ZB-0)")

    return {
        "track": "zb0_readiness",
        "ok": ok,
        "checks": checks,
        "gaps": gaps,
        "next_actions": next_actions[:4],
        "new_mmo_root": str(_new_mmo_root()),
    }


def _probe_zone_bridge_feed_ssh(host: str) -> dict[str, Any]:
    """Sonde feed ZB-1 sur Prime via SSH (orchestrateur 140 → VM 246)."""
    import json
    import subprocess

    user = os.environ.get("LBG_ZONE_BRIDGE_PROBE_USER", "lbg").strip()
    json_path = os.environ.get(
        "LBG_ZONE_BRIDGE_JSON_PATH",
        "/opt/lbg-new-mmo-clean/MMOCoreORB/bin/ia_bridge/zone_bridge_live.json",
    )
    cmd = (
        f"python3 -c \"import json,time,os;"
        f"p='{json_path}';"
        f"out={{'track':'zb1_live_feed','ok':False,'checks':{{'json_path':p,'remote':True}}}};"
        f"import pathlib; p=pathlib.Path(p);"
        f"out['checks']['file_exists']=p.is_file();"
        f"out['checks']['live_enabled']=True;"
        f"import time as t;"
        f"out['checks']['mtime_age_s']=round(t.time()-p.stat().st_mtime,3) if p.is_file() else None;"
        f"data=json.loads(p.read_text()) if p.is_file() else None;"
        f"out['ok']=isinstance(data,dict) and data.get('type')=='zone_state';"
        f"out['checks']['tick']=data.get('tick') if isinstance(data,dict) else None;"
        f"out['checks']['zone']=data.get('zone') if isinstance(data,dict) else None;"
        f"print(json.dumps(out))\""
    )
    try:
        proc = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", f"{user}@{host}", cmd],
            capture_output=True,
            text=True,
            timeout=20.0,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            data = json.loads(proc.stdout.strip().splitlines()[-1])
            if isinstance(data, dict):
                return data
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
        pass
    return {
        "track": "zb1_live_feed",
        "ok": False,
        "checks": {"json_path": json_path, "remote_host": host},
        "gaps": ["sonde SSH feed ZB-1 échouée"],
    }


def _zb1_export_paths() -> list[Path]:
    root = _new_mmo_root()
    return [
        root / "lbg-mmo/server-core3/server/lbg/LbgZoneBridgeJsonExport.h",
        root / "lbg-mmo/server-core3/server/lbg/LbgZoneBridgeJsonExport.cpp",
    ]


def audit_zb1_readiness(*, probe_live_feed: bool = True) -> dict[str, Any]:
    """Audit ZB-1 — export JSON C++ + module gateway live."""
    gaps: list[str] = []
    checks: dict[str, Any] = {}
    zb0 = audit_zb0_readiness()
    checks["zb0_ok"] = bool(zb0.get("ok"))

    export_paths = _zb1_export_paths()
    checks["zb1_json_export_h"] = export_paths[0].is_file()
    checks["zb1_json_export_cpp"] = export_paths[1].is_file() if len(export_paths) > 1 else False

    tick_task = _new_mmo_root() / "lbg-mmo/server-core3/server/lbg/LbgZoneBridgeTickTask.h"
    if tick_task.is_file():
        tt = tick_task.read_text(encoding="utf-8", errors="ignore")
        checks["zb1_tick_publishes_json"] = "publishZoneBridgeJson" in tt
    else:
        checks["zb1_tick_publishes_json"] = False

    gw_feed = _repo_root() / "services/lbg_gateway/zone_bridge_feed.py"
    checks["gateway_zone_bridge_feed"] = gw_feed.is_file()

    if not checks.get("zb1_json_export_cpp"):
        gaps.append("LbgZoneBridgeJsonExport.cpp absent (ZB-1)")
    if not checks.get("zb1_tick_publishes_json"):
        gaps.append("LbgZoneBridgeTickTask n'appelle pas publishZoneBridgeJson")
    if not checks.get("gateway_zone_bridge_feed"):
        gaps.append("services/lbg_gateway/zone_bridge_feed.py absent")

    live_probe: dict[str, Any] | None = None
    if probe_live_feed:
        remote_host = os.environ.get("LBG_ZONE_BRIDGE_PROBE_HOST", "").strip()
        if remote_host:
            live_probe = _probe_zone_bridge_feed_ssh(remote_host)
            checks["live_feed_ok"] = bool(live_probe.get("ok"))
            if not live_probe.get("ok"):
                gaps.extend(live_probe.get("gaps") or ["feed live JSON absent sur Prime (SSH)"])
        elif checks.get("gateway_zone_bridge_feed"):
            try:
                import sys

                root_s = str(_repo_root())
                if root_s not in sys.path:
                    sys.path.insert(0, root_s)
                from services.lbg_gateway.zone_bridge_feed import probe_zone_bridge_feed

                live_probe = probe_zone_bridge_feed()
                checks["live_feed_ok"] = bool(live_probe.get("ok"))
                if not live_probe.get("ok"):
                    gaps.append("feed live JSON absent ou périmé (compile + Prime requis)")
            except ImportError as e:
                checks["live_feed_ok"] = False
                gaps.append(f"import zone_bridge_feed: {e}")

    code_ok = bool(checks.get("zb1_json_export_cpp")) and bool(checks.get("zb1_tick_publishes_json"))
    code_ok = code_ok and bool(checks.get("gateway_zone_bridge_feed"))
    ok = bool(checks.get("zb0_ok")) and code_ok
    if probe_live_feed:
        if live_probe is not None:
            ok = ok and bool(live_probe.get("ok"))
            checks["runtime_feed"] = live_probe.get("checks")
        elif checks.get("live_feed_ok") is False:
            ok = False

    next_actions: list[str] = []
    if not checks.get("zb0_ok"):
        next_actions.append("Finaliser ZB-0 avant ZB-1")
    elif not code_ok:
        next_actions.append("Implémenter LbgZoneBridgeJsonExport + zone_bridge_feed gateway")
    elif live_probe and not live_probe.get("ok"):
        next_actions.append("Compiler Core3 (Vulcan) et redémarrer Prime — feed JSON 20 Hz")
    else:
        next_actions.append("ZB-2 : injection move validé depuis gateway")

    return {
        "track": "zb1_readiness",
        "ok": ok,
        "code_ok": code_ok,
        "checks": checks,
        "gaps": gaps,
        "live_probe": live_probe,
        "next_actions": next_actions[:4],
        "zb0": zb0,
    }


def audit_lbg_ws2_readiness() -> dict[str, Any]:
    root = _repo_root()
    gaps: list[str] = []
    checks: dict[str, Any] = {}

    schema_zone = root / "docs/schemas/lbg-ws/server.zone_state_v2.schema.json"
    schema_cmd = root / "docs/schemas/lbg-ws/client.zone_command_v2.schema.json"
    spec = root / "docs/core3_zone_bridge_spec.md"
    gateway_main = root / "services/lbg_gateway/main.py"
    ws2_mod = root / "services/lbg_gateway/lbg_ws2.py"

    checks["schema_zone_state_v2"] = schema_zone.is_file()
    checks["schema_zone_command_v2"] = schema_cmd.is_file()
    checks["spec_zone_bridge"] = spec.is_file()
    checks["gateway_main"] = gateway_main.is_file()
    checks["lbg_ws2_module"] = ws2_mod.is_file()

    if not checks["schema_zone_state_v2"]:
        gaps.append("schéma server.zone_state_v2 manquant")
    if not checks["lbg_ws2_module"]:
        gaps.append("module services/lbg_gateway/lbg_ws2.py manquant")
    else:
        try:
            import sys

            root_s = str(root)
            if root_s not in sys.path:
                sys.path.insert(0, root_s)
            from services.lbg_gateway.lbg_ws2 import build_zone_state_v2, supported_protos

            sample = build_zone_state_v2(
                zone="tatooine",
                tick=1,
                entities=[{"id": "player:Teome", "kind": "player", "name": "Teome", "pos": [0.0, 0.0, 0.0]}],
                your_character_id=1,
            )
            checks["sample_zone_state_v2"] = sample.get("proto") == "lbg-ws/2"
            checks["supported_protos"] = supported_protos()
            if not checks["sample_zone_state_v2"]:
                gaps.append("build_zone_state_v2 ne produit pas proto lbg-ws/2")
        except Exception as e:
            checks["lbg_ws2_import_error"] = str(e)
            gaps.append(f"import lbg_ws2: {e}")

    preview_on = os.environ.get("LBG_GATEWAY_WS2_PREVIEW", "1").strip().lower() in ("1", "true", "yes", "on")
    checks["ws2_preview_env"] = preview_on
    if gateway_main.is_file():
        text = gateway_main.read_text(encoding="utf-8", errors="ignore")
        checks["gateway_ws2_handler"] = "lbg-ws/2" in text or "lbg_ws2" in text
        if not checks["gateway_ws2_handler"]:
            gaps.append("gateway main.py sans branche lbg-ws/2")

    readiness_score = sum(1 for k, v in checks.items() if v is True) / max(len(checks), 1)
    ok = len(gaps) == 0 or (checks.get("lbg_ws2_module") and checks.get("schema_zone_state_v2"))

    return {
        "track": "lbg_ws2_readiness",
        "ok": ok,
        "readiness_score": round(readiness_score, 2),
        "checks": checks,
        "gaps": gaps,
        "next_actions": _suggest_next_actions(gaps),
    }


def _suggest_next_actions(gaps: list[str]) -> list[str]:
    actions: list[str] = []
    if any("gateway" in g for g in gaps):
        actions.append("Étendre lbg_gateway pour négocier proto lbg-ws/2 (preview lecture snapshots)")
    if any("lbg_ws2" in g or "schéma" in g for g in gaps):
        actions.append("Compléter schémas JSON et module lbg_ws2.py")
    if not actions:
        actions.append("Implémenter LbgZoneBridge C++ ZB-0 (hook ZoneServer lecture seule)")
    return actions[:4]
