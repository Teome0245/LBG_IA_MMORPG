"""Sonde Proxmox pour capability devops_probe (kind proxmox_status)."""

from __future__ import annotations

from typing import Any

from lbg_agents.proxmox_client import get_cluster_status, list_vms, match_lan_vms, probe_all_proxmox_hosts, proxmox_configured


def run_proxmox_status(
    *,
    actor_id: str,
    text: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ = actor_id, text, context
    if not proxmox_configured():
        return {
            "ok": True,
            "outcome": "skipped_not_configured",
            "agent": "proxmox_probe",
            "reply": (
                "Proxmox non configuré : définir LBG_PROXMOX_HOST et LBG_PROXMOX_TOKEN "
                "(token API read-only) dans lbg.env."
            ),
        }

    cluster = get_cluster_status()
    probes = probe_all_proxmox_hosts()
    lan = match_lan_vms()
    vms = list_vms(running_only=False)

    alerts: list[str] = []
    for probe in probes:
        if not probe.get("ok"):
            alerts.append(f"proxmox {probe.get('host')}: {probe.get('error', 'probe failed')}")
            continue
        perms = probe.get("permissions") if isinstance(probe.get("permissions"), dict) else {}
        if not perms.get("node_time"):
            alerts.append(
                f"proxmox {probe.get('host')}: heure API non lisible (token sans Sys.Audit sur /nodes/*/time)"
            )
    for label, row in (lan.get("matched") or {}).items():
        if not isinstance(row, dict):
            continue
        st = row.get("status") if isinstance(row.get("status"), dict) else {}
        inner = st.get("status") if isinstance(st.get("status"), dict) else st
        if not inner:
            continue
        mem_pct = inner.get("mem_pct")
        if isinstance(mem_pct, (int, float)) and mem_pct >= 90:
            alerts.append(f"{label}: RAM Proxmox {mem_pct}% (vmid {row.get('vmid')})")
        state = str(inner.get("status") or inner.get("qmpstatus") or "")
        if state and state not in {"running", "OK"}:
            alerts.append(f"{label}: état VM {state}")

    status_level = "ok"
    if alerts:
        status_level = "warn"

    lines = [
        f"Proxmox {cluster.get('host')}: version {cluster.get('version')} ({cluster.get('vm_count')} VMs).",
    ]
    for probe in probes:
        if not isinstance(probe, dict) or not probe.get("ok"):
            continue
        host = probe.get("host")
        nodes = ", ".join(probe.get("nodes") or []) or "?"
        lines.append(f"  [{host}] PVE {probe.get('version')} nodes={nodes}")
        time_blocks = probe.get("time") if isinstance(probe.get("time"), dict) else {}
        for node, tb in time_blocks.items():
            if isinstance(tb, dict) and tb.get("ok") and isinstance(tb.get("data"), dict):
                lines.append(f"    time {node}: {tb['data']}")
    for label, row in sorted((lan.get("matched") or {}).items()):
        if not isinstance(row, dict):
            continue
        vid = row.get("vmid")
        st_wrap = row.get("status") if isinstance(row.get("status"), dict) else {}
        inner = st_wrap.get("status") if isinstance(st_wrap.get("status"), dict) else st_wrap
        mem_pct = inner.get("mem_pct") if isinstance(inner, dict) else None
        cpu_pct = inner.get("cpu_pct") if isinstance(inner, dict) else None
        state = inner.get("status") if isinstance(inner, dict) else "?"
        lines.append(f"  {label}: vmid={vid} status={state} mem={mem_pct}% cpu={cpu_pct}%")

    if alerts:
        lines.append("Alertes: " + "; ".join(alerts))

    return {
        "ok": True,
        "outcome": status_level,
        "agent": "proxmox_probe",
        "cluster": cluster,
        "probes": probes,
        "lan_vms": lan,
        "vms": vms,
        "alerts": alerts,
        "reply": "\n".join(lines),
    }
