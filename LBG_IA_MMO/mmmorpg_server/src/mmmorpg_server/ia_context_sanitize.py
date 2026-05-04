"""Sanitisation du contexte client → pont IA (borné, liste blanche)."""

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


def sanitize_session_summary(raw: object) -> dict[str, str] | None:
    """
    Résumé session volontaire (ADR 0004) : clés courtes, valeurs string courtes ou bool/int bornés.
    Toute autre clé est ignorée.
    """
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


def _memory_hint_from_npc_flags(flags: dict[str, Any] | None) -> str | None:
    """Indice léger « mémoire monde » : noms de clés flags PNJ (sans valeurs), ordre stable."""
    if not isinstance(flags, dict) or not flags:
        return None
    keys = sorted(str(k)[:32] for k in flags.keys())[:12]
    s = ",".join(keys)
    return s[:160] if s else None


def build_server_session_summary_parts(
    *,
    quest_state: dict[str, Any] | None,
    npc_id: str,
    npc_name: str | None,
    npc_flags: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Données autoritatives monde (quête joueur + interlocuteur + indice flags PNJ) — fusionnées avant le client."""
    parts: dict[str, str] = {}
    nn = npc_name.strip() if isinstance(npc_name, str) and npc_name.strip() else ""
    nid = (npc_id or "").strip()
    if nn:
        parts["last_npc"] = nn[:160]
    elif nid:
        parts["last_npc"] = nid[:160]
    if isinstance(quest_state, dict):
        qid = quest_state.get("quest_id")
        if isinstance(qid, str) and qid.strip():
            tid = qid.strip()[:80]
            try:
                si = int(quest_state.get("quest_step", 0))
            except (TypeError, ValueError):
                si = 0
            st = quest_state.get("status")
            st_s = st.strip()[:20] if isinstance(st, str) and st.strip() else ""
            parts["tracked_quest"] = f"{tid} (étape {si})"[:160]
            qline = f"id={tid} step={si}"
            if st_s:
                qline += f" status={st_s}"
            parts["quest_snapshot"] = qline[:160]
    mh = _memory_hint_from_npc_flags(npc_flags)
    if mh:
        parts["memory_hint"] = mh
    return parts


def merge_session_summaries(*, server_parts: dict[str, str], client_raw: object) -> dict[str, str] | None:
    """
    Client : notes / humeur volontaires.
    Serveur : priment sur ``tracked_quest``, ``quest_snapshot``, ``last_npc`` (vérité monde).
    """
    client = sanitize_session_summary(client_raw) or {}
    merged: dict[str, str] = dict(client)
    for k, v in server_parts.items():
        if k in ("tracked_quest", "quest_snapshot", "last_npc", "memory_hint"):
            merged[k] = v
    return sanitize_session_summary(merged)
