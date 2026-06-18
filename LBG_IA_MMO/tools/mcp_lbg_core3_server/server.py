"""Serveur MCP read-only vers le sidecar Core3 IA (VM Prime 246)."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("lbg-core3")


def _sidecar_base() -> str:
    return (
        os.environ.get("LBG_CORE3_SIDECAR_URL")
        or os.environ.get("CORE3_IA_SIDECAR_URL")
        or "http://192.168.0.246:8791"
    ).rstrip("/")


def _get(path: str, *, params: dict[str, str] | None = None, timeout_s: float = 15.0) -> dict[str, Any]:
    url = f"{_sidecar_base()}{path}"
    with httpx.Client(timeout=timeout_s) as client:
        resp = client.get(url, params=params or {})
    try:
        body = resp.json() if resp.content else {}
    except ValueError:
        body = {"raw": resp.text[:500]}
    if resp.status_code >= 400:
        return {"ok": False, "status": resp.status_code, "url": url, "body": body}
    return {"ok": True, "status": resp.status_code, "url": url, "body": body}


def _dump(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def core3_sidecar_url() -> str:
    """URL de base du sidecar Core3 IA."""
    return _dump({"url": _sidecar_base()})


@mcp.tool()
def core3_health() -> str:
    """Santé du sidecar : phase, chemins registre, routage LLM."""
    return _dump(_get("/health"))


@mcp.tool()
def core3_player_snapshot(player: str = "Lia") -> str:
    """Snapshot joueur IA (position, online, métier, etc.)."""
    return _dump(_get("/v1/player-snapshot", params={"player": player}))


@mcp.tool()
def core3_npc_pilots() -> str:
    """Registre PNJ pilotés + snapshots live."""
    return _dump(_get("/v1/npc-pilots"))


@mcp.tool()
def core3_npc_snapshot(npc_id: str) -> str:
    """Snapshot d'un PNJ par npc_id ou pilot_id."""
    return _dump(_get("/v1/npc-snapshot", params={"npc_id": npc_id}))


@mcp.tool()
def core3_events(
    player: str = "",
    after: str = "",
    limit: int = 50,
    include_actor: bool = False,
) -> str:
    """Événements sociaux récents du sidecar (chat, interactions)."""
    params: dict[str, str] = {"limit": str(max(1, min(limit, 200)))}
    if player:
        params["player"] = player
    if after:
        params["after"] = after
    if include_actor:
        params["include_actor"] = "1"
    return _dump(_get("/v1/events", params=params))


if __name__ == "__main__":
    mcp.run()
