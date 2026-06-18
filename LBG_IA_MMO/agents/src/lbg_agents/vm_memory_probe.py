"""Sonde mémoire read-only sur les VM LAN (SSH depuis l'orchestrateur core)."""

from __future__ import annotations

import os
import re
import subprocess
import time
from typing import Any

from lbg_agents import ssh_client as _ssh
from lbg_agents.remote_targets import resolve_host

_PROBE_CMD = (
    "free -b | awk '/^Mem:/{print \"mem_total=\"$2\" mem_used=\"$3\" mem_avail=\"$7}' ; "
    "free -b | awk '/^Swap:/{print \"swap_total=\"$2\" swap_used=\"$3}' ; "
    "ps -eo comm,rss --sort=-rss 2>/dev/null | awk 'NR<=6{printf \"proc %s %s\\n\",$1,$2}'"
)

_DEFAULT_HOSTS: list[tuple[str, str]] = [
    ("prime", "246"),
    ("precu", "245"),
    ("front", "110"),
    ("core", "140"),
]


def _truthy(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def memory_probe_enabled() -> bool:
    if not _ssh.ssh_enabled():
        return False
    return _truthy(os.environ.get("LBG_VM_MEMORY_PROBE_ENABLED", "1"))


def _warn_pct() -> float:
    try:
        return max(5.0, float(os.environ.get("LBG_VM_MEMORY_WARN_PCT", "15")))
    except ValueError:
        return 15.0


def _crit_pct() -> float:
    try:
        return max(3.0, float(os.environ.get("LBG_VM_MEMORY_CRIT_PCT", "8")))
    except ValueError:
        return 8.0


def _lan_ip_from_suffix(sid: str) -> str:
    s = (sid or "").strip()
    if re.fullmatch(r"\d{1,3}", s):
        return f"192.168.0.{s}"
    return s


def _excluded_probe_labels() -> set[str]:
    out: set[str] = set()
    raw = os.environ.get("LBG_VM_MEMORY_PROBE_EXCLUDE", "").strip()
    if raw:
        out.update(p.strip().lower() for p in raw.split(",") if p.strip())
    if _truthy(os.environ.get("LBG_INFRA_WATCHDOG_EXCLUDE_PRIME", "0")):
        out.update({"prime", "mmo", "246", "core3"})
    return out


def _probe_hosts() -> list[tuple[str, str]]:
    raw = os.environ.get("LBG_VM_MEMORY_PROBE_HOSTS", "").strip()
    excluded = _excluded_probe_labels()
    if raw:
        out: list[tuple[str, str]] = []
        for part in raw.split(","):
            p = part.strip()
            if not p:
                continue
            if "=" in p:
                label, sid = p.split("=", 1)
                label = label.strip() or sid.strip()
                if label.lower() in excluded:
                    continue
                sid = sid.strip()
                host = resolve_host(sid) or _lan_ip_from_suffix(sid)
                out.append((label, host))
            else:
                if p.lower() in excluded:
                    continue
                host = resolve_host(p) or p
                out.append((p, host))
        return out
    resolved: list[tuple[str, str]] = []
    for label, sid in _DEFAULT_HOSTS:
        if label.lower() in excluded:
            continue
        host = resolve_host(sid)
        if host:
            resolved.append((label, host))
    return resolved


def _parse_probe_output(stdout: str) -> dict[str, Any]:
    mem_total = mem_used = mem_avail = swap_total = swap_used = 0
    procs: list[dict[str, Any]] = []
    for line in (stdout or "").splitlines():
        line = line.strip()
        if line.startswith("mem_total="):
            for kv in line.split():
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    if k == "mem_total":
                        mem_total = int(v or 0)
                    elif k == "mem_used":
                        mem_used = int(v or 0)
                    elif k == "mem_avail":
                        mem_avail = int(v or 0)
        elif line.startswith("swap_total="):
            for kv in line.split():
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    if k == "swap_total":
                        swap_total = int(v or 0)
                    elif k == "swap_used":
                        swap_used = int(v or 0)
        elif line.startswith("proc "):
            m = re.match(r"proc\s+(\S+)\s+(\d+)", line)
            if m:
                procs.append({"comm": m.group(1), "rss_kb": int(m.group(2))})
    avail_pct = (100.0 * mem_avail / mem_total) if mem_total else 0.0
    swap_pct = (100.0 * swap_used / swap_total) if swap_total else 0.0
    return {
        "mem_total_b": mem_total,
        "mem_used_b": mem_used,
        "mem_avail_b": mem_avail,
        "mem_avail_pct": round(avail_pct, 1),
        "swap_total_b": swap_total,
        "swap_used_b": swap_used,
        "swap_used_pct": round(swap_pct, 1),
        "top_processes": procs,
    }


def _status(metrics: dict[str, Any]) -> str:
    avail = float(metrics.get("mem_avail_pct") or 0)
    swap = float(metrics.get("swap_used_pct") or 0)
    if avail < _crit_pct() or swap >= 90.0:
        return "critical"
    if avail < _warn_pct() or swap >= 50.0:
        return "warn"
    return "ok"


def _format_host_line(label: str, host: str, entry: dict[str, Any]) -> str:
    m = entry.get("metrics") or {}
    if not entry.get("ok"):
        return f"• {label} ({host}) — KO : {entry.get('error', '?')}"
    avail_g = (int(m.get("mem_avail_b") or 0)) / (1024**3)
    total_g = (int(m.get("mem_total_b") or 0)) / (1024**3)
    top = m.get("top_processes") or []
    top_s = top[0]["comm"] if top else "?"
    rss_mib = (int(top[0].get("rss_kb") or 0)) / 1024 if top else 0
    st = entry.get("status", "ok")
    mark = {"ok": "OK", "warn": "ATTENTION", "critical": "CRITIQUE"}.get(st, st)
    extra = f" — swap {m.get('swap_used_pct', 0)}%" if float(m.get("swap_used_pct") or 0) > 10 else ""
    return (
        f"• {label} ({host}) [{mark}] : {avail_g:.1f}/{total_g:.1f} Go disponibles "
        f"({m.get('mem_avail_pct')}%) — top: {top_s} {rss_mib:.0f} MiB{extra}"
    )


def _run_probe(host: str) -> tuple[bool, str, str]:
    """Exécute la sonde en local (core) ou via SSH."""
    if not _ssh.should_use_ssh_for_host(host):
        try:
            proc = subprocess.run(
                ["bash", "-lc", _PROBE_CMD],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            return False, "", "local probe timeout (30s)"
        except OSError as exc:
            return False, "", f"{type(exc).__name__}: {exc}"
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or f"local exit {proc.returncode}").strip()
            return False, "", err[:500]
        return True, proc.stdout or "", ""
    res = _ssh.run_ssh(host, _PROBE_CMD, trusted=True)
    if not res.ok:
        return False, "", res.error or res.stderr
    return True, res.stdout, ""


def run_vm_memory_probe(
    *,
    actor_id: str,
    text: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ = actor_id, text, context
    if not memory_probe_enabled():
        return {
            "ok": False,
            "agent": "vm_memory_probe",
            "handler": "devops",
            "outcome": "forbidden",
            "error": "Sonde mémoire désactivée (LBG_VM_MEMORY_PROBE_ENABLED=0 ou LBG_MCP_SSH_ENABLED=0).",
        }

    hosts = _probe_hosts()
    entries: list[dict[str, Any]] = []
    worst = "ok"
    rank = {"ok": 0, "warn": 1, "critical": 2}

    for label, host in hosts:
        ok, stdout, err = _run_probe(host)
        if not ok:
            entry = {"label": label, "host": host, "ok": False, "error": err or "?"}
            entries.append(entry)
            worst = "critical"
            continue
        metrics = _parse_probe_output(stdout)
        st = _status(metrics)
        if rank.get(st, 0) > rank.get(worst, 0):
            worst = st
        entries.append(
            {
                "label": label,
                "host": host,
                "ok": True,
                "status": st,
                "metrics": metrics,
            }
        )

    lines = [_format_host_line(e["label"], e["host"], e) for e in entries]
    note = (
        "Note : sur Prime (246), core3-clean réserve souvent 6–8 Go (normal MMO). "
        "Les chutes brusques Proxmox coïncident souvent avec les redémarrages watchdog Prime."
    )
    return {
        "ok": True,
        "agent": "vm_memory_probe",
        "handler": "devops",
        "outcome": worst,
        "hosts": entries,
        "n_hosts": len(entries),
        "worst_status": worst,
        "reply": "\n".join(lines) + "\n\n" + note,
        "ts": time.time(),
    }
