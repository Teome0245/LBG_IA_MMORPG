"""Tests action DevOps ``ssh_run`` (multi-VM, allowlist/dry-run/approbation). Rapatrié de P03."""

from __future__ import annotations

import pytest

from lbg_agents import ssh_client
from lbg_agents.devops_executor import run_devops_action
from lbg_agents.remote_targets import resolve_host


def test_resolve_host_aliases() -> None:
    assert resolve_host("linux-245") == "192.168.0.245"
    assert resolve_host("linux-246") == "192.168.0.246"
    assert resolve_host("precu") == "192.168.0.245"
    assert resolve_host("mmo") == "192.168.0.246"
    assert resolve_host("core") == "192.168.0.140"
    assert resolve_host("front") == "192.168.0.110"
    assert resolve_host("inconnu") is None


def test_ssh_run_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_MCP_SSH_ENABLED", raising=False)
    out = run_devops_action(
        actor_id="ops:1",
        text="ssh",
        action={"kind": "ssh_run", "server_id": "linux-245", "command": "systemctl is-active nginx"},
        context={},
    )
    assert out["ok"] is False
    assert out["outcome"] == "forbidden"
    assert "LBG_MCP_SSH_ENABLED" in out["error"]


def test_ssh_run_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_MCP_SSH_ENABLED", "1")
    out = run_devops_action(
        actor_id="ops:1",
        text="ssh",
        action={"kind": "ssh_run", "server_id": "linux-245", "command": "systemctl is-active nginx"},
        context={"devops_dry_run": True},
    )
    assert out["ok"] is True
    assert out["outcome"] == "dry_run"
    assert out["result"]["ssh_host"] == "192.168.0.245"


def test_ssh_run_command_not_allowlisted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_MCP_SSH_ENABLED", "1")
    out = run_devops_action(
        actor_id="ops:1",
        text="ssh",
        action={"kind": "ssh_run", "server_id": "core", "command": "rm -rf /"},
        context={"devops_dry_run": True},
    )
    assert out["ok"] is False
    assert out["outcome"] == "forbidden"
    assert "allowlist" in out["error"].lower()


def test_ssh_run_requires_approval_when_token_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_MCP_SSH_ENABLED", "1")
    monkeypatch.setenv("LBG_DEVOPS_APPROVAL_TOKEN", "sekret")
    monkeypatch.delenv("LBG_DEVOPS_DRY_RUN", raising=False)
    out = run_devops_action(
        actor_id="ops:1",
        text="ssh",
        action={"kind": "ssh_run", "server_id": "core", "command": "uptime"},
        context={},  # ni dry-run ni approbation
    )
    assert out["ok"] is False
    assert out["outcome"] == "approval_required"


def test_ssh_run_real_exec_with_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_MCP_SSH_ENABLED", "1")
    monkeypatch.setenv("LBG_DEVOPS_APPROVAL_TOKEN", "sekret")
    monkeypatch.delenv("LBG_DEVOPS_DRY_RUN", raising=False)

    def fake_run_ssh(host, command, *, user=None, trusted=False):  # noqa: ANN001
        return ssh_client.SshResult(True, 0, "active\n", "", host, command)

    monkeypatch.setattr(ssh_client, "run_ssh", fake_run_ssh)
    out = run_devops_action(
        actor_id="ops:1",
        text="ssh",
        action={"kind": "ssh_run", "server_id": "linux-110", "command": "systemctl is-active nginx"},
        context={"devops_approval": "sekret"},
    )
    assert out["ok"] is True
    assert out["outcome"] == "ok"
    assert out["result"]["ssh_host"] == "192.168.0.110"
    assert "active" in out["result"]["stdout"]
