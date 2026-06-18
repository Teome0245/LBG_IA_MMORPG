"""Tests remédiation assistée plan→apply→validate (rapatrié de P03)."""

from __future__ import annotations

import pytest

from lbg_agents.remediation import (
    build_plan_from_selfcheck,
    default_remediation_action_from_text,
    run_remediation,
)


def _selfcheck_ko() -> dict:
    return {
        "result": {
            "kind": "selfcheck",
            "ok": False,
            "dry_run": True,
            "steps": [
                {
                    "kind": "systemd_is_active",
                    "unit": "lbg-backend.service",
                    "outcome": "executed_error",
                    "healthy": False,
                    "result": {"unit": "lbg-backend.service", "active_state": "failed"},
                },
                {
                    "kind": "http_get",
                    "url": "http://127.0.0.1:8000/healthz",
                    "outcome": "executed_error",
                    "healthy": False,
                    "result": {"url": "http://127.0.0.1:8000/healthz", "status_code": 502},
                },
            ],
            "remediation_hints": ["Vérifier le service derrière http://127.0.0.1:8000/healthz (HTTP 502)."],
        }
    }


def test_build_plan_suggests_restart_and_resonde() -> None:
    plan = build_plan_from_selfcheck(_selfcheck_ko())
    assert plan["kind"] == "remediation_plan"
    assert plan["selfcheck_ok"] is False
    kinds = {a["devops_action"]["kind"] for a in plan["suggested_actions"] if "devops_action" in a}
    assert "systemd_restart" in kinds
    assert "http_get" in kinds
    restart = next(a for a in plan["suggested_actions"] if a.get("devops_action", {}).get("kind") == "systemd_restart")
    assert restart["devops_action"]["unit"] == "lbg-backend.service"
    assert restart["requires_approval"] is True


def test_default_action_from_text() -> None:
    assert default_remediation_action_from_text("fais un plan de remédiation") == {"step": "plan"}
    assert default_remediation_action_from_text("remédiation apply") == {"step": "apply"}
    assert default_remediation_action_from_text("remédiation, vérifie") == {"step": "validate"}
    assert default_remediation_action_from_text("bonjour") is None


def test_run_remediation_plan_is_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    import lbg_agents.devops_executor as de

    def fake_run(*, actor_id, text, action, context):  # noqa: ANN001
        assert action["kind"] == "selfcheck"
        return _selfcheck_ko()

    monkeypatch.setattr(de, "run_devops_action", fake_run)
    out = run_remediation(actor_id="ops:1", text="plan", action={"step": "plan"}, context={})
    assert out["ok"] is True
    assert out["meta"]["read_only"] is True
    assert out["result"]["kind"] == "remediation_plan"


def test_run_remediation_apply_requires_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_DEVOPS_DRY_RUN", raising=False)
    out = run_remediation(
        actor_id="ops:1",
        text="apply",
        action={"step": "apply", "devops_action": {"kind": "systemd_restart", "unit": "lbg-backend.service"}},
        context={},  # ni dry-run ni approval
    )
    assert out["ok"] is False
    assert out["outcome"] == "approval_required"


def test_run_remediation_apply_dry_run_executes_dryrun(monkeypatch: pytest.MonkeyPatch) -> None:
    import lbg_agents.devops_executor as de

    captured: dict = {}

    def fake_run(*, actor_id, text, action, context):  # noqa: ANN001
        captured["action"] = action
        return {"result": {"kind": action["kind"], "ok": True, "dry_run": True}}

    monkeypatch.setattr(de, "run_devops_action", fake_run)
    out = run_remediation(
        actor_id="ops:1",
        text="apply",
        action={"step": "apply", "devops_action": {"kind": "systemd_restart", "unit": "lbg-backend.service"}},
        context={"devops_dry_run": True},
    )
    assert out["ok"] is True
    assert captured["action"]["kind"] == "systemd_restart"
