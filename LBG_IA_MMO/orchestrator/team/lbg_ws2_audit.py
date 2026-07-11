"""Audit readiness lbg-ws/2 (schémas, gateway, spec) — sans réseau obligatoire."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


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
