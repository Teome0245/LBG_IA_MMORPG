"""
Injection de ``context.lyra`` depuis le serveur monde (HTTP) avant routage orchestrateur.

Voir ``docs/lyra.md`` : ``world_npc_id`` + ``LBG_MMO_SERVER_URL``.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _skip_mmo_sync(context: dict[str, Any]) -> bool:
    lyra_existing = context.get("lyra")
    if isinstance(lyra_existing, dict):
        meta = lyra_existing.get("meta")
        if isinstance(meta, dict) and meta.get("skip_mmo_sync"):
            return True
    return False


async def _try_merge_from_mmmorpg_internal_http(context: dict[str, Any], *, npc_id: str) -> bool:
    """
    Source "jeu WS" (lecture seule) : endpoint interne mmmorpg.
    Variables:
      - LBG_MMMORPG_INTERNAL_HTTP_URL (ex. http://192.168.0.245:8773)
      - LBG_MMMORPG_INTERNAL_HTTP_TOKEN (optionnel, header X-LBG-Service-Token)
    """
    base = os.environ.get("LBG_MMMORPG_INTERNAL_HTTP_URL", "").strip().rstrip("/")
    if not base:
        return False

    token = os.environ.get("LBG_MMMORPG_INTERNAL_HTTP_TOKEN", "").strip()
    trace_id = context.get("_trace_id")
    params = {}
    if isinstance(trace_id, str) and trace_id.strip():
        params["trace_id"] = trace_id.strip()

    headers = {}
    if token:
        headers["X-LBG-Service-Token"] = token

    try:
        url = f"{base}/internal/v1/npc/{npc_id.strip()}/lyra-snapshot"
        async with httpx.AsyncClient(timeout=1.5) as client:
            r = await client.get(
                url,
                params=params or None,
                headers=headers or None,
            )
        if r.status_code != 200:
            logger.info(
                "mmmorpg lyra snapshot HTTP %s for npc_id=%s trace_id=%s body=%s",
                r.status_code,
                npc_id,
                (params.get("trace_id") if params else "") or "",
                (r.text or "")[:200],
            )
            return False
        try:
            data = r.json()
        except ValueError:
            logger.info(
                "mmmorpg lyra snapshot non-JSON for npc_id=%s trace_id=%s body=%s",
                npc_id,
                (params.get("trace_id") if params else "") or "",
                (r.text or "")[:200],
            )
            return False
        ly = data.get("lyra") if isinstance(data, dict) else None
        if isinstance(ly, dict):
            context["lyra"] = ly
            return True
    except Exception as e:
        logger.info(
            "mmmorpg lyra snapshot failed for npc_id=%s trace_id=%s: %s",
            npc_id,
            (params.get("trace_id") if params else "") or "",
            e,
        )
    return False


async def _try_merge_from_mmo_server(context: dict[str, Any], *, npc_id: str) -> bool:
    """Source 'mmo_server' historique : GET /v1/world/lyra (LAN)."""
    base = os.environ.get("LBG_MMO_SERVER_URL", "").strip().rstrip("/")
    if not base:
        return False
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(
                f"{base}/v1/world/lyra",
                params={"npc_id": npc_id.strip()},
            )
        if r.status_code != 200:
            logger.warning(
                "mmo lyra sync HTTP %s for npc_id=%s: %s",
                r.status_code,
                npc_id,
                r.text[:200],
            )
            return False
        data = r.json()
        ly = data.get("lyra")
        if isinstance(ly, dict):
            context["lyra"] = ly
            return True
    except Exception as e:
        logger.warning("mmo lyra sync failed for npc_id=%s: %s", npc_id, e)
    return False


async def merge_mmo_lyra_if_configured(context: dict[str, Any]) -> None:
    """
    Si ``world_npc_id`` est présent, tente d'injecter ``context['lyra']`` depuis une source monde :
    - priorité : snapshot interne `mmmorpg_server` (si `LBG_MMMORPG_INTERNAL_HTTP_URL` est défini),
    - fallback : `mmo_server` (si `LBG_MMO_SERVER_URL` est défini).

    ``context.lyra.meta.skip_mmo_sync`` (truthy) désactive la fusion pour cet appel.
    """
    if _skip_mmo_sync(context):
        return
    npc_id = context.get("world_npc_id")
    if not npc_id or not isinstance(npc_id, str):
        return

    # 1) Source jeu WS (si activée)
    if await _try_merge_from_mmmorpg_internal_http(context, npc_id=npc_id):
        return

    # 2) Fallback historique
    await _try_merge_from_mmo_server(context, npc_id=npc_id)
