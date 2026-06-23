"""Sonde pool LVM thin Proxmox (local-lvm) — prévention io-error VM Prime."""

from __future__ import annotations

import os
import re
import subprocess
from typing import Any


def proxmox_ssh_host() -> str:
    return os.environ.get("LBG_PROXMOX_SSH_HOST", "192.168.0.200").strip() or "192.168.0.200"


def proxmox_ssh_user() -> str:
    return os.environ.get("LBG_PROXMOX_SSH_USER", "root").strip() or "root"


def thin_pool_lv() -> str:
    return os.environ.get("LBG_PROXMOX_THIN_POOL", "pve/data").strip() or "pve/data"


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


def _ssh_proxmox(script: str, *, timeout_s: float = 12.0) -> tuple[bool, str, str]:
    host = proxmox_ssh_host()
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


def probe_proxmox_storage_local() -> dict[str, Any]:
    """Interroge Proxmox via SSH (read-only)."""
    pool = thin_pool_lv()
    script = f"""
set -euo pipefail
POOL="{pool}"
data_pct=$(lvs -o data_percent --noheadings "$POOL" 2>/dev/null | tr -d ' ' | head -1)
vg_free=$(vgs -o vg_free --noheadings pve 2>/dev/null | tr -d ' ')
pvesm=$(pvesm status 2>/dev/null | awk '/local-lvm/ {{gsub(/%/,"",$NF); print $NF}}' | head -1)
qm246=$(qm status 246 2>/dev/null | awk '{{print $2}}' || echo unknown)
echo "data_pct=${{data_pct:-na}}"
echo "vg_free=${{vg_free:-na}}"
echo "pvesm_local_lvm=${{pvesm:-na}}"
echo "vm246_status=${{qm246}}"
"""
    ok, stdout, stderr = _ssh_proxmox(script)
    if not ok:
        return {
            "ok": False,
            "outcome": "critical",
            "error": stderr.strip() or "ssh_proxmox_failed",
            "host": proxmox_ssh_host(),
            "pool": pool,
        }

    kv = _parse_kv_block(stdout)
    data_raw = kv.get("data_pct", "0")
    m = re.match(r"^(\d+(?:\.\d+)?)", data_raw)
    data_pct = float(m.group(1)) if m else 0.0

    warn = thin_warn_pct()
    crit = thin_crit_pct()
    if data_pct >= crit or "io-error" in str(kv.get("vm246_status", "")):
        outcome = "critical"
    elif data_pct >= warn:
        outcome = "warn"
    else:
        outcome = "ok"

    return {
        "ok": True,
        "outcome": outcome,
        "host": proxmox_ssh_host(),
        "pool": pool,
        "data_percent": data_pct,
        "data_percent_raw": data_raw,
        "vg_free": kv.get("vg_free"),
        "pvesm_local_lvm_pct": kv.get("pvesm_local_lvm"),
        "vm246_status": kv.get("vm246_status"),
        "thresholds": {"warn": warn, "critical": crit},
    }


def format_storage_probe_reply(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return f"Stockage Proxmox : sonde KO — {payload.get('error', '?')}"
    lines = [
        f"Pool {payload.get('pool')} @ {payload.get('host')} : {payload.get('data_percent_raw')}% utilisé",
        f"VG libre : {payload.get('vg_free')}",
        f"VM 246 Prime : {payload.get('vm246_status')}",
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
    import sys

    parser = argparse.ArgumentParser(description="Sonde pool thin Proxmox local-lvm")
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
