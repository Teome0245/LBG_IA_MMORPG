"""Synthèse infra pour Pilot / Assistant — jobs, Proxmox API, stockage, GPU front."""

from __future__ import annotations

import re
import time
from typing import Any

from services import jobs as svc_jobs

_INFRA_ACTOR_PREFIX = "system:"
_INFRA_OBJECTIVE_RE = re.compile(
    r"\b(proxmox|stockage|storage|infra|mémoire|memoire|ram|watchdog|prime|246|thin|local-lvm)\b",
    re.I,
)

_LAN_LABEL_FR = {
    "core": "Core 140",
    "front": "Front 110",
    "precu": "Précu 245",
    "prime": "Prime 246",
}


def _is_infra_job(job: svc_jobs.Job) -> bool:
    aid = (job.actor_id or "").strip()
    if aid.startswith(_INFRA_ACTOR_PREFIX):
        return True
    return bool(_INFRA_OBJECTIVE_RE.search(job.objective or ""))


def _job_card(job: svc_jobs.Job) -> dict[str, Any]:
    return {
        "id": job.id,
        "actor_id": job.actor_id,
        "objective": job.objective,
        "status": job.status,
        "result_summary": job.result_summary,
        "n_steps": len(job.steps),
        "updated_ts": job.updated_ts,
    }


