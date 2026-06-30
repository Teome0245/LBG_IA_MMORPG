"""Plans de remédiation stockage Proxmox / Prime (pool thin local-lvm)."""

from __future__ import annotations

import os
from typing import Any


def _truthy(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def storage_auto_hygiene_enabled() -> bool:
    return _truthy(os.environ.get("LBG_STORAGE_AUTO_HYGIENE", "1"))


def build_storage_remediation_plan(
    storage_payload: dict[str, Any] | None = None,
    *,
    watchdog_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construit remediation_plan à partir de la sonde stockage."""
    storage = storage_payload
    if storage is None and isinstance(watchdog_payload, dict):
        block = watchdog_payload.get("storage")
        if isinstance(block, dict):
            inner = block.get("storage") if isinstance(block.get("storage"), dict) else block
            storage = inner

    if not isinstance(storage, dict):
        return {
            "kind": "remediation_plan",
            "source": "proxmox_storage",
            "outcome": "ok",
            "hints": ["Sonde stockage absente — rien à remédier."],
            "suggested_actions": [],
        }

    outcome = str(storage.get("outcome") or "ok")
    data_pct = storage.get("data_percent")
    vm246 = str(storage.get("vm_prime_status") or storage.get("vm246_status") or "")
    vg_free = str(storage.get("vg_free") or "")
    pve_host = str(storage.get("host") or "192.168.0.201")
    hints: list[str] = []
    actions: list[dict[str, Any]] = []

    host_rows = storage.get("hosts") if isinstance(storage.get("hosts"), list) else []
    stressed_hosts = [
        h for h in host_rows
        if isinstance(h, dict) and h.get("ok") and str(h.get("outcome")) in {"warn", "critical"}
    ]

    if outcome == "ok" and "io-error" not in vm246 and not stressed_hosts:
        return {
            "kind": "remediation_plan",
            "source": "proxmox_storage",
            "outcome": "ok",
            "data_percent": data_pct,
            "hints": [f"Pool(s) thin OK ({data_pct}%)"],
            "suggested_actions": [],
        }

    for row in stressed_hosts:
        hints.append(
            f"PVE {row.get('host')} : pool thin {row.get('data_percent')}% — VG libre {row.get('vg_free')}"
        )

    if "io-error" in vm246:
        hints.append("VM 246 en io-error : redémarrer Prime après libération du pool thin.")
        actions.append(
            {
                "level": "manual",
                "label": f"Proxmox {pve_host or '201'} : lvextend -l +100%FREE pve/data puis qm stop/start 246",
                "command_hint": "lvextend -l +100%FREE pve/data && qm stop 246 --skiplock && qm start 246",
            }
        )

    if outcome in {"warn", "critical"} or stressed_hosts:
        if not hints:
            hints.append(f"Pool thin local-lvm à {data_pct}% — risque io-error sur Prime.")
        if storage_auto_hygiene_enabled():
            actions.append(
                {
                    "level": "safe",
                    "label": "Prime 246 : hygiène disque build Antigravity (SSH allowlist)",
                    "devops_action": {
                        "kind": "ssh_run",
                        "server_id": "prime",
                        "command": "rm -rf /opt/lbg-antigravity/lbg-mmo/build && :> /tmp/core3-antigravity-build.log && df -h /",
                    },
                    "requires_approval": True,
                }
            )
        if vg_free and vg_free not in {"0", "0.00g", "<0"}:
            actions.append(
                {
                    "level": "manual",
                    "label": f"Étendre le pool thin sur {pve_host or 'PVE'} (VG libre {vg_free})",
                    "command_hint": "lvextend -l +100%FREE pve/data",
                }
            )
        hints.append("Doc : docs/runbook_proxmox_storage_prime.md")

    return {
        "kind": "remediation_plan",
        "source": "proxmox_storage",
        "outcome": outcome,
        "data_percent": data_pct,
        "vm246_status": vm246,
        "hints": hints,
        "suggested_actions": actions,
        "next_steps": [
            "Approuver le job Pilot pour apply hygiene SSH si proposé.",
            "Surveiller Proxmox : bash infra/scripts/check_proxmox_storage_lan.sh",
        ],
    }


def format_storage_plan_reply(plan: dict[str, Any]) -> str:
    lines = [
        "Plan remédiation stockage Proxmox / Prime",
        f"État : {plan.get('outcome')} — pool {plan.get('data_percent')}% — VM246 {plan.get('vm246_status', '?')}",
    ]
    for h in plan.get("hints") or []:
        lines.append(f"  → {h}")
    for i, a in enumerate(plan.get("suggested_actions") or [], 1):
        if isinstance(a, dict):
            lines.append(f"  {i}. [{a.get('level')}] {a.get('label')}")
    return "\n".join(lines)
