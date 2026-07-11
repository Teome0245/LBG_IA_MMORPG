"""Sonde L1 Infographiste IA — manifest GLB Godot + pipeline assets (en cours)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from team.models import TeamTask


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def godot_client_root() -> Path:
    raw = os.environ.get("LBG_INFOGRAPHISTE_GODOT_ROOT", "").strip()
    if raw:
        return Path(raw)
    return _repo_root() / "lbg_client_godot"


def _collect_manifest_glb_paths(manifest: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for key in ("species", "mobile_template", "pilot_id", "world", "props"):
        block = manifest.get(key)
        if isinstance(block, dict):
            for v in block.values():
                if isinstance(v, str) and v.endswith(".glb"):
                    paths.append(v)
        elif isinstance(block, list):
            for item in block:
                if isinstance(item, str) and item.endswith(".glb"):
                    paths.append(item)
    extra = manifest.get("assets")
    if isinstance(extra, list):
        for item in extra:
            if isinstance(item, str) and item.endswith(".glb"):
                paths.append(item)
    return paths


def _res_path_to_fs(res_path: str, root: Path) -> Path:
    p = res_path.strip()
    if p.startswith("res://"):
        p = p[len("res://") :]
    return root / p


def probe_infographiste_assets(task: TeamTask | None = None) -> dict[str, object]:
    """Inventorie le manifest avatars/world et les .glb présents (read-only)."""
    root = godot_client_root()
    ctx = task.context if task else {}
    subproject = str(ctx.get("subproject") or "infographiste_ia")

    checks: list[dict[str, object]] = []
    manifest_paths = [
        root / "assets/avatars/manifest.json",
        root / "assets/world/manifest.json",
    ]
    all_expected: list[str] = []
    all_present: list[str] = []
    all_missing: list[str] = []

    for mp in manifest_paths:
        entry: dict[str, object] = {"path": str(mp), "kind": "manifest"}
        if not mp.is_file():
            entry["ok"] = False
            entry["error"] = "absent"
            checks.append(entry)
            continue
        try:
            data = json.loads(mp.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            entry["ok"] = False
            entry["error"] = str(e)
            checks.append(entry)
            continue
        if not isinstance(data, dict):
            entry["ok"] = False
            entry["error"] = "JSON invalide"
            checks.append(entry)
            continue

        glb_paths = _collect_manifest_glb_paths(data)
        present: list[str] = []
        missing: list[str] = []
        for gp in glb_paths:
            fs = _res_path_to_fs(gp, root)
            if fs.is_file() and fs.stat().st_size > 0:
                present.append(gp)
            else:
                missing.append(gp)
        all_expected.extend(glb_paths)
        all_present.extend(present)
        all_missing.extend(missing)
        entry["ok"] = True
        entry["expected"] = len(glb_paths)
        entry["present"] = len(present)
        entry["missing"] = missing[:12]
        checks.append(entry)

    pipeline_doc = _repo_root() / "docs/pipeline_assets_swg_godot.md"
    pipeline_ok = pipeline_doc.is_file()
    checks.append(
        {
            "kind": "pipeline_doc",
            "path": str(pipeline_doc),
            "ok": pipeline_ok,
        }
    )

    # Projet en cours : OK si manifest + doc pipeline lisibles (GLB optionnels)
    structural_ok = any(c.get("ok") for c in checks if c.get("kind") == "manifest") and pipeline_ok
    coverage = len(all_present) / max(len(all_expected), 1)

    return {
        "kind": "infographiste_probe",
        "ok": structural_ok,
        "readiness": "en_cours" if all_missing else "partiel",
        "subproject": subproject,
        "godot_root": str(root),
        "glb_expected": len(all_expected),
        "glb_present": len(all_present),
        "glb_missing": all_missing[:20],
        "coverage_ratio": round(coverage, 3),
        "checks": checks,
        "hint": (
            "Aucun GLB encore — normal en phase Infographiste ; suivre docs/pipeline_assets_swg_godot.md"
            if all_missing and structural_ok
            else None
        ),
    }
