"""Tests tri-backend — openclaw, reason_llm, iris_llm_forge."""

from __future__ import annotations

import json
from pathlib import Path

from pathlib import Path

import pytest

from team.openclaw_adapter import list_skills, load_skill_definitions, run_skill
from team.reason_llm import extract_code_block, reason_llm_enabled
from team.iris_llm_forge import llm_patch_for_gap, run_forge_smoke


def test_openclaw_lists_skills() -> None:
    skills = list_skills()
    ids = {s["id"] for s in skills}
    assert "ops_qa_smoke_lan" in ids
    assert "ops_m9_prime_sync" in ids


def test_openclaw_loads_json_skills() -> None:
    defs = load_skill_definitions()
    assert defs["ops_qa_smoke_lan"]["openclaw_native"] is True


def test_openclaw_run_unknown_skill() -> None:
    out = run_skill("skill_inexistant_xyz")
    assert out["ok"] is False


def test_extract_gdscript_block() -> None:
    text = "Voici:\n```gdscript\nextends Node\n```"
    assert extract_code_block(text) == "extends Node"


def test_llm_patch_skipped_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_REASON_LLM_DISABLED", "1")
    out = llm_patch_for_gap("minimap script missing")
    assert out.get("skipped") is True


def test_forge_smoke_skips_unknown_track() -> None:
    out = run_forge_smoke("unknown_track")
    assert out.get("skipped") is True


def test_reason_routes_local_first() -> None:
    from team.reason_llm import reason_routes

    routes = reason_routes()
    assert routes
    assert routes[0]["tier"] == "local"
    assert "110" in routes[0]["base_url"] or "11434" in routes[0]["base_url"]


def test_probe_comfyui_skipped_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_COMFYUI_ENABLED", "0")
    from team.comfyui_media import probe_comfyui

    out = probe_comfyui()
    assert out.get("skipped") is True


def test_openclaw_bridge_health_import() -> None:
    import importlib.util

    path = Path(__file__).resolve().parents[2] / "infra" / "openclaw" / "lbg_skill_bridge.py"
    assert path.is_file()
