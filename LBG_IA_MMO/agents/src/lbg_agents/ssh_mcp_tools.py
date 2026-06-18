"""Helpers MCP SSH (allowlist) — testables sans dépendance FastMCP."""

from __future__ import annotations

from typing import Any

from lbg_agents import ssh_client
from lbg_agents.remote_targets import canonical_role, known_server_ids, resolve_host


def resolve_ssh_target(server_id: str) -> tuple[str | None, str | None]:
    sid = (server_id or "").strip()
    host = resolve_host(sid)
    if not host and sid and not canonical_role(sid):
        if "." in sid or sid.isdigit():
            return sid, sid
    role = canonical_role(sid) or sid
    return host, role


def ssh_run_readonly(server_id: str, command: str) -> dict[str, Any]:
    if not ssh_client.ssh_enabled():
        return {
            "ok": False,
            "error": "SSH désactivé : LBG_MCP_SSH_ENABLED=1 requis sur le host MCP.",
        }
    host, role = resolve_ssh_target(server_id)
    if not host:
        return {"ok": False, "error": f"server_id inconnu : {server_id!r}"}
    cmd = (command or "").strip()
    if not cmd:
        return {"ok": False, "error": "command vide"}
    if not ssh_client.command_allowed(cmd):
        return {"ok": False, "error": f"commande refusée (allowlist) : {cmd[:120]}"}
    res = ssh_client.run_ssh(host, cmd)
    return {
        "ok": res.ok,
        "server_id": server_id,
        "role": role,
        "host": res.host,
        "command": res.command,
        "exit_code": res.exit_code,
        "stdout": res.stdout,
        "stderr": res.stderr,
        "error": res.error,
    }


def list_ssh_targets() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for sid in known_server_ids():
        role = canonical_role(sid)
        if role in seen:
            continue
        seen.add(role or sid)
        host = resolve_host(sid)
        if host:
            rows.append({"server_id": sid, "role": role or "", "host": host})
    return rows
