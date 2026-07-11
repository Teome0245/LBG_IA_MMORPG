"""Export borné de session_summary / résumé assistant (Pilot, ADR 0004).

Ne persiste rien : validation et troncature côté serveur avant copie ou pont MMO.
"""

from __future__ import annotations

from typing import Any

SESSION_SUMMARY_KEYS = frozenset(
    {
        "tracked_quest",
        "last_npc",
        "player_note",
        "session_mood",
        "quest_snapshot",
        "memory_hint",
    }
)

MMO_BRIDGE_KEYS = frozenset({"source", "imported_at", "via"})


def sanitize_session_summary(raw: object) -> dict[str, str] | None:
    if not isinstance(raw, dict):
        return None
    out: dict[str, str] = {}
    for k, v in raw.items():
        if not isinstance(k, str) or k not in SESSION_SUMMARY_KEYS:
            continue
        if isinstance(v, str):
            s = v.strip()
            if not s:
                continue
            out[k] = s[:160] if len(s) > 160 else s
        elif isinstance(v, bool):
            out[k] = "true" if v else "false"
        elif isinstance(v, int) and not isinstance(v, bool) and -10_000 <= v <= 10_000:
            out[k] = str(int(v))
    return out if out else None


def sanitize_mmo_bridge(raw: object) -> dict[str, str] | None:
    if not isinstance(raw, dict):
        return None
    out: dict[str, str] = {}
    for k, v in raw.items():
        if not isinstance(k, str) or k not in MMO_BRIDGE_KEYS:
            continue
        if isinstance(v, str):
            s = v.strip()
            if s:
                out[k] = s[:120] if len(s) > 120 else s
    return out if out else None


def sanitize_history(
    raw: object,
    *,
    max_items: int = 12,
    max_text_len: int = 500,
) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in raw[:max_items]:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        if not isinstance(kind, str) or not kind.strip():
            continue
        row: dict[str, str] = {"kind": kind.strip()[:64]}
        for key in ("capability", "policy_decision", "ts"):
            val = item.get(key)
            if isinstance(val, str) and val.strip():
                row[key] = val.strip()[:120]
        text = item.get("text") or item.get("summary")
        if isinstance(text, str) and text.strip():
            row["text"] = text.strip()[:max_text_len]
        out.append(row)
    return out


def build_assistant_session_export(payload: dict[str, Any]) -> dict[str, object]:
    notes_raw = payload.get("notes")
    notes = ""
    if isinstance(notes_raw, str):
        notes = notes_raw.strip()[:2000]

    history = sanitize_history(payload.get("history"))
    session_summary = sanitize_session_summary(payload.get("session_summary"))
    mmo_bridge = sanitize_mmo_bridge(payload.get("mmo_bridge"))

    export: dict[str, object] = {
        "kind": "assistant_voluntary_session_summary",
        "voluntary": True,
        "sanitized": True,
        "pilot_view": "#/assistant",
    }
    if notes:
        export["notes"] = notes
    if history:
        export["history"] = history
    if session_summary:
        export["session_summary"] = session_summary
    if mmo_bridge:
        export["mmo_bridge"] = mmo_bridge

    dropped: list[str] = []
    if isinstance(payload.get("session_summary"), dict) and not session_summary:
        dropped.append("session_summary")
    if isinstance(payload.get("mmo_bridge"), dict) and not mmo_bridge:
        dropped.append("mmo_bridge")
    if dropped:
        export["dropped_keys"] = dropped

    return export
