"""Watchdog infra LAN (core 140) — Proxmox + mémoire VM, sans Prime pendant rebuild."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from lbg_agents.infra_memory_remediation import build_memory_remediation_plan
from lbg_agents.proxmox_client import proxmox_configured
from lbg_agents.proxmox_probe import run_proxmox_status
from lbg_agents.vm_memory_probe import run_vm_memory_probe


def _truthy(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def watchdog_enabled() -> bool:
    return _truthy(os.environ.get("LBG_INFRA_WATCHDOG_ENABLED", "1"))


def watchdog_state_path() -> Path:
    raw = os.environ.get("LBG_INFRA_WATCHDOG_STATE", "").strip()
    if raw:
        return Path(raw)
    return Path(os.environ.get("HOME", "/var/lib/lbg")) / ".local/state/lbg/infra_watchdog/state.json"


def _worst(*levels: str) -> str:
    rank = {"ok": 0, "skipped": 0, "skipped_not_configured": 0, "warn": 1, "critical": 2, "forbidden": 2}
    worst = "ok"
    for lv in levels:
        if rank.get(lv, 0) > rank.get(worst, 0):
            worst = lv
    return worst


def _normalize_outcome(raw: str | None) -> str:
    v = (raw or "ok").strip().lower()
    if v in {"critical", "forbidden"}:
        return "critical"
    if v == "warn":
        return "warn"
    return "ok"


def run_infra_watchdog(
    *,
    actor_id: str = "infra_watchdog",
    persist: bool = True,
) -> dict[str, Any]:
    """Sonde Proxmox (si token) + mémoire SSH (core/front/precu, Prime exclu par défaut)."""
    if not watchdog_enabled():
        return {
            "ok": True,
            "agent": "infra_watchdog",
            "outcome": "skipped",
            "reply": "Watchdog désactivé (LBG_INFRA_WATCHDOG_ENABLED=0).",
        }

    exclude_prime = _truthy(os.environ.get("LBG_INFRA_WATCHDOG_EXCLUDE_PRIME", "1"))
    alerts: list[str] = []
    sections: list[str] = []

    proxmox_block: dict[str, Any]
    if proxmox_configured():
        proxmox_block = run_proxmox_status(actor_id=actor_id, text="infra watchdog", context={})
        sections.append("=== Proxmox ===\n" + str(proxmox_block.get("reply", "")))
        alerts.extend(proxmox_block.get("alerts") or [])
    else:
        proxmox_block = {
            "ok": True,
            "outcome": "skipped_not_configured",
            "reply": "Proxmox : token absent (LBG_PROXMOX_TOKEN).",
        }
        sections.append("=== Proxmox ===\n" + proxmox_block["reply"])

    mem_block = run_vm_memory_probe(actor_id=actor_id, text="infra watchdog", context={})
    if mem_block.get("ok"):
        sections.append("=== Mémoire VM ===\n" + str(mem_block.get("reply", "")))
        for entry in mem_block.get("hosts") or []:
            if not isinstance(entry, dict):
                continue
            if not entry.get("ok"):
                alerts.append(f"mem:{entry.get('label')}: {entry.get('error', 'KO')}")
            elif entry.get("status") in {"warn", "critical"}:
                alerts.append(f"mem:{entry.get('label')}: {entry.get('status')}")
    else:
        sections.append("=== Mémoire VM ===\n" + str(mem_block.get("error", mem_block.get("reply", "KO"))))
        if mem_block.get("outcome") == "forbidden":
            alerts.append("mem: sonde désactivée (SSH)")

    from lbg_agents.proxmox_storage_probe import run_proxmox_storage_probe
    from lbg_agents.infra_storage_remediation import build_storage_remediation_plan

    storage_block = run_proxmox_storage_probe(actor_id=actor_id, text="infra watchdog")
    storage_inner = storage_block.get("storage") if isinstance(storage_block.get("storage"), dict) else {}
    sections.append("=== Stockage Proxmox ===\n" + str(storage_block.get("reply", "")))
    if not storage_block.get("ok"):
        alerts.append(f"storage: {storage_block.get('error', 'KO')}")
    elif storage_inner.get("outcome") in {"warn", "critical"}:
        alerts.append(f"storage:thin_pool:{storage_inner.get('outcome')}")
    if str(storage_inner.get("vm246_status") or "").find("io-error") >= 0:
        alerts.append("storage:vm246:io-error")

    if exclude_prime:
        sections.append("=== Prime 246 ===\nexclu (LBG_INFRA_WATCHDOG_EXCLUDE_PRIME=1 — rebuild en cours)")

    prox_out = _normalize_outcome(str(proxmox_block.get("outcome")))
    mem_out = _normalize_outcome(str(mem_block.get("worst_status") or mem_block.get("outcome")))
    stor_out = _normalize_outcome(str(storage_inner.get("outcome") or storage_block.get("outcome")))
    outcome = _worst(prox_out, mem_out, stor_out)

    payload: dict[str, Any] = {
        "ok": True,
        "agent": "infra_watchdog",
        "outcome": outcome,
        "ts": time.time(),
        "exclude_prime": exclude_prime,
        "proxmox": proxmox_block,
        "memory": mem_block,
        "storage": storage_block,
        "alerts": alerts,
        "reply": "\n\n".join(sections),
    }

    if outcome in {"warn", "critical"}:
        mem_plan = build_memory_remediation_plan(payload)
        stor_plan = build_storage_remediation_plan(storage_payload=storage_inner)
        payload["remediation_plan"] = mem_plan
        payload["storage_remediation_plan"] = stor_plan
        hints = list(mem_plan.get("hints") or []) + list(stor_plan.get("hints") or [])
        if hints:
            payload["remediation_hints"] = hints

    if persist:
        path = watchdog_state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
        payload["state_path"] = str(path)

    return payload


def main() -> int:
    result = run_infra_watchdog()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    outcome = str(result.get("outcome") or "ok")
    if outcome == "critical":
        return 2
    if outcome == "warn":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
