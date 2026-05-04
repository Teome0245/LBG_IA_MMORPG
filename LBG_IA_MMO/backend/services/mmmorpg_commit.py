from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_ALLOWED_FLAG_KEYS: set[str] = {
    "quest_accepted",
    "quest_completed",
    "quest_id",
    "quest_step",
    "mood",
    "rp_tone",
    "reputation_delta",
    # Gameplay v1 (commit WS) : deltas bornés appliqués côté serveur WS.
    "aid_hunger_delta",
    "aid_thirst_delta",
    "aid_fatigue_delta",
    "aid_reputation_delta",
    # Inventaire joueur (session) : ``player_id`` requis côté HTTP interne / pont WS.
    "player_item_id",
    "player_item_qty_delta",
    "player_item_label",
}


def _allowed_flag_keys() -> set[str]:
    raw = os.environ.get("LBG_MMMORPG_COMMIT_ALLOWED_FLAGS", "").strip()
    if not raw:
        return set(_DEFAULT_ALLOWED_FLAG_KEYS)
    out: set[str] = set()
    for part in raw.split(","):
        k = (part or "").strip()
        if not k:
            continue
        out.add(k)
    return out or set(_DEFAULT_ALLOWED_FLAG_KEYS)


def _int_env(name: str, default: int) -> int:
    try:
        v = int(os.environ.get(name, str(default)) or str(default))
        return v
    except Exception:
        return default


def _commit_limits() -> tuple[int, int, int]:
    # Best-effort : cohérent avec les gardes-fous côté serveur jeu, mais configurables.
    max_flags = _int_env("LBG_MMMORPG_COMMIT_MAX_FLAGS", 16)
    max_key_len = _int_env("LBG_MMMORPG_COMMIT_MAX_KEY_LEN", 64)
    max_str_len = _int_env("LBG_MMMORPG_COMMIT_MAX_STR_LEN", 256)
    return max(1, max_flags), max(1, max_key_len), max(1, max_str_len)


def _validate_and_sanitize_flags(flags: dict[str, Any] | None) -> tuple[dict[str, Any] | None, list[str]]:
    """
    Validation/sanitation côté backend (avant appel HTTP interne).
    - whitelist config-driven
    - limites (nb, tailles)
    - types JSON simples uniquement
    """
    if flags is None:
        return None, []
    if not isinstance(flags, dict) or not flags:
        return None, ["flags must be an object (non-empty)"]

    allowed = _allowed_flag_keys()
    max_flags, max_key_len, max_str_len = _commit_limits()
    if len(flags) > max_flags:
        return None, [f"too many flags (got={len(flags)} max={max_flags})"]

    out: dict[str, Any] = {}
    errors: list[str] = []
    for k, v in flags.items():
        if not isinstance(k, str):
            errors.append("flag key must be string")
            continue
        key = k.strip()
        if not key:
            errors.append("flag key must be non-empty")
            continue
        if len(key) > max_key_len:
            errors.append(f"flag key too long: {key[:40]}")
            continue
        if key not in allowed:
            # Contract : non autorisé => on ignore côté backend (le serveur jeu revalidera).
            continue

        if isinstance(v, str):
            vv = v.strip()
            if len(vv) > max_str_len:
                errors.append(f"flag value too long for key={key}")
                continue
            out[key] = vv
        elif isinstance(v, (bool, int, float)) or v is None:
            out[key] = v
        else:
            errors.append(f"unsupported flag value type for key={key}")

    return out or None, errors


def _commit_base() -> str:
    return os.environ.get("LBG_MMMORPG_INTERNAL_HTTP_URL", "").strip().rstrip("/")


def _commit_token() -> str:
    return os.environ.get("LBG_MMMORPG_INTERNAL_HTTP_TOKEN", "").strip()


async def try_commit_dialogue(
    *,
    trace_id: str,
    npc_id: str,
    flags: dict[str, Any] | None,
    player_id: str | None = None,
) -> dict[str, Any] | None:
    """
    Tente d'appliquer un commit "dialogue" sur le serveur WS (mmmorpg) via son HTTP interne.

    Retourne un dict sérialisable (commit_result) ou None si non configuré.
    Ne lève pas : toute erreur est encapsulée dans `ok: False` (ou retourne None si disabled).
    """
    base = _commit_base()
    if not base:
        return None

    npc_id = (npc_id or "").strip()
    trace_id = (trace_id or "").strip()
    if not npc_id or not trace_id:
        return {"ok": False, "attempted": True, "error": "missing npc_id/trace_id"}

    headers = {}
    token = _commit_token()
    if token:
        headers["X-LBG-Service-Token"] = token

    payload: dict[str, Any] = {"trace_id": trace_id}
    cleaned_flags, errors = _validate_and_sanitize_flags(flags)
    if errors:
        return {"ok": False, "attempted": True, "error": "invalid_commit_flags", "details": errors[:10]}
    if cleaned_flags is not None:
        payload["flags"] = cleaned_flags
    pid = (player_id or "").strip()
    if pid:
        payload["player_id"] = pid

    url = f"{base}/internal/v1/npc/{npc_id}/dialogue-commit"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.post(url, json=payload, headers=headers or None)
        # 200 => accepted, 409 => rejected (voir serveur)
        if r.status_code not in (200, 409):
            return {"ok": False, "attempted": True, "http_status": r.status_code, "body": (r.text or "")[:500]}
        data = r.json()
        if not isinstance(data, dict):
            return {"ok": False, "attempted": True, "http_status": r.status_code, "error": "non-dict json"}
        return {"ok": True, "attempted": True, "http_status": r.status_code, **data}
    except Exception as e:
        logger.info("mmmorpg commit failed (npc_id=%s trace_id=%s): %s", npc_id, trace_id, e)
        return {"ok": False, "attempted": True, "error": str(e)}

