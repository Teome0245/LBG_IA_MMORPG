"""Tests helpers MCP SSH (allowlist, résolution hôtes)."""

from __future__ import annotations

from unittest.mock import patch

from lbg_agents import ssh_client
from lbg_agents.ssh_mcp_tools import list_ssh_targets, ssh_run_readonly


def test_list_ssh_targets_has_core():
    rows = list_ssh_targets()
    roles = {r["role"] for r in rows}
    assert "core" in roles


def test_ssh_run_rejects_disallowed(monkeypatch):
    monkeypatch.setenv("LBG_MCP_SSH_ENABLED", "1")
    out = ssh_run_readonly("core", "rm -rf /")
    assert out["ok"] is False
    assert "allowlist" in out["error"]


def test_ssh_run_ok(monkeypatch):
    monkeypatch.setenv("LBG_MCP_SSH_ENABLED", "1")

    def fake_run(host, command, **kwargs):
        return ssh_client.SshResult(True, 0, "active\n", "", host, command)

    with patch.object(ssh_client, "run_ssh", fake_run):
        out = ssh_run_readonly("precu", "systemctl is-active lbg-mmo-server.service")
    assert out["ok"] is True
    assert out["host"] == "192.168.0.245"
