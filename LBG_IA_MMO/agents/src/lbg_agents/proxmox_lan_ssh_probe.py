"""Sonde VMs LAN via SSH sur l'hôte Proxmox (pvesh local — sans token API distant)."""

from __future__ import annotations

import json
import re
from typing import Any

from lbg_agents.proxmox_storage_probe import proxmox_ssh_hosts
from lbg_agents.proxmox_storage_probe import _ssh_proxmox_host

_LABEL_FR = {
    "core": "Core 140",
    "front": "Front 110",
    "precu": "Précu 245",
    "prime": "Prime 246",
}

_PROBE_SCRIPT = r"""
set -euo pipefail
NODE="${NODE:-lbgr720}"
labels="core:140 front:110 precu:245 prime:246"
for pair in $labels; do
  label="${pair%%:*}"
  vmid="${pair##*:}"
  json=$(pvesh get "/nodes/${NODE}/qemu/${vmid}/status/current" --output-format json 2>/dev/null || echo "{}")
  python3 - <<'PY' "$label" "$vmid" "$json"
import json, sys
label, vmid, raw = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    d = json.loads(raw) if raw.strip() else {}
except json.JSONDecodeError:
    d = {}
mem, mx = d.get("mem"), d.get("maxmem")
pct = round(100.0 * float(mem) / float(mx), 2) if mem and mx and float(mx) > 0 else ""
cpu = d.get("cpu")
cpu_pct = round(float(cpu) * 100.0, 2) if cpu is not None else ""
st = d.get("status") or d.get("qmpstatus") or "?"
print(f"vm|{label}|{vmid}|{st}|{pct}|{cpu_pct}")
PY
done
"""


def _parse_ssh_vm_lines(stdout: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("vm|"):
            continue
        parts = line.split("|")
        if len(parts) < 6:
            continue
        _, label, vmid, status, mem_pct, cpu_pct = parts[:6]
        mp = float(mem_pct) if mem_pct not in ("", "None") else None
        cp = float(cpu_pct) if cpu_pct not in ("", "None") else None
        rows.append(
            {
                "label": label,
                "label_fr": _LABEL_FR.get(label, label),
                "vmid": int(vmid) if vmid.isdigit() else vmid,
                "status": status,
                "mem_pct": mp,
                "cpu_pct": cp,
            }
        )
    return rows


def probe_lan_vms_ssh(host: str | None = None) -> dict[str, Any]:
    """Lit RAM/CPU des VM LAN via pvesh sur l'hyperviseur (SSH root)."""
    hosts = [host] if host else proxmox_ssh_hosts()
    if not hosts:
        return {"ok": False, "error": "no_proxmox_ssh_host"}
    last_err = ""
    for h in hosts:
        ok, stdout, stderr = _ssh_proxmox_host(h, _PROBE_SCRIPT, timeout_s=18.0)
        if not ok:
            last_err = stderr.strip() or "ssh_failed"
            continue
        rows = _parse_ssh_vm_lines(stdout)
        if not rows:
            last_err = "no_vm_rows"
            continue
        alerts: list[str] = []
        for v in rows:
            mp = v.get("mem_pct")
            name = v.get("label_fr") or v.get("label")
            if isinstance(mp, (int, float)) and mp >= 90:
                alerts.append(f"{name}: RAM {mp}% (vmid {v.get('vmid')})")
            elif isinstance(mp, (int, float)) and mp >= 80:
                alerts.append(f"{name}: RAM élevée {mp}% (vmid {v.get('vmid')})")
        outcome = "ok"
        if any(isinstance(v.get("mem_pct"), (int, float)) and v["mem_pct"] >= 92 for v in rows):
            outcome = "critical"
        elif alerts:
            outcome = "warn"
        return {
            "ok": True,
            "host": h,
            "mode": "ssh_pvesh",
            "vm_dashboard": rows,
            "alerts": alerts,
            "outcome": outcome,
        }
    return {"ok": False, "error": last_err or "ssh_probe_failed", "host": hosts[0]}


def merge_vm_dashboard(
    api_rows: list[dict[str, Any]] | None,
    ssh_snapshot: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Privilégie les lignes SSH si l'API Proxmox est incomplète."""
    ssh_rows = (
        ssh_snapshot.get("vm_dashboard")
        if isinstance(ssh_snapshot, dict) and ssh_snapshot.get("ok")
        else None
    )
    if ssh_rows:
        return list(ssh_rows)
    return list(api_rows or [])
