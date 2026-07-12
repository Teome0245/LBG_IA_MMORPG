"""Tests Iris — forge GDScript M9 (gaps → patches staging)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from team.iris_gdscript_forge import (
    _patch_main_tscn,
    forge_from_m9_probes,
    forge_patches_from_gaps,
)


@pytest.fixture(autouse=True)
def _forge_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LBG_IRIS_FORGE_ENABLED", "1")
    monkeypatch.setenv("LBG_IRIS_FORGE_AUTO_APPLY", "0")
    monkeypatch.setenv("LBG_IRIS_FORGE_STAGING_DIR", str(tmp_path / "staging"))
    monkeypatch.setenv("LBG_PRIME_CLIENT_ROOT", str(tmp_path / "prime"))


def test_match_minimap_gap_generates_staging_patch(tmp_path: Path) -> None:
    prime = tmp_path / "prime"
    prime.mkdir()
    gaps = ["config/minimap_config.json absent (M9b-5)"]
    result = forge_patches_from_gaps(gaps, task_id="t-minimap")
    assert result.patches
    assert result.patches[0].target_rel == "config/minimap_config.json"
    staged = Path(result.patches[0].staging_path)
    assert staged.is_file()
    data = json.loads(staged.read_text(encoding="utf-8"))
    assert data.get("schema_version") == 1


def test_forge_from_probes_collects_nested_gaps(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    prime = tmp_path / "prime"
    prime.mkdir()
    probes = [
        {
            "track": "m9b_readiness",
            "ok": False,
            "gaps": ["scripts/minimap_hud.gd absent (minimap_script)"],
        }
    ]
    result = forge_from_m9_probes(probes, task_id="t-probes", track="m9b")
    assert result is not None
    assert any(p.target_rel == "scripts/minimap_hud.gd" for p in result.patches)


def test_patch_main_tscn_injects_minimap() -> None:
    content = '[gd_scene format=3]\n\n[node name="UI" type="CanvasLayer" parent="."]\n'
    patched, changed = _patch_main_tscn(content, mode="patch_main_minimap")
    assert changed
    assert "MinimapHud" in patched
    assert "minimap_hud.tscn" in patched


def test_auto_apply_copies_to_prime_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    prime = tmp_path / "prime"
    prime.mkdir()
    monkeypatch.setenv("LBG_IRIS_FORGE_AUTO_APPLY", "1")
    gaps = ["config/waypoints.json absent (M9c-3)"]
    result = forge_patches_from_gaps(gaps, task_id="t-apply")
    assert result.applied_count == 1
    assert (prime / "config/waypoints.json").is_file()


def test_m9_workflow_triggers_iris_forge(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    os.environ["LBG_TEAM_DB_PATH"] = ":memory:"
    monkeypatch.setenv("LBG_IRIS_FORGE_STAGING_DIR", str(tmp_path / "staging"))
    monkeypatch.setenv("LBG_PRIME_CLIENT_ROOT", str(tmp_path / "prime"))
    (tmp_path / "prime").mkdir()

    from team import roles as team_roles
    from team import store as team_store

    team_store._conn = None  # type: ignore[attr-defined]
    team_roles.set_dispatch_for_tests(lambda *a, **k: {"ok": True})

    def fake_m9b() -> dict:
        return {
            "track": "m9b_readiness",
            "ok": False,
            "gaps": ["config/minimap_config.json absent (M9b-5)"],
        }

    monkeypatch.setattr("team.m9_map_workflow.audit_m9b_readiness", fake_m9b)
    monkeypatch.setattr("team.m9_map_workflow.audit_m9a_readiness", lambda: {"track": "m9a", "ok": True, "gaps": []})
    monkeypatch.setattr("team.m9_map_workflow.audit_m9c_readiness", lambda: {"track": "m9c", "ok": True, "gaps": []})

    task = team_store.create_task(
        role="dev_godot",
        objective="Iris forge M9b minimap",
        actor_id="u:test",
        context={"godot_dev_persona": "iris", "godot_dev_track": "m9b", "m9_track": "m9b", "iris_forge": True},
    )
    result = team_roles.run_task(task.id)
    assert result is not None
    assert result.status == "failed"  # gaps M9 encore présents
    payload = result.result if isinstance(result.result, dict) else {}
    assert payload.get("iris_forge") is not None
    assert payload["iris_forge"]["patches"]
