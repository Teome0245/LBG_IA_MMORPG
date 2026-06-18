"""Serveur MCP read-only Proxmox VE pour Cursor / World Director."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# agents/src sur PYTHONPATH si lancé depuis tools/mcp_proxmox_server/
_ROOT = Path(__file__).resolve().parents[2]
_AGENTS_SRC = _ROOT / "agents" / "src"
if str(_AGENTS_SRC) not in sys.path:
    sys.path.insert(0, str(_AGENTS_SRC))

from mcp.server.fastmcp import FastMCP

from lbg_agents.proxmox_client import (
    get_cluster_status,
    get_vm_status,
    list_vms,
    match_lan_vms,
    proxmox_configured,
)

mcp = FastMCP("lbg-proxmox")


def _dump(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def proxmox_configured_check() -> str:
    """Indique si LBG_PROXMOX_TOKEN est défini."""
    return _dump({"configured": proxmox_configured()})


@mcp.tool()
def proxmox_cluster_status() -> str:
    """Version Proxmox et liste résumée des VMs du cluster (read-only)."""
    return _dump(get_cluster_status())


@mcp.tool()
def proxmox_list_vms(running_only: bool = False) -> str:
    """Liste les VMs QEMU ; running_only=true filtre les VMs en cours d'exécution."""
    return _dump(list_vms(running_only=running_only))


@mcp.tool()
def proxmox_vm_status(vmid: int) -> str:
    """Métriques courantes d'une VM par son vmid Proxmox."""
    return _dump(get_vm_status(vmid))


@mcp.tool()
def proxmox_vm_config(vmid: int) -> str:
    """Configuration QEMU d'une VM (lecture seule)."""
    from lbg_agents.proxmox_client import get_vm_config

    return _dump(get_vm_config(vmid))


@mcp.tool()
def proxmox_lan_vms() -> str:
    """Associe core/front/precu/prime aux VMs Proxmox (nom ou LBG_PROXMOX_VM_LABELS)."""
    return _dump(match_lan_vms())


if __name__ == "__main__":
    mcp.run()
