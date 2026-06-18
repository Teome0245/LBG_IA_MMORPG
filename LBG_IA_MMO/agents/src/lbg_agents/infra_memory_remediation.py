"""Plans de remédiation RAM — infra watchdog + mémoire VM (Track C)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _truthy(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def remediation_prime_enabled() -> bool:
    """Autorise de proposer un restart Prime dans le plan (apply reste sous approbation)."""
    return _truthy(os.environ.get("LBG_REMEDIATION_PRIME_ENABLED", "0"))


def host_systemd_units() -> dict[str, str]:
    """Label sonde mémoire → unité systemd suggérée pour restart."""
    raw = os.environ.get("LBG_REMEDIATION_HOST_UNITS", "").strip()
    if raw:
        out: dict[str, str] = {}
        for part in raw.split(","):
            p = part.strip()
            if "=" in p:
                label, unit = p.split("=", 1)
                out[label.strip().lower()] = unit.strip()
        if out:
            return out
    return {
        "prime": "lbg-core3-prime.service",
        "precu": "lbg-core3-precu.service",
        "front": "nginx.service",
        "core": "lbg-orchestrator.service",
    }


def _format_metrics(entry: dict[str, Any]) -> str:
    m = entry.get("metrics") if isinstance(entry.get("metrics"), dict) else {}
    avail = m.get("mem_avail_pct", "?")
    swap = m.get("swap_used_pct", 0)
    top = m.get("top_processes") or []
    top_s = top[0].get("comm", "?") if top else "?"
    return f"dispo {avail}% — top {top_s}" + (f" — swap {swap}%" if float(swap or 0) > 10 else "")


def build_memory_remediation_plan(
    watchdog_payload: dict[str, Any],
    *,
    include_prime_restart: bool | None = None,
) -> dict[str, Any]:
    """Construit un plan remediation_plan à partir du résultat infra_watchdog."""
    mem = watchdog_payload.get("memory") if isinstance(watchdog_payload.get("memory"), dict) else {}
    hosts = mem.get("hosts") if isinstance(mem.get("hosts"), list) else []
    worst = str(mem.get("worst_status") or watchdog_payload.get("outcome") or "ok")
    units = host_systemd_units()
    prime_ok = remediation_prime_enabled() if include_prime_restart is None else include_prime_restart

    hints: list[str] = []
    suggestions: list[dict[str, Any]] = []

    stressed: list[dict[str, Any]] = []
    for entry in hosts:
        if not isinstance(entry, dict) or not entry.get("ok"):
            continue
        st = str(entry.get("status") or "ok")
        if st in {"warn", "critical"}:
            stressed.append(entry)

    if not stressed and worst in {"warn", "critical"}:
        hints.append(f"Sonde mémoire globale : {worst} (détail hosts vide).")
    elif not stressed:
        return {
            "kind": "remediation_plan",
            "source": "infra_memory",
            "memory_worst_status": worst,
            "selfcheck_ok": True,
            "hints": ["Mémoire VM : aucun hôte en warn/critical — pas d'action RAM proposée."],
            "suggested_actions": [],
            "next_steps": [],
        }

    for entry in stressed:
        label = str(entry.get("label") or "?")
        host = str(entry.get("host") or "?")
        st = str(entry.get("status") or "warn")
        hints.append(f"{label} ({host}) [{st}] : {_format_metrics(entry)}")

    suggestions.append(
        {
            "level": "safe",
            "label": "Re-sonder watchdog infra (Proxmox + mémoire)",
            "devops_action": {"kind": "infra_watchdog"},
            "requires_approval": False,
        }
    )
    suggestions.append(
        {
            "level": "safe",
            "label": "Plan remédiation mémoire (lecture)",
            "devops_action": {"kind": "memory_remediation_plan"},
            "requires_approval": False,
        }
    )

    for entry in stressed:
        label = str(entry.get("label") or "").lower()
        host = str(entry.get("host") or "")
        st = str(entry.get("status") or "warn")
        unit = units.get(label)
        if label == "prime":
            suggestions.append(
                {
                    "level": "manual",
                    "label": "Prime (246) : sonde locale + restart optionnel",
                    "command_hint": (
                        "ssh lbg@192.168.0.246 "
                        "'bash /opt/LBG_IA_MMO/infra/scripts/watch_vm_memory_health.sh --json'"
                    ),
                }
            )
            if not prime_ok:
                hints.append(
                    "Prime : restart non proposé via orchestrateur (LBG_REMEDIATION_PRIME_ENABLED=0). "
                    "Utiliser watch_vm_memory_health.sh sur 246 avec LBG_VM_MEMORY_WATCHDOG_RESTART=1."
                )
                continue
        if not unit:
            continue
        if label == "prime" and not prime_ok:
            continue
        suggestions.append(
            {
                "level": "safe" if st == "warn" else "elevated",
                "label": f"Redémarrer {unit} — {label} RAM {st}",
                "devops_action": {"kind": "systemd_restart", "unit": unit},
                "requires_approval": True,
                "target_host": host,
                "note": (
                    "systemd_restart s'exécute sur l'hôte de l'orchestrateur ; "
                    "sur Prime utiliser ssh_run allowlisté ou script local 246."
                ),
            }
        )
        suggestions.append(
            {
                "level": "manual",
                "label": f"Diagnostic {unit} : journalctl -u {unit} -n 80",
                "command_hint": f"journalctl -u {unit} -n 80 --no-pager",
            }
        )

    return {
        "kind": "remediation_plan",
        "source": "infra_memory",
        "memory_worst_status": worst,
        "selfcheck_ok": worst == "ok",
        "stressed_hosts": [
            {"label": e.get("label"), "host": e.get("host"), "status": e.get("status")}
            for e in stressed
        ],
        "hints": hints,
        "suggested_actions": _dedupe_actions(suggestions),
        "next_steps": [
            "Relancer infra_watchdog pour confirmer l'alerte.",
            "Appliquer une action safe via remediation_apply + devops_approval (hors dry-run).",
            "Valider avec remediation_validate ou nouveau watchdog.",
        ],
    }


def _dedupe_actions(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for it in items:
        key = str(it.get("devops_action")) + "|" + str(it.get("command_hint")) + "|" + str(it.get("label"))
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def format_memory_plan_reply(plan: dict[str, Any]) -> str:
    lines = [
        "Plan remédiation RAM (suggestions — apply explicite + approbation si restart)",
        f"Statut mémoire pire : {plan.get('memory_worst_status', '?')}",
    ]
    for h in plan.get("hints") or []:
        if isinstance(h, str) and h.strip():
            lines.append(f"  → {h.strip()}")
    actions = plan.get("suggested_actions") or []
    if actions:
        lines.append("Actions proposées :")
        for i, a in enumerate(actions[:10], 1):
            if isinstance(a, dict):
                appr = " [approbation]" if a.get("requires_approval") else ""
                lines.append(f"  {i}. [{a.get('level', '?')}] {a.get('label', '?')}{appr}")
    return "\n".join(lines)


def load_watchdog_state(path: Path | None = None) -> dict[str, Any] | None:
    raw = os.environ.get("LBG_INFRA_WATCHDOG_STATE", "").strip()
    p = path or (Path(raw) if raw else None)
    if p is None or not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None
