import json
import subprocess

import pytest

from lbg_agents.dispatch import invoke_after_route
from lbg_agents.opengame_executor import run_opengame_action
import lbg_agents.opengame_executor as oe


def _last_audit_line(capsys: pytest.CaptureFixture[str]) -> dict:
    out = capsys.readouterr().out
    last: dict | None = None
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if o.get("event") == "agents.opengame.audit":
            last = o
    assert last is not None
    return last


def test_opengame_generate_prototype_dry_run(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.delenv("LBG_OPENGAME_DRY_RUN", raising=False)
    monkeypatch.delenv("LBG_OPENGAME_EXECUTION_ENABLED", raising=False)
    monkeypatch.delenv("LBG_OPENGAME_APPROVAL_TOKEN", raising=False)
    monkeypatch.setenv("LBG_OPENGAME_SANDBOX_DIR", str(tmp_path / "sandbox"))

    out = run_opengame_action(
        actor_id="p:1",
        text="Génère un snake",
        action={"kind": "generate_prototype", "project_name": "snake", "prompt": "Build a Snake clone"},
        context={"_trace_id": "t-open"},
    )

    assert out["agent"] == "opengame_executor"
    assert out["handler"] == "opengame"
    assert out["ok"] is True
    assert out["outcome"] == "dry_run"
    assert out["project_name"] == "snake"
    assert out["target_dir"].endswith("/sandbox/snake")
    assert out["planned"]["command"][0] == "opengame"
    assert out["meta"]["dry_run"] is True
    audit = _last_audit_line(capsys)
    assert audit["trace_id"] == "t-open"
    assert audit["outcome"] == "dry_run_planned"
    assert audit["capability"] == "prototype_game"


def test_opengame_rejects_invalid_project_name(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("LBG_OPENGAME_SANDBOX_DIR", str(tmp_path / "sandbox"))

    out = run_opengame_action(
        actor_id="p:1",
        text="x",
        action={"kind": "generate_prototype", "project_name": "../escape", "prompt": "x"},
        context={},
    )

    assert out["ok"] is False
    assert out["outcome"] == "bad_request"
    audit = _last_audit_line(capsys)
    assert audit["outcome"] == "bad_request"


def test_opengame_real_execution_is_disabled_in_skeleton(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("LBG_OPENGAME_DRY_RUN", "0")
    monkeypatch.delenv("LBG_OPENGAME_EXECUTION_ENABLED", raising=False)
    monkeypatch.setenv("LBG_OPENGAME_SANDBOX_DIR", str(tmp_path / "sandbox"))

    out = run_opengame_action(
        actor_id="p:1",
        text="x",
        action={"kind": "generate_prototype", "project_name": "arena", "prompt": "Build an arena prototype"},
        context={},
    )

    assert out["ok"] is False
    assert out["outcome"] == "execution_disabled"
    audit = _last_audit_line(capsys)
    assert audit["outcome"] == "execution_disabled"
    assert audit["dry_run"] is False


def test_opengame_real_execution_reports_missing_cli(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("LBG_OPENGAME_DRY_RUN", "0")
    monkeypatch.setenv("LBG_OPENGAME_EXECUTION_ENABLED", "1")
    monkeypatch.setenv("LBG_OPENGAME_SANDBOX_DIR", str(tmp_path / "sandbox"))
    monkeypatch.setattr(oe.shutil, "which", lambda name: None)

    out = run_opengame_action(
        actor_id="p:1",
        text="x",
        action={"kind": "generate_prototype", "project_name": "arena", "prompt": "Build an arena prototype"},
        context={},
    )

    assert out["ok"] is False
    assert out["outcome"] == "tool_missing"
    audit = _last_audit_line(capsys)
    assert audit["outcome"] == "tool_missing"


def test_opengame_real_execution_success(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    calls: list[dict] = []

    def fake_run(command, **kwargs):
        calls.append({"command": command, **kwargs})
        return subprocess.CompletedProcess(command, 0, stdout="ok generated", stderr="")

    monkeypatch.setenv("LBG_OPENGAME_DRY_RUN", "0")
    monkeypatch.setenv("LBG_OPENGAME_EXECUTION_ENABLED", "1")
    monkeypatch.setenv("LBG_OPENGAME_SANDBOX_DIR", str(tmp_path / "sandbox"))
    monkeypatch.setattr(oe.shutil, "which", lambda name: "/usr/local/bin/opengame")
    monkeypatch.setattr(oe.subprocess, "run", fake_run)

    out = run_opengame_action(
        actor_id="p:1",
        text="x",
        action={"kind": "generate_prototype", "project_name": "arena", "prompt": "Build an arena prototype"},
        context={"_trace_id": "t-run"},
    )

    assert out["ok"] is True
    assert out["outcome"] == "success"
    assert out["returncode"] == 0
    assert "ok generated" in out["stdout_preview"]
    assert calls
    assert calls[0]["command"] == [
        "/usr/local/bin/opengame",
        "-p",
        "Build an arena prototype",
        "--approval-mode",
        "auto-edit",
    ]
    assert "--yolo" not in calls[0]["command"]
    assert calls[0]["cwd"] == out["target_dir"]
    audit = _last_audit_line(capsys)
    assert audit["trace_id"] == "t-run"
    assert audit["outcome"] == "success"


def test_opengame_refuses_non_empty_target(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    sandbox = tmp_path / "sandbox"
    target = sandbox / "arena"
    target.mkdir(parents=True)
    (target / "old.txt").write_text("old", encoding="utf-8")

    monkeypatch.setenv("LBG_OPENGAME_DRY_RUN", "0")
    monkeypatch.setenv("LBG_OPENGAME_EXECUTION_ENABLED", "1")
    monkeypatch.setenv("LBG_OPENGAME_SANDBOX_DIR", str(sandbox))
    monkeypatch.setattr(oe.shutil, "which", lambda name: "/usr/local/bin/opengame")

    out = run_opengame_action(
        actor_id="p:1",
        text="x",
        action={"kind": "generate_prototype", "project_name": "arena", "prompt": "Build an arena prototype"},
        context={},
    )

    assert out["ok"] is False
    assert out["outcome"] == "target_not_empty"
    audit = _last_audit_line(capsys)
    assert audit["outcome"] == "target_not_empty"


def test_dispatch_opengame_requires_structured_action() -> None:
    out = invoke_after_route("agent.opengame", actor_id="p:1", text="prototype", context={})
    assert out["agent"] == "opengame_dispatch"
    assert out["ok"] is False
    assert out["outcome"] == "bad_request"


def test_dispatch_opengame_dry_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("LBG_OPENGAME_SANDBOX_DIR", str(tmp_path / "sandbox"))
    out = invoke_after_route(
        "agent.opengame",
        actor_id="p:1",
        text="prototype",
        context={
            "opengame_action": {
                "kind": "generate_prototype",
                "project_name": "cards",
                "prompt": "Build a card battle prototype",
            }
        },
    )
    assert out["agent"] == "opengame_executor"
    assert out["ok"] is True
    assert out["outcome"] == "dry_run"
