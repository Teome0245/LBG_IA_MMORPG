"""Sonde pool LVM thin Proxmox (local-lvm) — prévention io-error VM Prime."""

from __future__ import annotations

import os
import re
import subprocess
from typing import Any

from lbg_agents.proxmox_client import proxmox_hosts


def proxmox_ssh_host() -> str:
    """Hôte unique (rétrocompat) — premier de la liste multi-PVE."""
    hosts = proxmox_ssh_hosts()
    return hosts[0] if hosts else "192.168.0.201"


def proxmox_ssh_hosts() -> list[str]:
    """Hyperviseurs à sonder (SSH). Réutilise LBG_PROXMOX_HOSTS / LBG_PROXMOX_SSH_HOSTS."""
    return proxmox_hosts()


def proxmox_ssh_user() -> str:
    return os.environ.get("LBG_PROXMOX_SSH_USER", "root").strip() or "root"


def thin_pool_lv() -> str:
    return os.environ.get("LBG_PROXMOX_THIN_POOL", "pve/data").strip() or "pve/data"


def prime_vmid() -> int:
    try:
        return int(os.environ.get("LBG_PROXMOX_PRIME_VMID", "246"))
    except ValueError:
        return 246


def thin_warn_pct() -> int:
    try:
        return max(1, min(99, int(os.environ.get("LBG_PROXMOX_THIN_WARN_PCT", "85"))))
    except ValueError:
        return 85


def thin_crit_pct() -> int:
    try:
        return max(thin_warn_pct() + 1, min(100, int(os.environ.get("LBG_PROXMOX_THIN_CRIT_PCT", "95"))))
    except ValueError:
        return 95


_OUTCOME_RANK = {"ok": 0, "warn": 1, "critical": 2}


def _parse_kv_block(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in raw.splitlines():
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        out[key.strip()] = val.strip()
    return out


def proxmox_ssh_identity() -> str:
    return (
        os.environ.get("LBG_PROXMOX_SSH_IDENTITY")
        or os.environ.get("LBG_SSH_IDENTITY")
        or ""
    ).strip()


def _ssh_proxmox_host(host: str, script: str, *, timeout_s: float = 12.0) -> tuple[bool, str, str]:
    user = proxmox_ssh_user()
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        f"ConnectTimeout={int(timeout_s)}",
    ]
    identity = proxmox_ssh_identity()
    if identity:
        cmd.extend(["-i", identity])
    cmd.extend([f"{user}@{host}", "bash", "-s"])
    try:
        proc = subprocess.run(
            cmd,
            input=script,
            capture_output=True,
            text=True,
            timeout=timeout_s + 5,
        )
        return proc.returncode == 0, proc.stdout or "", proc.stderr or ""
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, "", str(exc)


def _outcome_from_metrics(
    data_pct: float,
    vm_status: str,
    *,
    warn: int,
    crit: int,
) -> str:
    if data_pct >= crit or "io-error" in vm_status:
        return "critical"
    if data_pct >= warn:
        return "warn"
    return "ok"


def probe_proxmox_storage_host(host: str) -> dict[str, Any]:
    """Sonde un hyperviseur Proxmox via SSH (read-only)."""
    pool = thin_pool_lv()
    vmid = prime_vmid()
    script = f"""
set -euo pipefail
POOL="{pool}"
VMID={vmid}
data_pct=$(lvs -o data_percent --noheadings "$POOL" 2>/dev/null | tr -d ' ' | head -1)
vg_free=$(vgs -o vg_free --noheadings pve 2>/dev/null | tr -d ' ')
pvesm=$(pvesm status 2>/dev/null | awk '/local-lvm/ {{gsub(/%/,"",$NF); print $NF}}' | head -1)
qm_prime=$(qm status "$VMID" 2>/dev/null | awk '{{print $2}}' || echo unknown)
echo "data_pct=${{data_pct:-na}}"
echo "vg_free=${{vg_free:-na}}"
echo "pvesm_local_lvm=${{pvesm:-na}}"
echo "vm_prime_status=${{qm_prime}}"
"""
    ok, stdout, stderr = _ssh_proxmox_host(host, script)
    warn = thin_warn_pct()
    crit = thin_crit_pct()
    if not ok:
        return {
            "ok": False,
            "outcome": "critical",
            "error": stderr.strip() or "ssh_proxmox_failed",
            "host": host,
            "pool": pool,
            "prime_vmid": vmid,
        }

    kv = _parse_kv_block(stdout)
    data_raw = kv.get("data_pct", "0")
    m = re.match(r"^(\d+(?:\.\d+)?)", data_raw)
    data_pct = float(m.group(1)) if m else 0.0
    vm_status = str(kv.get("vm_prime_status", ""))
    outcome = _outcome_from_metrics(data_pct, vm_status, warn=warn, crit=crit)

    return {
        "ok": True,
        "outcome": outcome,
        "host": host,
        "pool": pool,
        "prime_vmid": vmid,
        "data_percent": data_pct,
        "data_percent_raw": data_raw,
        "vg_free": kv.get("vg_free"),
        "pvesm_local_lvm_pct": kv.get("pvesm_local_lvm"),
        "vm246_status": vm_status,
        "vm_prime_status": vm_status,
        "thresholds": {"warn": warn, "critical": crit},
    }


