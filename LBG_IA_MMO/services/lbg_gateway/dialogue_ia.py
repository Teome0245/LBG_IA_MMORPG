"""Pont dialogue Prime → orchestrateur / agent (même contrat que mmmorpg_server)."""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

LOG = logging.getLogger("lbg_gateway.dialogue")

IA_URL = (
    os.environ.get("LBG_GATEWAY_IA_BACKEND_URL", os.environ.get("MMMORPG_IA_BACKEND_URL", ""))
    .strip()
    .rstrip("/")
)
IA_PATH = (
    os.environ.get("LBG_GATEWAY_IA_BACKEND_PATH", os.environ.get("MMMORPG_IA_BACKEND_PATH", "/v1/pilot/internal/route"))
    .strip()
    or "/v1/pilot/internal/route"
)
IA_TOKEN = os.environ.get("LBG_GATEWAY_IA_BACKEND_TOKEN", os.environ.get("MMMORPG_IA_BACKEND_TOKEN", "")).strip()
IA_TIMEOUT_S = float(
    os.environ.get("LBG_GATEWAY_IA_TIMEOUT_S", os.environ.get("MMMORPG_IA_TIMEOUT_S", "45"))
)
PLACEHOLDER_ENABLED = os.environ.get("LBG_GATEWAY_IA_PLACEHOLDER", "1").strip().lower() not in (
    "0",
    "false",
    "no",
)


def ia_configured() -> bool:
    return bool(IA_URL) and httpx is not None


def placeholder_reply(npc_name: str | None) -> str:
    label = (npc_name or "PNJ").strip() or "PNJ"
    return f"{label} réfléchit…"


def _extract_reply(payload: dict[str, Any]) -> tuple[str, str]:
    tid = str(payload.get("trace_id") or uuid.uuid4().hex)
    res = payload.get("result")
    out = res.get("output") if isinstance(res, dict) else None
    remote = out.get("remote") if isinstance(out, dict) else None
    rep = remote.get("reply") if isinstance(remote, dict) else None
    if isinstance(rep, str) and rep.strip():
        return rep.strip(), tid
    err = payload.get("error")
    if isinstance(err, str) and err.strip():
        return err.strip()[:500], tid
    return "Désolé, je ne peux pas répondre pour l'instant.", tid


async def fetch_npc_reply(
    *,
    actor_id: str,
    text: str,
    world_npc_id: str,
    npc_name: str | None = None,
    ia_context: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Appelle le backend IA ; retourne (réplique, trace_id)."""
    world_npc_id = world_npc_id.strip()
    text = text.strip()
    if not text or not world_npc_id:
        return "Message vide.", "prime-empty"
    if not ia_configured():
        return (
            f"[Prime] Pont IA absent — définir LBG_GATEWAY_IA_BACKEND_URL sur la VM. Vous: {text[:100]}",
            "prime-no-backend",
        )

    ctx: dict[str, Any] = dict(ia_context) if isinstance(ia_context, dict) else {}
    ctx.setdefault("world_npc_id", world_npc_id)
    ctx.setdefault("history", [])
    ctx.setdefault("lyra_engagement", "mmo_persona")
    ctx.setdefault("planet_id", "tatooine")
    ctx.setdefault("zone", "mos_eisley")
    if npc_name and npc_name.strip():
        ctx["npc_name"] = npc_name.strip()

    payload = {"actor_id": actor_id, "text": text, "context": ctx}
    tid = uuid.uuid4().hex
    headers: dict[str, str] = {"X-LBG-Trace-Id": tid}
    if IA_TOKEN:
        headers["X-LBG-Service-Token"] = IA_TOKEN

    timeout = httpx.Timeout(timeout=IA_TIMEOUT_S, connect=3.0, read=IA_TIMEOUT_S, write=10.0)
    url = f"{IA_URL}{IA_PATH}"
    try:
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            r = await client.post(url, json=payload, headers=headers)
        if r.status_code != 200:
            LOG.warning("IA HTTP %s %s trace_id=%s", r.status_code, url, tid)
            return "Désolé, le service IA est indisponible.", tid
        data = r.json()
        if not isinstance(data, dict):
            return "Réponse IA invalide.", tid
        return _extract_reply(data)
    except Exception:
        LOG.exception("IA call failed trace_id=%s npc=%s", tid, world_npc_id)
        return "Désolé, je ne peux pas t'aider maintenant.", tid
