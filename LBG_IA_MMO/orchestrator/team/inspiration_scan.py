"""Pont Pygmalion → Infographiste_IA (scan/classification inspiration LoRA)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from team.models import TeamTask


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def infographiste_ia_root() -> Path | None:
    raw = os.environ.get("LBG_INFOGRAPHISTE_IA_ROOT", "").strip()
    if raw:
        p = Path(raw)
        return p if p.is_dir() else None
    for cand in (
        _repo_root().parent.parent / "Infographiste_IA",
        Path("/home/sdesh/projects/Infographiste_IA"),
    ):
        if (cand / "orchestrator.py").is_file():
            return cand
    return None


def _dataset_dir(root: Path) -> Path:
    raw = os.environ.get("LBG_INFOGRAPHISTE_DATASET_DIR", "").strip()
    if raw:
        return Path(raw)
    return root / "dataset" / "inspiration_mmorpg"


def _classify_inline(root: Path, dataset: Path) -> dict[str, Any]:
    """Fallback sans dépendances ComfyUI (import direct style_classifier)."""
    styles_path = root / "config" / "art_styles.json"
    src = str(root / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from infographiste_virtuel.style_classifier import scan_and_classify

    report = scan_and_classify(dataset, styles_path)
    payload = report.to_dict()
    payload["ok"] = bool(payload.get("count", 0) > 0)
    payload["kind"] = "inspiration_classify"
    payload["infographiste_ia_root"] = str(root)
    payload["mode"] = "inline"
    return payload


def run_inspiration_classify(
    *,
    sort_to: Path | None = None,
    json_out: bool = True,
) -> dict[str, Any]:
    """Lance `orchestrator.py classify` dans Infographiste_IA."""
    root = infographiste_ia_root()
    if root is None:
        return {
            "ok": False,
            "error": "Infographiste_IA introuvable — définir LBG_INFOGRAPHISTE_IA_ROOT",
        }

    dataset = _dataset_dir(root)
    if not dataset.is_dir():
        return {
            "ok": False,
            "error": f"dataset inspiration absent: {dataset}",
            "infographiste_ia_root": str(root),
        }

    cmd = [
        sys.executable,
        str(root / "orchestrator.py"),
        "classify",
        "--dataset-dir",
        str(dataset),
        "--styles",
        str(root / "config" / "art_styles.json"),
    ]
    if json_out:
        cmd.append("--json")
    if sort_to is not None:
        cmd.extend(["--sort-to", str(sort_to), "--sort-mode", "symlink"])

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=float(os.environ.get("LBG_INFOGRAPHISTE_CLASSIFY_TIMEOUT_S", "120")),
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "error": str(e), "infographiste_ia_root": str(root)}

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "classify échoué").strip()
        if "ModuleNotFoundError" in err or "No module named" in err:
            try:
                return _classify_inline(root, dataset)
            except Exception as inline_exc:  # noqa: BLE001
                return {
                    "ok": False,
                    "error": f"{err[:200]} | inline: {inline_exc}",
                    "infographiste_ia_root": str(root),
                }
        return {
            "ok": False,
            "error": err[:500],
            "infographiste_ia_root": str(root),
        }

    if not json_out:
        return {"ok": True, "stdout": proc.stdout, "infographiste_ia_root": str(root)}

    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        return {
            "ok": False,
            "error": f"JSON classify invalide: {e}",
            "stdout_tail": proc.stdout[-400:],
        }

    payload["ok"] = bool(payload.get("count", 0) > 0)
    payload["kind"] = "inspiration_classify"
    payload["infographiste_ia_root"] = str(root)
    return payload


def probe_inspiration_dataset(task: TeamTask | None = None) -> dict[str, Any]:
    """Sonde L1 — inventaire + classification par style (read-only sauf sort_to explicite)."""
    ctx = task.context if task else {}
    sort = bool(ctx.get("inspiration_sort"))
    sort_to = None
    if sort:
        root = infographiste_ia_root()
        if root:
            sort_to = root / "dataset" / "styles_sorted"

    out = run_inspiration_classify(sort_to=sort_to)
    by_style = out.get("by_style") if isinstance(out.get("by_style"), dict) else {}
    unclassified = int(out.get("unclassified") or 0)
    ready = out.get("ready_for_lora") if isinstance(out.get("ready_for_lora"), list) else []

    return {
        "kind": "inspiration_probe",
        "ok": bool(out.get("ok")),
        "readiness": "pret_lora" if ready else ("partiel" if out.get("ok") else "absent"),
        "unclassified": unclassified,
        "ready_for_lora": ready,
        "by_style": by_style,
        "classify": out,
        "hint": (
            "Lancer: python orchestrator.py classify --json dans Infographiste_IA"
            if not out.get("ok")
            else None
        ),
    }
