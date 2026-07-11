"""Résumés lisibles pour validation humaine (#/team)."""

from __future__ import annotations

from typing import Any


def _icon(ok: bool | None, skipped: bool = False) -> str:
    if skipped:
        return "⏭"
    if ok is True:
        return "✅"
    if ok is False:
        return "❌"
    return "·"


def format_probe_lines(probes: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for p in probes:
        if not isinstance(p, dict):
            continue
        track = str(p.get("track") or "probe")
        skipped = bool(p.get("skipped"))
        ok = p.get("ok") if not skipped else None
        line = f"{_icon(bool(ok) if ok is not None else None, skipped)} [{track}]"
        if p.get("hint"):
            line += f" — {p['hint']}"
        elif p.get("error"):
            line += f" — {p['error']}"
        elif isinstance(p.get("gaps"), list) and p["gaps"]:
            line += f" — {p['gaps'][0]}"
        elif track == "zb0_readiness":
            checks = p.get("checks") if isinstance(p.get("checks"), dict) else {}
            hook = checks.get("zone_server_zb_hook")
            hdr = checks.get("zb0_header")
            line += f" — header={hdr} hook={hook}"
        elif track in ("soe_m3_login", "soe_m3_zone", "soe_m5_play"):
            line += f" — host={p.get('host', '?')}"
        lines.append(line)
    return lines


def format_validation_summary(
    *,
    title: str,
    probes: list[dict[str, Any]] | None = None,
    checklist: list[str] | None = None,
    forge_note: str | None = None,
    build_plan: dict[str, Any] | None = None,
) -> str:
    parts: list[str] = [title, ""]
    if probes:
        parts.append("Sondes")
        parts.extend(format_probe_lines(probes))
        parts.append("")
    if build_plan:
        parts.append("Plan build Core3")
        host = build_plan.get("host") or "?"
        parts.append(f"  VM cible : {host}")
        steps = build_plan.get("steps") if isinstance(build_plan.get("steps"), list) else []
        for i, step in enumerate(steps[:6], 1):
            parts.append(f"  {i}. {step}")
        if build_plan.get("log_path"):
            parts.append(f"  Log : {build_plan['log_path']}")
        if build_plan.get("dry_run"):
            parts.append("  → L2 requis pour lancer le build (preset Compiler Core3 + token)")
        parts.append("")
    if forge_note:
        parts.append(f"Forge : {forge_note}")
        parts.append("")
    if checklist:
        parts.append("Checklist humain (rapide)")
        for item in checklist:
            parts.append(f"  □ {item}")
    return "\n".join(parts).strip()