def _vm_dashboard_row(label: str, row: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    vid = row.get("vmid")
    st_wrap = row.get("status") if isinstance(row.get("status"), dict) else {}
    inner = st_wrap.get("status") if isinstance(st_wrap.get("status"), dict) else st_wrap
    if not isinstance(inner, dict):
        inner = {}
    mem_pct = inner.get("mem_pct")
    cpu_pct = inner.get("cpu_pct")
    state = str(inner.get("status") or inner.get("qmpstatus") or "?")
    return {
        "label": label,
        "label_fr": _LAN_LABEL_FR.get(label, label),
        "vmid": vid,
        "status": state,
        "mem_pct": mem_pct,
        "cpu_pct": cpu_pct,
    }


def _fetch_proxmox_snapshot() -> dict[str, Any] | None:
    try:
        from lbg_agents.proxmox_client import proxmox_configured
        from lbg_agents.proxmox_probe import run_proxmox_status

        if not proxmox_configured():
            return {"ok": False, "skipped": "proxmox_not_configured"}
        return run_proxmox_status(actor_id="system:infra_alerts", text="", context={})
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _fetch_gpu_snapshot() -> dict[str, Any] | None:
    try:
        from lbg_agents.gpu_host_probe import probe_front_gpu

        return probe_front_gpu()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _format_summary_fr(
    *,
    waiting: list[dict[str, Any]],
    active: list[dict[str, Any]],
    recent: list[dict[str, Any]],
    storage_probe: dict[str, Any] | None,
    proxmox_snapshot: dict[str, Any] | None,
    gpu_probe: dict[str, Any] | None,
    vm_dashboard: list[dict[str, Any]],
) -> str:
    lines: list[str] = []

    if vm_dashboard:
        vm_bits = []
        for v in vm_dashboard:
            mp = v.get("mem_pct")
            st = v.get("status", "?")
            name = v.get("label_fr") or v.get("label")
            if mp is not None:
                vm_bits.append(f"{name} RAM {mp}% ({st})")
            else:
                vm_bits.append(f"{name} ({st})")
        if vm_bits:
            lines.append("VM LAN : " + " · ".join(vm_bits) + ".")

    if proxmox_snapshot and proxmox_snapshot.get("ok"):
        px_alerts = proxmox_snapshot.get("alerts") or []
        if px_alerts:
            lines.append("Proxmox : " + "; ".join(str(a) for a in px_alerts[:4]))
        elif not lines:
            lines.append(
                f"Proxmox {proxmox_snapshot.get('cluster', {}).get('host', '?')} : "
                "VMs suivies — pas d'alerte RAM/charge."
            )
    elif proxmox_snapshot and proxmox_snapshot.get("skipped"):
        lines.append("Proxmox API : token non configuré (LBG_PROXMOX_TOKEN).")

    if gpu_probe and gpu_probe.get("ok"):
        go = str(gpu_probe.get("outcome") or "ok")
        if go not in {"ok", "skipped_no_pci"}:
            lines.append(f"GPU front (110) : {gpu_probe.get('summary_fr', go)}")
        elif go == "ok" and gpu_probe.get("driver_usable"):
            lines.append("GPU M2090 (110) : opérationnelle (nvidia-smi OK).")

    if storage_probe:
        if storage_probe.get("ok"):
            outcome = storage_probe.get("outcome", "ok")
            host = storage_probe.get("host", "?")
            pct = storage_probe.get("data_percent_raw") or storage_probe.get("data_percent")
            vm = storage_probe.get("vm_prime_status") or storage_probe.get("vm246_status")
            lines.append(f"Stockage ({host}) : thin {pct}% — Prime {vm} — {outcome}.")
        else:
            lines.append(f"Sonde stockage : {storage_probe.get('error', 'indisponible')}.")

    if waiting:
        lines.append(f"{len(waiting)} action(s) infra en attente de votre validation.")
        for w in waiting[:3]:
            obj = str(w.get("objective") or "")[:120]
            lines.append(f"  → Job {w.get('id', '?')[:8]}… : {obj}")
    elif not lines:
        lines.append("Aucune alerte infra critique — surveillance OK.")

    if active:
        lines.append(f"{len(active)} job(s) infra en cours d'exécution.")

    for r in recent[:2]:
        if r.get("status") == "failed" and r.get("result_summary"):
            lines.append(f"Dernier échec : {r['result_summary'][:200]}")

    return "\n".join(lines) if lines else "Surveillance infra : rien à signaler."


def _outcome_from_snapshots(
    *,
    waiting: list[dict[str, Any]],
    storage_probe: dict[str, Any] | None,
    proxmox_snapshot: dict[str, Any] | None,
    gpu_probe: dict[str, Any] | None,
    infra_jobs: list[svc_jobs.Job],
    vm_dashboard: list[dict[str, Any]],
) -> str:
    if waiting:
        return "waiting_approval"
    for v in vm_dashboard:
        mp = v.get("mem_pct")
        if isinstance(mp, (int, float)) and mp >= 92:
            return "critical"
    if proxmox_snapshot and proxmox_snapshot.get("outcome") == "critical":
        return "critical"
    if storage_probe and storage_probe.get("outcome") == "critical":
        return "critical"
    if proxmox_snapshot and proxmox_snapshot.get("outcome") == "warn":
        return "warn"
    if storage_probe and storage_probe.get("outcome") in ("warn", "critical"):
        return str(storage_probe["outcome"])
    if gpu_probe and gpu_probe.get("outcome") in ("warn", "critical"):
        return "warn"
    for v in vm_dashboard:
        mp = v.get("mem_pct")
        if isinstance(mp, (int, float)) and mp >= 85:
            return "warn"
    if any(j.status == "failed" for j in infra_jobs[:5]):
        return "warn"
    return "ok"


def build_infra_alerts(*, include_probe: bool = True) -> dict[str, Any]:
    """Agrège jobs, Proxmox API, stockage SSH et GPU front pour l'Assistant."""
    all_jobs = svc_jobs.list_jobs()
    infra_jobs = [j for j in all_jobs if _is_infra_job(j)]
    infra_jobs.sort(key=lambda j: float(j.updated_ts or 0), reverse=True)

    waiting = [_job_card(j) for j in infra_jobs if j.status == "waiting_approval"]
    active = [
        _job_card(j)
        for j in infra_jobs
        if j.status in ("running", "queued", "planning")
    ]
    recent = [
        _job_card(j)
        for j in infra_jobs
        if j.status in ("done", "failed")
    ][:8]

    storage_probe: dict[str, Any] | None = None
    proxmox_snapshot: dict[str, Any] | None = None
    gpu_probe: dict[str, Any] | None = None
    vm_dashboard: list[dict[str, Any]] = []

    if include_probe:
        try:
            from lbg_agents.proxmox_storage_probe import probe_proxmox_storage_local

            storage_probe = probe_proxmox_storage_local()
        except Exception as exc:
            storage_probe = {"ok": False, "error": str(exc)}

        proxmox_snapshot = _fetch_proxmox_snapshot()
        ssh_vms: dict[str, Any] | None = None
        try:
            from lbg_agents.proxmox_lan_ssh_probe import probe_lan_vms_ssh

            ssh_vms = probe_lan_vms_ssh()
        except Exception as exc:
            ssh_vms = {"ok": False, "error": str(exc)}

        from lbg_agents.proxmox_lan_ssh_probe import merge_vm_dashboard

        api_rows: list[dict[str, Any]] = []
        if proxmox_snapshot and proxmox_snapshot.get("ok"):
            lan = proxmox_snapshot.get("lan_vms") or {}
            matched = lan.get("matched") if isinstance(lan, dict) else {}
            if isinstance(matched, dict):
                for label, row in sorted(matched.items()):
                    dash = _vm_dashboard_row(label, row if isinstance(row, dict) else {})
                    if dash:
                        api_rows.append(dash)
        vm_dashboard = merge_vm_dashboard(api_rows, ssh_vms)

        if ssh_vms and ssh_vms.get("ok") and ssh_vms.get("alerts"):
            if not proxmox_snapshot or not isinstance(proxmox_snapshot, dict):
                proxmox_snapshot = {"ok": True, "outcome": ssh_vms.get("outcome"), "alerts": []}
            alerts = list(proxmox_snapshot.get("alerts") or [])
            for a in ssh_vms.get("alerts") or []:
                if a not in alerts:
                    alerts.append(a)
            proxmox_snapshot["alerts"] = alerts
            if ssh_vms.get("outcome") in ("warn", "critical"):
                proxmox_snapshot["outcome"] = ssh_vms["outcome"]

        gpu_probe = _fetch_gpu_snapshot()

    outcome = _outcome_from_snapshots(
        waiting=waiting,
        storage_probe=storage_probe,
        proxmox_snapshot=proxmox_snapshot,
        gpu_probe=gpu_probe,
        infra_jobs=infra_jobs,
        vm_dashboard=vm_dashboard,
    )

    summary_fr = _format_summary_fr(
        waiting=waiting,
        active=active,
        recent=recent,
        storage_probe=storage_probe,
        proxmox_snapshot=proxmox_snapshot,
        gpu_probe=gpu_probe,
        vm_dashboard=vm_dashboard,
    )

    pending_job_id = waiting[0]["id"] if waiting else None

    return {
        "ok": True,
        "outcome": outcome,
        "summary_fr": summary_fr,
        "pending_job_id": pending_job_id,
        "waiting_approval": waiting,
        "active_jobs": active,
        "recent_jobs": recent,
        "storage_probe": storage_probe,
        "proxmox_snapshot": proxmox_snapshot,
        "proxmox_ssh_vms": ssh_vms if include_probe else None,
        "gpu_probe": gpu_probe,
        "vm_dashboard": vm_dashboard,
        "ts": time.time(),
    }
