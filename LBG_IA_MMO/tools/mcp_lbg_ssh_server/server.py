"""Serveur MCP SSH read-only (allowlist) vers les VM LAN."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_AGENTS_SRC = _ROOT / "agents" / "src"
if str(_AGENTS_SRC) not in sys.path:
    sys.path.insert(0, str(_AGENTS_SRC))

from mcp.server.fastmcp import FastMCP

from lbg_agents import ssh_client
from lbg_agents.ssh_mcp_tools import list_ssh_targets, ssh_run_readonly

mcp = FastMCP("lbg-ssh")


def _dump(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def ssh_configured_check() -> str:
    """Indique si LBG_MCP_SSH_ENABLED est actif."""
    return _dump({"ssh_enabled": ssh_client.ssh_enabled(), "user": ssh_client.ssh_user()})


@mcp.tool()
def ssh_list_targets() -> str:
    """Liste les server_id connus et leur IP résolue (core, front, precu, mmo…)."""
    return _dump({"ok": True, "targets": list_ssh_targets()})


@mcp.tool()
def ssh_run_readonly_tool(server_id: str, command: str) -> str:
    """Exécute une commande allowlistée sur une VM (systemctl is-active, free, uptime, curl -…)."""
    return _dump(ssh_run_readonly(server_id, command))


@mcp.tool()
def ssh_systemctl_is_active(server_id: str, unit: str) -> str:
    """État systemd d'une unité (lecture seule)."""
    unit = (unit or "").strip()
    if unit and "." not in unit:
        unit = f"{unit}.service"
    return _dump(ssh_run_readonly(server_id, f"systemctl is-active {unit}"))


@mcp.tool()
def ssh_uptime(server_id: str) -> str:
    """Uptime de la VM cible."""
    return _dump(ssh_run_readonly(server_id, "uptime"))


@mcp.tool()
def ssh_free_memory(server_id: str) -> str:
    """Mémoire et swap (free -h)."""
    return _dump(ssh_run_readonly(server_id, "free -h"))


if __name__ == "__main__":
    mcp.run()
