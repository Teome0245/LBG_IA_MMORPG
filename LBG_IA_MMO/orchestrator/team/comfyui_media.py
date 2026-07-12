"""Backend MEDIA — connecteur ComfyUI pour Pygmalion (tri-backend slot 3)."""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

import httpx


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def comfyui_enabled() -> bool:
    return os.environ.get("LBG_COMFYUI_ENABLED", "1").strip().lower() in ("1", "true", "yes", "on")


def comfyui_base_url() -> str:
    return os.environ.get("LBG_COMFYUI_BASE_URL", "http://192.168.0.140:8188").strip().rstrip("/")


def comfyui_output_dir() -> Path:
    raw = os.environ.get("LBG_COMFYUI_OUTPUT_DIR", "").strip()
    if raw:
        return Path(raw)
    return _repo_root() / "var" / "pygmalion_comfyui"


def _workflow_template_path() -> Path:
    raw = os.environ.get("LBG_COMFYUI_WORKFLOW", "").strip()
    if raw:
        return Path(raw)
    return _repo_root() / "infra" / "media" / "comfyui" / "workflow_sd15_lora_lowvram.json"


def probe_comfyui() -> dict[str, Any]:
    if not comfyui_enabled():
        return {"ok": False, "skipped": True, "reason": "LBG_COMFYUI_ENABLED=0"}
    base = comfyui_base_url()
    try:
        with httpx.Client(timeout=httpx.Timeout(8.0)) as client:
            r = client.get(f"{base}/system_stats")
            ok = r.status_code == 200
            return {"ok": ok, "url": f"{base}/system_stats", "status": r.status_code}
    except Exception as exc:
        return {"ok": False, "url": base, "error": str(exc)}


def _load_workflow_template() -> dict[str, Any]:
    path = _workflow_template_path()
    if not path.is_file():
        raise FileNotFoundError(f"workflow ComfyUI absent: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if "prompt" not in data:
        raise ValueError("workflow sans clé prompt")
    return data


def _patch_prompts(workflow: dict[str, Any], *, positive: str, negative: str) -> dict[str, Any]:
    prompt = workflow.get("prompt") or {}
    for node in prompt.values():
        if not isinstance(node, dict):
            continue
        if node.get("class_type") == "CLIPTextEncode":
            title = (node.get("_meta") or {}).get("title", "")
            inputs = node.setdefault("inputs", {})
            if "Negative" in str(title):
                inputs["text"] = negative
            elif "Positive" in str(title) or not inputs.get("text"):
                inputs["text"] = positive
    return workflow


def submit_comfyui_generation(
    *,
    positive_prompt: str,
    negative_prompt: str = "blurry, low quality, watermark, text, logo, deformed",
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Soumet un workflow text2img ComfyUI et télécharge les sorties."""
    if not comfyui_enabled():
        return {"ok": False, "skipped": True, "reason": "LBG_COMFYUI_ENABLED=0"}

    probe = probe_comfyui()
    if not probe.get("ok"):
        return {"ok": False, "error": "ComfyUI injoignable", "probe": probe}

    base = comfyui_base_url()
    out_dir = output_dir or comfyui_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    workflow = _patch_prompts(_load_workflow_template(), positive=positive_prompt, negative=negative_prompt)
    client_id = str(uuid.uuid4())
    timeout = float(os.environ.get("LBG_COMFYUI_JOB_TIMEOUT_S", "300"))
    poll = float(os.environ.get("LBG_COMFYUI_POLL_INTERVAL_S", "2"))

    try:
        with httpx.Client(timeout=httpx.Timeout(30.0)) as client:
            resp = client.post(f"{base}/prompt", json={"prompt": workflow["prompt"], "client_id": client_id})
            resp.raise_for_status()
            prompt_id = resp.json().get("prompt_id")
            if not prompt_id:
                return {"ok": False, "error": "pas de prompt_id ComfyUI"}

            deadline = time.time() + timeout
            history_entry: dict[str, Any] | None = None
            while time.time() < deadline:
                hr = client.get(f"{base}/history/{prompt_id}")
                hr.raise_for_status()
                hist = hr.json()
                if prompt_id in hist:
                    entry = hist[prompt_id]
                    if entry.get("outputs") or (entry.get("status") or {}).get("completed"):
                        history_entry = entry
                        break
                    if (entry.get("status") or {}).get("status_str") == "error":
                        return {"ok": False, "error": "job ComfyUI en erreur", "history": entry}
                time.sleep(poll)

            if history_entry is None:
                return {"ok": False, "error": f"timeout {timeout}s", "prompt_id": prompt_id}

            saved: list[str] = []
            for node_out in (history_entry.get("outputs") or {}).values():
                for img in node_out.get("images") or []:
                    params = {
                        "filename": img["filename"],
                        "subfolder": img.get("subfolder", ""),
                        "type": img.get("type", "output"),
                    }
                    vr = client.get(f"{base}/view", params=params)
                    vr.raise_for_status()
                    dest = out_dir / img["filename"]
                    dest.write_bytes(vr.content)
                    saved.append(str(dest))

            return {
                "ok": True,
                "prompt_id": prompt_id,
                "output_dir": str(out_dir),
                "images": saved,
                "positive_prompt": positive_prompt,
            }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "base_url": base}


def generate_asset_for_gap(gap_label: str, *, style: str = "SWG MMORPG isometric sprite") -> dict[str, Any]:
    """Traduit un gap asset en prompt technique et appelle ComfyUI."""
    positive = (
        f"{style}, {gap_label}, game asset, clean background, highly detailed, "
        "consistent lighting, production ready"
    )
    return submit_comfyui_generation(positive_prompt=positive)
