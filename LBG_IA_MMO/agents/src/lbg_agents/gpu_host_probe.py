"""Sonde GPU NVIDIA sur une VM (passthrough Proxmox) — lecture seule via SSH ou local."""

from __future__ import annotations

import os
import re
import subprocess
from typing import Any

_NVRM_FAIL_RE = re.compile(r"NVRM:.*(failed|RmInitAdapter failed)", re.I)


def _front_host() -> str:
    raw = (
        os.environ.get("LBG_GPU_PROBE_HOST")
        or os.environ.get("LBG_LAN_HOST_FRONT")
        or "192.168.0.110"
    ).strip()
    return raw.split(":", 1)[0]


def _ssh_user() -> str:
    return (os.environ.get("LBG_GPU_PROBE_USER") or os.environ.get("LBG_SSH_USER") or "lbg").strip() or "lbg"


def _ssh_identity() -> str:
    return (
        os.environ.get("LBG_GPU_PROBE_IDENTITY")
        or os.environ.get("LBG_SSH_IDENTITY")
        or ""
    ).strip()


def _parse_probe_output(stdout: str) -> dict[str, Any]:
    raw = stdout or ""
    pci_part, smi_part, dmesg_part = raw, "", ""
    if "---SMI---" in raw:
        pci_part, rest = raw.split("---SMI---", 1)
        if "---DMESG---" in rest:
            smi_part, dmesg_part = rest.split("---DMESG---", 1)
        else:
            smi_part = rest
    lines_pci = [ln.strip() for ln in pci_part.splitlines() if ln.strip()]
    lines_smi = [ln.strip() for ln in smi_part.splitlines() if ln.strip()]
    lines_dmesg = [ln.strip() for ln in dmesg_part.splitlines() if ln.strip()]

    pci_lines = [ln for ln in lines_pci if "nvidia" in ln.lower() or "10de:" in ln.lower()]
    smi_lines = lines_smi
    nvrm_errors = [ln for ln in lines_dmesg if _NVRM_FAIL_RE.search(ln)]

    smi_ok = any(re.search(r"gpu\s+\d+:", ln, re.I) or "m2090" in ln.lower() for ln in smi_lines)
    smi_ok = smi_ok and not any("no devices" in ln.lower() for ln in smi_lines)

    outcome = "ok"
    if pci_lines and not smi_ok:
        outcome = "warn" if nvrm_errors else "critical"
    elif not pci_lines:
        outcome = "skipped_no_pci"

    summary_parts: list[str] = []
    if pci_lines:
        summary_parts.append("PCI: " + pci_lines[0][:120])
    else:
        summary_parts.append("Aucune carte NVIDIA visible (PCI).")
    if smi_ok:
        summary_parts.append("nvidia-smi: GPU utilisable.")
    elif any("no devices" in ln.lower() for ln in smi_lines):
        summary_parts.append("nvidia-smi: aucun GPU (driver chargé mais carte inactive).")
    if nvrm_errors:
        summary_parts.append("Erreur driver: " + nvrm_errors[-1][:100])

    return {
        "ok": True,
        "host": _front_host(),
        "outcome": outcome,
        "pci": pci_lines[:4],
        "nvidia_smi": smi_lines[:6],
        "nvrm_errors": nvrm_errors[-5:],
        "driver_usable": smi_ok,
        "summary_fr": " ".join(summary_parts),
    }


_PROBE_SCRIPT = r"""
set -euo pipefail
lspci -nn 2>/dev/null | grep -iE 'nvidia|vga.*10de' || true
echo '---SMI---'
nvidia-smi -L 2>&1 || true
echo '---DMESG---'
dmesg 2>/dev/null | grep -iE 'NVRM|nvidia' | tail -8 || sudo dmesg 2>/dev/null | grep -iE 'NVRM|nvidia' | tail -8 || true
"""


def probe_gpu_local() -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["bash", "-c", _PROBE_SCRIPT],
            capture_output=True,
            text=True,
            timeout=15,
        )
        out = _parse_probe_output((proc.stdout or "") + "\n" + (proc.stderr or ""))
        out["mode"] = "local"
        return out
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc), "host": _front_host(), "mode": "local"}


def probe_gpu_ssh(host: str | None = None) -> dict[str, Any]:
    h = (host or _front_host()).strip()
    user = _ssh_user()
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ConnectTimeout=8",
    ]
    ident = _ssh_identity()
    if ident:
        cmd.extend(["-i", ident])
    cmd.extend([f"{user}@{h}", "bash", "-s"])
    try:
        proc = subprocess.run(
            cmd,
            input=_PROBE_SCRIPT,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if proc.returncode != 0 and not (proc.stdout or proc.stderr):
            return {
                "ok": False,
                "host": h,
                "error": proc.stderr.strip() or f"ssh exit {proc.returncode}",
                "mode": "ssh",
            }
        out = _parse_probe_output((proc.stdout or "") + "\n" + (proc.stderr or ""))
        out["host"] = h
        out["mode"] = "ssh"
        return out
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "host": h, "error": str(exc), "mode": "ssh"}


def probe_front_gpu() -> dict[str, Any]:
    """Sonde la VM front (110 par défaut) — SSH depuis l'orchestrateur, local si déjà sur 110."""
    try:
        import socket

        local_ips = {socket.gethostbyname(socket.gethostname())}
        for info in socket.getaddrinfo(None, 0, socket.AF_INET):
            local_ips.add(info[4][0])
    except OSError:
        local_ips = set()
    front = _front_host()
    if front in local_ips or front in {"127.0.0.1", "localhost"}:
        return probe_gpu_local()
    return probe_gpu_ssh(front)