def _aggregate_host_probes(hosts: list[dict[str, Any]]) -> dict[str, Any]:
    """Fusionne les sondes multi-PVE — le pire état l'emporte."""
    if not hosts:
        return {
            "ok": False,
            "outcome": "critical",
            "error": "no_proxmox_hosts_configured",
            "hosts": [],
        }

    ok_hosts = [h for h in hosts if h.get("ok")]
    if not ok_hosts:
        first = hosts[0]
        return {
            "ok": False,
            "outcome": "critical",
            "error": first.get("error") or "all_proxmox_probes_failed",
            "host": first.get("host"),
            "hosts": hosts,
            "pool": first.get("pool"),
        }

    worst = max(ok_hosts, key=lambda h: _OUTCOME_RANK.get(str(h.get("outcome")), 0))
    warn = thin_warn_pct()
    crit = thin_crit_pct()
    outcome = str(worst.get("outcome") or "ok")
    any_io_error = any(
        "io-error" in str(h.get("vm_prime_status") or h.get("vm246_status") or "")
        for h in ok_hosts
    )
    if any_io_error:
        outcome = "critical"

    return {
        "ok": True,
        "outcome": outcome,
        "host": worst.get("host"),
        "pool": worst.get("pool"),
        "data_percent": worst.get("data_percent"),
        "data_percent_raw": worst.get("data_percent_raw"),
        "vg_free": worst.get("vg_free"),
        "pvesm_local_lvm_pct": worst.get("pvesm_local_lvm_pct"),
        "vm246_status": worst.get("vm246_status"),
        "vm_prime_status": worst.get("vm_prime_status"),
        "prime_vmid": worst.get("prime_vmid"),
        "thresholds": {"warn": warn, "critical": crit},
        "hosts": hosts,
        "proxmox_hosts": [h.get("host") for h in hosts],
    }


def probe_proxmox_storage_local() -> dict[str, Any]:
    """Interroge tous les hyperviseurs Proxmox configurés via SSH."""
    host_list = proxmox_ssh_hosts()
    probes = [probe_proxmox_storage_host(host) for host in host_list]
    return _aggregate_host_probes(probes)


def format_storage_probe_reply(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        host = payload.get("host") or proxmox_ssh_host()
        return f"Stockage Proxmox ({host}) : sonde KO — {payload.get('error', '?')}"

    host_rows = payload.get("hosts")
    if isinstance(host_rows, list) and len(host_rows) > 1:
        lines = [
            f"Sonde stockage Proxmox — {len(host_rows)} hyperviseur(s)",
            f"Résultat global : {payload.get('outcome')} (pire pool : {payload.get('host')})",
            f"Seuils : warn ≥ {payload.get('thresholds', {}).get('warn')}% | critical ≥ {payload.get('thresholds', {}).get('critical')}%",
            "",
        ]
        for row in host_rows:
            if not isinstance(row, dict):
                continue
            if not row.get("ok"):
                lines.append(f"  • {row.get('host')} : ERREUR — {row.get('error', '?')}")
                continue
            vmid = row.get("prime_vmid", prime_vmid())
            lines.append(
                f"  • {row.get('host')} : pool {row.get('data_percent_raw')}% | "
                f"VG libre {row.get('vg_free')} | VM {vmid} {row.get('vm_prime_status')}"
            )
        if payload.get("outcome") != "ok":
            lines.append("→ Risque io-error si le pool thin reste saturé (voir runbook_proxmox_storage_prime.md)")
        return "\n".join(lines)

    vmid = payload.get("prime_vmid", prime_vmid())
    vm_status = payload.get("vm_prime_status") or payload.get("vm246_status")
    lines = [
        f"Pool {payload.get('pool')} @ {payload.get('host')} : {payload.get('data_percent_raw')}% utilisé",
        f"VG libre : {payload.get('vg_free')}",
        f"VM {vmid} Prime : {vm_status}",
        f"Seuils : warn ≥ {payload.get('thresholds', {}).get('warn')}% | critical ≥ {payload.get('thresholds', {}).get('critical')}%",
        f"Résultat : {payload.get('outcome')}",
    ]
    if payload.get("outcome") != "ok":
        lines.append("→ Risque io-error si le pool thin reste saturé (voir runbook_proxmox_storage_prime.md)")
    return "\n".join(lines)


def run_proxmox_storage_probe(*, actor_id: str = "proxmox_storage_probe", text: str = "") -> dict[str, Any]:
    payload = probe_proxmox_storage_local()
    return {
        "ok": bool(payload.get("ok")),
        "agent": "proxmox_storage_probe",
        "actor_id": actor_id,
        "request_text": text,
        "outcome": payload.get("outcome", "critical" if not payload.get("ok") else "ok"),
        "storage": payload,
        "reply": format_storage_probe_reply(payload),
    }


def main() -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Sonde pool thin Proxmox local-lvm (multi-PVE)")
    parser.add_argument("--json", action="store_true", help="Sortie JSON")
    args = parser.parse_args()

    payload = probe_proxmox_storage_local()
    outcome = str(payload.get("outcome") or ("critical" if not payload.get("ok") else "ok"))

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_storage_probe_reply(payload))

    if not payload.get("ok"):
        return 3
    if outcome == "critical":
        return 2
    if outcome == "warn":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
