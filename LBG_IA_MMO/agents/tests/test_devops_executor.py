import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from lbg_agents.devops_executor import default_action_from_text, is_devops_dry_run, run_devops_action
from lbg_agents.dispatch import invoke_after_route


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
        if o.get("event") == "agents.devops.audit":
            last = o
    assert last is not None
    return last


def test_http_get_rejects_url_not_in_allowlist(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LBG_DEVOPS_APPROVAL_TOKEN", raising=False)
    monkeypatch.setenv("LBG_DEVOPS_HTTP_ALLOWLIST", "http://127.0.0.1:8010/healthz")
    out = run_devops_action(
        actor_id="p:1",
        text="x",
        action={"kind": "http_get", "url": "http://evil.test/healthz"},
        context={},
    )
    assert out["agent"] == "devops_executor"
    res = out.get("result")
    assert isinstance(res, dict)
    assert res.get("ok") is False
    assert "non autorisée" in (res.get("error") or "")
    audit = _last_audit_line(capsys)
    assert audit["outcome"] == "denied"
    assert audit["action_kind"] == "http_get"
    assert audit["dry_run"] is False
    assert audit.get("approval_gate_active") is False
    assert isinstance(audit.get("ts"), str) and "T" in audit["ts"]


def test_read_log_tail_disabled_when_allowlist_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_DEVOPS_APPROVAL_TOKEN", raising=False)
    monkeypatch.delenv("LBG_DEVOPS_LOG_ALLOWLIST", raising=False)
    out = run_devops_action(
        actor_id="p:1",
        text="x",
        action={"kind": "read_log_tail", "path": "/etc/passwd"},
        context={},
    )
    res = out.get("result")
    assert isinstance(res, dict)
    assert res.get("ok") is False


def test_read_log_tail_allowed_path(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_DEVOPS_APPROVAL_TOKEN", raising=False)
    logf = tmp_path / "app.log"
    logf.write_text("line1\nline2\n", encoding="utf-8")
    monkeypatch.setenv("LBG_DEVOPS_LOG_ALLOWLIST", str(logf))
    out = run_devops_action(
        actor_id="p:1",
        text="x",
        action={"kind": "read_log_tail", "path": str(logf), "max_bytes": 1024},
        context={},
    )
    res = out.get("result")
    assert isinstance(res, dict)
    assert res.get("ok") is True
    assert "line2" in (res.get("tail_preview") or "")


def test_default_action_from_text_devops_keyword() -> None:
    a = default_action_from_text("sonde devops")
    assert a == {"kind": "http_get", "url": "http://127.0.0.1:8010/healthz"}


def test_default_action_from_text_selfcheck_phrases() -> None:
    assert default_action_from_text("diagnostic complet") == {"kind": "selfcheck"}
    assert default_action_from_text("auto-diagnostic stack") == {"kind": "selfcheck"}


def test_selfcheck_dry_run_two_http_urls(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LBG_DEVOPS_APPROVAL_TOKEN", raising=False)
    monkeypatch.setenv(
        "LBG_DEVOPS_SELFCHECK_HTTP",
        "http://127.0.0.1:8010/healthz,http://127.0.0.1:8000/healthz",
    )
    monkeypatch.delenv("LBG_ORCHESTRATOR_URL", raising=False)
    monkeypatch.delenv("MMMORPG_IA_BACKEND_URL", raising=False)
    monkeypatch.delenv("LBG_DEVOPS_SYSTEMD_UNIT_ALLOWLIST", raising=False)
    out = run_devops_action(
        actor_id="p:1",
        text="x",
        action={"kind": "selfcheck"},
        context={"devops_dry_run": True},
    )
    assert out.get("error") is None
    res = out.get("result")
    assert isinstance(res, dict)
    assert res.get("kind") == "selfcheck"
    assert res.get("ok") is True
    assert res.get("dry_run") is True
    assert res.get("http_checked") == 2
    assert res.get("systemd_checked") == 0
    steps = res.get("steps")
    assert isinstance(steps, list) and len(steps) == 2
    assert all(s.get("healthy") for s in steps)
    audit = _last_audit_line(capsys)
    assert audit["action_kind"] == "selfcheck_summary"
    assert audit["outcome"] == "dry_run_planned"


def test_selfcheck_validation_error_when_no_steps(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LBG_DEVOPS_APPROVAL_TOKEN", raising=False)
    monkeypatch.setenv("LBG_DEVOPS_HTTP_ALLOWLIST", "http://127.0.0.1:9999/healthz")
    monkeypatch.setenv("LBG_DEVOPS_SELFCHECK_HTTP", "http://127.0.0.1:8010/healthz")
    monkeypatch.delenv("LBG_DEVOPS_SYSTEMD_UNIT_ALLOWLIST", raising=False)
    out = run_devops_action(
        actor_id="p:1",
        text="x",
        action={"kind": "selfcheck"},
        context={"devops_dry_run": True},
    )
    assert out.get("error")
    res = out.get("result")
    assert res is None
    audit = _last_audit_line(capsys)
    assert audit["action_kind"] == "selfcheck"
    assert audit["outcome"] == "validation_error"


def test_selfcheck_systemd_subset_respects_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LBG_DEVOPS_APPROVAL_TOKEN", raising=False)
    monkeypatch.setenv("LBG_DEVOPS_SELFCHECK_HTTP", "")
    monkeypatch.setenv("LBG_DEVOPS_HTTP_ALLOWLIST", "http://127.0.0.1:8010/healthz")
    monkeypatch.setenv(
        "LBG_DEVOPS_SYSTEMD_UNIT_ALLOWLIST",
        "lbg-backend.service,lbg-orchestrator.service",
    )
    monkeypatch.setenv("LBG_DEVOPS_SELFCHECK_SYSTEMD", "lbg-orchestrator.service")
    out = run_devops_action(
        actor_id="p:1",
        text="x",
        action={"kind": "selfcheck"},
        context={"devops_dry_run": True},
    )
    res = out.get("result")
    assert isinstance(res, dict)
    assert res.get("kind") == "selfcheck"
    kinds = [s.get("kind") for s in (res.get("steps") or [])]
    assert kinds.count("http_get") >= 1
    assert "systemd_is_active" in kinds
    systemd_steps = [s for s in (res.get("steps") or []) if s.get("kind") == "systemd_is_active"]
    assert len(systemd_steps) == 1
    assert systemd_steps[0].get("unit") == "lbg-orchestrator.service"


def test_dispatch_devops_selfcheck_context_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LBG_DEVOPS_APPROVAL_TOKEN", raising=False)
    monkeypatch.delenv("LBG_DEVOPS_SYSTEMD_UNIT_ALLOWLIST", raising=False)
    out = invoke_after_route(
        "agent.devops",
        actor_id="p:1",
        text="",
        context={"devops_selfcheck": True, "devops_dry_run": True},
    )
    res = out.get("result")
    assert isinstance(res, dict)
    assert res.get("kind") == "selfcheck"
    assert res.get("ok") is True


def test_http_get_dry_run_env_skips_httpx(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import lbg_agents.devops_executor as de

    def _boom(**kw: object) -> object:
        raise AssertionError("httpx.Client ne doit pas être appelé en dry-run")

    monkeypatch.setenv("LBG_DEVOPS_DRY_RUN", "1")
    monkeypatch.delenv("LBG_DEVOPS_APPROVAL_TOKEN", raising=False)
    monkeypatch.setenv("LBG_DEVOPS_HTTP_ALLOWLIST", "http://127.0.0.1:8010/healthz")
    monkeypatch.setattr(de.httpx, "Client", _boom)

    out = run_devops_action(
        actor_id="p:1",
        text="x",
        action={"kind": "http_get", "url": "http://127.0.0.1:8010/healthz"},
        context={"_trace_id": "t1"},
    )
    res = out.get("result")
    assert isinstance(res, dict)
    assert res.get("ok") is True
    assert res.get("dry_run") is True
    assert out.get("meta", {}).get("dry_run") is True
    assert out.get("meta", {}).get("dry_run_source") == "env"
    audit = _last_audit_line(capsys)
    assert audit["outcome"] == "dry_run_planned"
    assert audit["trace_id"] == "t1"
    assert audit["dry_run"] is True
    assert audit["dry_run_source"] == "env"


def test_http_get_dry_run_context_only(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import lbg_agents.devops_executor as de

    monkeypatch.delenv("LBG_DEVOPS_DRY_RUN", raising=False)
    monkeypatch.delenv("LBG_DEVOPS_APPROVAL_TOKEN", raising=False)
    monkeypatch.setenv("LBG_DEVOPS_HTTP_ALLOWLIST", "http://127.0.0.1:8010/healthz")
    def _no_http(**kw: object) -> None:
        raise AssertionError("httpx ne doit pas être appelé")

    monkeypatch.setattr(de.httpx, "Client", _no_http)

    out = run_devops_action(
        actor_id="p:1",
        text="x",
        action={"kind": "http_get", "url": "http://127.0.0.1:8010/healthz"},
        context={"devops_dry_run": True},
    )
    assert out.get("meta", {}).get("dry_run_source") == "context"
    audit = _last_audit_line(capsys)
    assert audit["dry_run_source"] == "context"


def test_is_devops_dry_run_env_over_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_DEVOPS_DRY_RUN", "true")
    assert is_devops_dry_run({"devops_dry_run": False}) is True


def test_http_get_blocked_without_approval_when_token_set(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import lbg_agents.devops_executor as de

    def _boom(**kw: object) -> None:
        raise AssertionError("httpx ne doit pas être appelé sans approbation")

    monkeypatch.setenv("LBG_DEVOPS_APPROVAL_TOKEN", "secret-token")
    monkeypatch.delenv("LBG_DEVOPS_DRY_RUN", raising=False)
    monkeypatch.setenv("LBG_DEVOPS_HTTP_ALLOWLIST", "http://127.0.0.1:8010/healthz")
    monkeypatch.setattr(de.httpx, "Client", _boom)

    out = run_devops_action(
        actor_id="p:1",
        text="x",
        action={"kind": "http_get", "url": "http://127.0.0.1:8010/healthz"},
        context={},
    )
    res = out.get("result")
    assert isinstance(res, dict)
    assert res.get("ok") is False
    assert res.get("approval_required") is True
    assert out.get("meta", {}).get("execution_gated") is True
    audit = _last_audit_line(capsys)
    assert audit["outcome"] == "approval_denied"
    assert audit.get("approval_gate_active") is True


def test_http_get_ok_with_approval_token_and_mock_httpx(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import lbg_agents.devops_executor as de

    class _Resp:
        status_code = 200
        text = '{"status":"ok"}'

    class _Client:
        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, *a: object) -> None:
            return None

        def get(self, url: str) -> _Resp:
            assert "8010" in url
            return _Resp()

    monkeypatch.setenv("LBG_DEVOPS_APPROVAL_TOKEN", "secret-token")
    monkeypatch.delenv("LBG_DEVOPS_DRY_RUN", raising=False)
    monkeypatch.setenv("LBG_DEVOPS_HTTP_ALLOWLIST", "http://127.0.0.1:8010/healthz")
    monkeypatch.setattr(de.httpx, "Client", lambda **kw: _Client())

    out = run_devops_action(
        actor_id="p:1",
        text="x",
        action={"kind": "http_get", "url": "http://127.0.0.1:8010/healthz"},
        context={"devops_approval": "secret-token"},
    )
    res = out.get("result")
    assert isinstance(res, dict)
    assert res.get("ok") is True
    assert res.get("status_code") == 200
    audit = _last_audit_line(capsys)
    assert audit["outcome"] == "executed_ok"


def test_http_get_ok_with_mock_httpx(monkeypatch: pytest.MonkeyPatch) -> None:
    import lbg_agents.devops_executor as de

    class _Resp:
        status_code = 200
        text = '{"status":"ok"}'

    class _Client:
        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, *a: object) -> None:
            return None

        def get(self, url: str) -> _Resp:
            assert "8010" in url
            return _Resp()

    monkeypatch.delenv("LBG_DEVOPS_APPROVAL_TOKEN", raising=False)
    monkeypatch.setenv("LBG_DEVOPS_HTTP_ALLOWLIST", "http://127.0.0.1:8010/healthz")
    monkeypatch.setattr(de.httpx, "Client", lambda **kw: _Client())

    out = run_devops_action(
        actor_id="p:1",
        text="x",
        action={"kind": "http_get", "url": "http://127.0.0.1:8010/healthz"},
        context={},
    )
    res = out.get("result")
    assert isinstance(res, dict)
    assert res.get("ok") is True
    assert res.get("status_code") == 200


def test_audit_appended_to_jsonl_file(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    import lbg_agents.devops_executor as de

    logf = tmp_path / "devops_audit.jsonl"
    monkeypatch.setenv("LBG_DEVOPS_AUDIT_LOG_PATH", str(logf))
    monkeypatch.delenv("LBG_DEVOPS_AUDIT_STDOUT", raising=False)
    monkeypatch.delenv("LBG_DEVOPS_APPROVAL_TOKEN", raising=False)
    monkeypatch.setenv("LBG_DEVOPS_HTTP_ALLOWLIST", "http://127.0.0.1:8010/healthz")

    class _Resp:
        status_code = 200
        text = "ok"

    class _Cl:
        def __enter__(self) -> "_Cl":
            return self

        def __exit__(self, *a: object) -> None:
            return None

        def get(self, url: str) -> _Resp:
            return _Resp()

    monkeypatch.setattr(de.httpx, "Client", lambda **kw: _Cl())

    run_devops_action(
        actor_id="p:1",
        text="x",
        action={"kind": "http_get", "url": "http://127.0.0.1:8010/healthz"},
        context={},
    )
    text = logf.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) >= 1
    row = json.loads(lines[-1])
    assert row["event"] == "agents.devops.audit"
    assert row["outcome"] == "executed_ok"
    assert "ts" in row


def test_audit_stdout_disabled_file_only(tmp_path: object, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    import lbg_agents.devops_executor as de

    logf = tmp_path / "only.jsonl"
    monkeypatch.setenv("LBG_DEVOPS_AUDIT_LOG_PATH", str(logf))
    monkeypatch.setenv("LBG_DEVOPS_AUDIT_STDOUT", "0")
    monkeypatch.delenv("LBG_DEVOPS_APPROVAL_TOKEN", raising=False)
    monkeypatch.setenv("LBG_DEVOPS_HTTP_ALLOWLIST", "http://127.0.0.1:8010/healthz")

    class _Resp:
        status_code = 200
        text = "ok"

    class _Cl:
        def __enter__(self) -> "_Cl":
            return self

        def __exit__(self, *a: object) -> None:
            return None

        def get(self, url: str) -> _Resp:
            return _Resp()

    monkeypatch.setattr(de.httpx, "Client", lambda **kw: _Cl())

    run_devops_action(
        actor_id="p:1",
        text="x",
        action={"kind": "http_get", "url": "http://127.0.0.1:8010/healthz"},
        context={},
    )
    out = capsys.readouterr().out
    assert "agents.devops.audit" not in out
    lines = [ln for ln in logf.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert json.loads(lines[-1])["event"] == "agents.devops.audit"


def test_systemd_is_active_dry_run_ok(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_DEVOPS_SYSTEMD_UNIT_ALLOWLIST", "lbg-backend.service")
    monkeypatch.delenv("LBG_DEVOPS_DRY_RUN", raising=False)
    out = run_devops_action(
        actor_id="p:1",
        text="x",
        action={"kind": "systemd_is_active", "unit": "lbg-backend.service"},
        context={"devops_dry_run": True},
    )
    res = out.get("result")
    assert isinstance(res, dict)
    assert res.get("ok") is True
    assert res.get("dry_run") is True
    audit = _last_audit_line(capsys)
    assert audit["outcome"] == "dry_run_planned"
    assert audit.get("unit") == "lbg-backend.service"


def test_systemd_is_active_empty_allowlist_denied(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_DEVOPS_SYSTEMD_UNIT_ALLOWLIST", raising=False)
    out = run_devops_action(
        actor_id="p:1",
        text="x",
        action={"kind": "systemd_is_active", "unit": "lbg-backend.service"},
        context={"devops_dry_run": True},
    )
    res = out.get("result")
    assert isinstance(res, dict)
    assert res.get("ok") is False
    audit = _last_audit_line(capsys)
    assert audit["outcome"] == "denied"


def test_systemd_is_active_mock_subprocess_ok(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import lbg_agents.devops_executor as de

    def _fake_run(cmd: list[str], **kw: object) -> SimpleNamespace:
        assert cmd == ["systemctl", "is-active", "lbg-backend.service"]
        return SimpleNamespace(returncode=0, stdout="active\n", stderr="")

    monkeypatch.setenv("LBG_DEVOPS_SYSTEMD_UNIT_ALLOWLIST", "lbg-backend.service")
    monkeypatch.delenv("LBG_DEVOPS_APPROVAL_TOKEN", raising=False)
    monkeypatch.delenv("LBG_DEVOPS_DRY_RUN", raising=False)
    monkeypatch.setattr(de.subprocess, "run", _fake_run)

    out = run_devops_action(
        actor_id="p:1",
        text="x",
        action={"kind": "systemd_is_active", "unit": "lbg-backend.service"},
        context={},
    )
    res = out.get("result")
    assert isinstance(res, dict)
    assert res.get("ok") is True
    assert res.get("active_state") == "active"
    assert res.get("exit_code") == 0
    audit = _last_audit_line(capsys)
    assert audit["outcome"] == "executed_ok"


def test_systemd_is_active_invalid_unit(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_DEVOPS_SYSTEMD_UNIT_ALLOWLIST", "lbg-backend.service")
    out = run_devops_action(
        actor_id="p:1",
        text="x",
        action={"kind": "systemd_is_active", "unit": "not-a-unit"},
        context={"devops_dry_run": True},
    )
    res = out.get("result")
    assert isinstance(res, dict)
    assert res.get("ok") is False
    audit = _last_audit_line(capsys)
    assert audit["outcome"] == "denied"


def test_systemd_is_active_not_on_allowlist(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_DEVOPS_SYSTEMD_UNIT_ALLOWLIST", "lbg-backend.service")
    out = run_devops_action(
        actor_id="p:1",
        text="x",
        action={"kind": "systemd_is_active", "unit": "dbus.service"},
        context={"devops_dry_run": True},
    )
    res = out.get("result")
    assert isinstance(res, dict)
    assert res.get("ok") is False
    assert "hors" in (res.get("error") or "")
    audit = _last_audit_line(capsys)
    assert audit["outcome"] == "denied"


def test_systemd_restart_disabled_when_allowlist_empty(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LBG_DEVOPS_APPROVAL_TOKEN", raising=False)
    monkeypatch.delenv("LBG_DEVOPS_SYSTEMD_RESTART_ALLOWLIST", raising=False)
    out = run_devops_action(
        actor_id="p:1",
        text="x",
        action={"kind": "systemd_restart", "unit": "lbg-backend.service"},
        context={"devops_dry_run": True},
    )
    res = out.get("result")
    assert isinstance(res, dict)
    assert res.get("ok") is False
    assert "RESTART_ALLOWLIST" in (res.get("error") or "")
    audit = _last_audit_line(capsys)
    assert audit["action_kind"] == "systemd_restart"
    assert audit["outcome"] == "denied"


def test_systemd_restart_dry_run_ok(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LBG_DEVOPS_APPROVAL_TOKEN", raising=False)
    monkeypatch.delenv("LBG_DEVOPS_DRY_RUN", raising=False)
    monkeypatch.setenv("LBG_DEVOPS_SYSTEMD_RESTART_ALLOWLIST", "lbg-backend.service")
    out = run_devops_action(
        actor_id="p:1",
        text="x",
        action={"kind": "systemd_restart", "unit": "lbg-backend.service"},
        context={"devops_dry_run": True},
    )
    res = out.get("result")
    assert isinstance(res, dict)
    assert res.get("ok") is True
    assert res.get("dry_run") is True
    audit = _last_audit_line(capsys)
    assert audit["action_kind"] == "systemd_restart"
    assert audit["outcome"] == "dry_run_planned"
    assert audit.get("unit") == "lbg-backend.service"


def test_systemd_restart_requires_approval_when_token_set(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import lbg_agents.devops_executor as de

    def _boom(*a: object, **kw: object) -> None:
        raise AssertionError("subprocess ne doit pas être appelé sans approbation")

    monkeypatch.setenv("LBG_DEVOPS_APPROVAL_TOKEN", "secret-token")
    monkeypatch.delenv("LBG_DEVOPS_DRY_RUN", raising=False)
    monkeypatch.setenv("LBG_DEVOPS_SYSTEMD_RESTART_ALLOWLIST", "lbg-backend.service")
    monkeypatch.setattr(de.subprocess, "run", _boom)
    out = run_devops_action(
        actor_id="p:1",
        text="x",
        action={"kind": "systemd_restart", "unit": "lbg-backend.service"},
        context={},
    )
    res = out.get("result")
    assert isinstance(res, dict)
    assert res.get("ok") is False
    assert res.get("approval_required") is True
    audit = _last_audit_line(capsys)
    assert audit["action_kind"] == "systemd_restart"
    assert audit["outcome"] == "approval_denied"


def test_systemd_restart_mock_subprocess_ok(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import lbg_agents.devops_executor as de

    de._restart_real_ts.clear()

    def _fake_run(cmd: list[str], **kw: object) -> SimpleNamespace:
        assert cmd == ["sudo", "-n", "systemctl", "restart", "lbg-backend.service"]
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.delenv("LBG_DEVOPS_APPROVAL_TOKEN", raising=False)
    monkeypatch.delenv("LBG_DEVOPS_DRY_RUN", raising=False)
    monkeypatch.setenv("LBG_DEVOPS_SYSTEMD_RESTART_ALLOWLIST", "lbg-backend.service")
    monkeypatch.setattr(de.subprocess, "run", _fake_run)
    out = run_devops_action(
        actor_id="p:1",
        text="x",
        action={"kind": "systemd_restart", "unit": "lbg-backend.service"},
        context={},
    )
    res = out.get("result")
    assert isinstance(res, dict)
    assert res.get("ok") is True
    assert res.get("exit_code") == 0
    audit = _last_audit_line(capsys)
    assert audit["action_kind"] == "systemd_restart"
    assert audit["outcome"] == "executed_ok"


def test_restart_maintenance_allows_inside_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_DEVOPS_SYSTEMD_RESTART_MAINTENANCE_UTC", "10:00-12:00")
    from lbg_agents.devops_executor import _restart_maintenance_allows

    ok, _ = _restart_maintenance_allows(datetime(2026, 1, 1, 11, 30, tzinfo=timezone.utc))
    assert ok is True


def test_restart_maintenance_denies_outside_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_DEVOPS_SYSTEMD_RESTART_MAINTENANCE_UTC", "10:00-12:00")
    from lbg_agents.devops_executor import _restart_maintenance_allows

    ok, err = _restart_maintenance_allows(datetime(2026, 1, 1, 15, 0, tzinfo=timezone.utc))
    assert ok is False
    assert err and "maintenance" in err.lower()


def test_restart_maintenance_overnight_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_DEVOPS_SYSTEMD_RESTART_MAINTENANCE_UTC", "22:00-06:00")
    from lbg_agents.devops_executor import _restart_maintenance_allows

    assert _restart_maintenance_allows(datetime(2026, 1, 1, 23, 0, tzinfo=timezone.utc))[0] is True
    assert _restart_maintenance_allows(datetime(2026, 1, 1, 5, 0, tzinfo=timezone.utc))[0] is True
    assert _restart_maintenance_allows(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc))[0] is False


def test_systemd_restart_quota_blocks_after_max(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import lbg_agents.devops_executor as de

    de._restart_real_ts.clear()
    monkeypatch.delenv("LBG_DEVOPS_APPROVAL_TOKEN", raising=False)
    monkeypatch.delenv("LBG_DEVOPS_DRY_RUN", raising=False)
    monkeypatch.setenv("LBG_DEVOPS_SYSTEMD_RESTART_ALLOWLIST", "lbg-backend.service")
    monkeypatch.setenv("LBG_DEVOPS_SYSTEMD_RESTART_MAX_PER_WINDOW", "2")
    monkeypatch.setenv("LBG_DEVOPS_SYSTEMD_RESTART_WINDOW_S", "86400")

    def _fake_run(cmd: list[str], **kw: object) -> SimpleNamespace:
        assert cmd[:4] == ["sudo", "-n", "systemctl", "restart"]
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(de.subprocess, "run", _fake_run)

    for _ in range(2):
        out = run_devops_action(
            actor_id="p:1",
            text="x",
            action={"kind": "systemd_restart", "unit": "lbg-backend.service"},
            context={},
        )
        assert out.get("result", {}).get("ok") is True

    out3 = run_devops_action(
        actor_id="p:1",
        text="x",
        action={"kind": "systemd_restart", "unit": "lbg-backend.service"},
        context={},
    )
    res = out3.get("result")
    assert isinstance(res, dict)
    assert res.get("ok") is False
    assert "quota" in (res.get("error") or "").lower()
    audit = _last_audit_line(capsys)
    assert audit["outcome"] == "denied"
