"""Client read-only API Proxmox VE (cluster / VMs)."""

from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import quote

import httpx

_DEFAULT_HOST = "192.168.0.200"
_DEFAULT_PORT = 8006


def _truthy(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def proxmox_configured() -> bool:
    return bool(proxmox_token().strip())


def proxmox_host() -> str:
    return (
        os.environ.get("LBG_PROXMOX_HOST")
        or os.environ.get("PROXMOX_HOST")
        or _DEFAULT_HOST
    ).strip() or _DEFAULT_HOST


def proxmox_port() -> int:
    raw = os.environ.get("LBG_PROXMOX_PORT") or os.environ.get("PROXMOX_PORT") or str(_DEFAULT_PORT)
    try:
        return int(raw)
    except ValueError:
        return _DEFAULT_PORT


def proxmox_token() -> str:
    return (os.environ.get("LBG_PROXMOX_TOKEN") or os.environ.get("PROXMOX_TOKEN") or "").strip()


def proxmox_verify_ssl() -> bool:
    return _truthy(os.environ.get("LBG_PROXMOX_VERIFY_SSL", os.environ.get("PROXMOX_VERIFY_SSL", "0")))


def _base_url() -> str:
    host = proxmox_host()
    if host.startswith("http://") or host.startswith("https://"):
        return host.rstrip("/")
    return f"https://{host}:{proxmox_port()}"


def _headers() -> dict[str, str]:
    token = proxmox_token()
    if not token:
        raise ValueError("PROXMOX_TOKEN / LBG_PROXMOX_TOKEN non défini")
    return {"Authorization": f"PVEAPIToken={token}"}


def _request(method: str, path: str, *, timeout_s: float = 20.0) -> dict[str, Any]:
    path = path if path.startswith("/") else f"/{path}"
    url = f"{_base_url()}{path}"
    with httpx.Client(verify=proxmox_verify_ssl(), timeout=timeout_s) as client:
        resp = client.request(method, url, headers=_headers())
    try:
        payload = resp.json() if resp.content else {}
    except ValueError:
        payload = {}
    if resp.status_code >= 400:
        err = payload.get("errors") if isinstance(payload, dict) else None
        raise RuntimeError(f"Proxmox HTTP {resp.status_code}: {err or resp.text[:300]}")
    if isinstance(payload, dict) and "data" in payload:
        return {"ok": True, "data": payload["data"]}
    return {"ok": True, "data": payload}


def get_cluster_status() -> dict[str, Any]:
    """Version + ressources cluster (lecture seule)."""
    if not proxmox_configured():
        return {"ok": False, "error": "proxmox_not_configured", "hint": "Définir LBG_PROXMOX_TOKEN dans lbg.env"}
    try:
        version = _request("GET", "/api2/json/version")
        resources = _request("GET", "/api2/json/cluster/resources?type=vm")
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        return {"ok": False, "error": str(exc), "host": proxmox_host()}
    vdata = version.get("data") if isinstance(version.get("data"), dict) else {}
    rlist = resources.get("data") if isinstance(resources.get("data"), list) else []
    return {
        "ok": True,
        "host": proxmox_host(),
        "version": vdata.get("version"),
        "release": vdata.get("release"),
        "vm_count": len(rlist),
        "vms": [_vm_summary(row) for row in rlist if isinstance(row, dict)],
    }


def _vm_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "vmid": row.get("vmid"),
        "name": row.get("name"),
        "node": row.get("node"),
        "status": row.get("status"),
        "cpu": row.get("cpu"),
        "maxcpu": row.get("maxcpu"),
        "mem": row.get("mem"),
        "maxmem": row.get("maxmem"),
        "disk": row.get("disk"),
        "maxdisk": row.get("maxdisk"),
        "uptime": row.get("uptime"),
    }


def list_vms(*, running_only: bool = False) -> dict[str, Any]:
    out = get_cluster_status()
    if not out.get("ok"):
        return out
    vms = out.get("vms") or []
    if running_only:
        vms = [v for v in vms if str(v.get("status")) == "running"]
    return {"ok": True, "host": out.get("host"), "count": len(vms), "vms": vms}


def _find_vm(vmid: int) -> dict[str, Any] | None:
    status = get_cluster_status()
    if not status.get("ok"):
        return None
    for row in status.get("vms") or []:
        if int(row.get("vmid") or 0) == vmid:
            return row
    return None


def get_vm_status(vmid: int) -> dict[str, Any]:
    """Métriques courantes d'une VM QEMU."""
    if not proxmox_configured():
        return {"ok": False, "error": "proxmox_not_configured", "vmid": vmid}
    vm = _find_vm(vmid)
    if vm is None:
        return {"ok": False, "error": "vm_not_found", "vmid": vmid}
    node = str(vm.get("node") or "")
    if not node:
        return {"ok": False, "error": "node_missing", "vmid": vmid, "summary": vm}
    try:
        current = _request("GET", f"/api2/json/nodes/{quote(node)}/qemu/{vmid}/status/current")
    except (httpx.HTTPError, RuntimeError) as exc:
        return {"ok": False, "error": str(exc), "vmid": vmid, "node": node}
    data = current.get("data") if isinstance(current.get("data"), dict) else {}
    merged = {**vm, **data}
    merged["mem_pct"] = _pct(merged.get("mem"), merged.get("maxmem"))
    merged["cpu_pct"] = _pct(merged.get("cpu"), merged.get("maxcpu"))
    return {"ok": True, "vmid": vmid, "node": node, "status": merged}


def _pct(used: Any, total: Any) -> float | None:
    try:
        u, t = float(used), float(total)
    except (TypeError, ValueError):
        return None
    if t <= 0:
        return None
    return round(100.0 * u / t, 2)


def get_vm_config(vmid: int) -> dict[str, Any]:
    """Configuration QEMU (lecture seule)."""
    if not proxmox_configured():
        return {"ok": False, "error": "proxmox_not_configured", "vmid": vmid}
    vm = _find_vm(vmid)
    if vm is None:
        return {"ok": False, "error": "vm_not_found", "vmid": vmid}
    node = str(vm.get("node") or "")
    if not node:
        return {"ok": False, "error": "node_missing", "vmid": vmid}
    try:
        cfg = _request("GET", f"/api2/json/nodes/{quote(node)}/qemu/{vmid}/config")
    except (httpx.HTTPError, RuntimeError) as exc:
        return {"ok": False, "error": str(exc), "vmid": vmid, "node": node}
    data = cfg.get("data") if isinstance(cfg.get("data"), dict) else {}
    return {"ok": True, "vmid": vmid, "node": node, "config": data}


def match_lan_vms() -> dict[str, Any]:
    """Associe les VM Proxmox aux rôles LAN connus (nom ou LBG_PROXMOX_VM_LABELS)."""
    raw = os.environ.get("LBG_PROXMOX_VM_LABELS", "").strip()
    labels: dict[str, int] = {}
    if raw:
        for part in raw.split(","):
            if "=" not in part:
                continue
            label, vid = part.split("=", 1)
            try:
                labels[label.strip()] = int(vid.strip())
            except ValueError:
                continue
    else:
        # vmid 0 → résolution par nom (regex) ; surcharger via LBG_PROXMOX_VM_LABELS=prime=104,...
        labels = {"core": 0, "front": 0, "precu": 0, "prime": 0}
    hints = {
        "core": re.compile(r"core|140|orchestr", re.I),
        "front": re.compile(r"front|110|ollama|pilot", re.I),
        "precu": re.compile(r"precu|245|swgemu", re.I),
        "prime": re.compile(r"prime|246|clean", re.I),
    }
    listed = list_vms()
    if not listed.get("ok"):
        return listed
    vms = listed.get("vms") or []
    matched: dict[str, Any] = {}
    for label, vmid in labels.items():
        if vmid > 0:
            st = get_vm_status(vmid)
            matched[label] = {"vmid": vmid, "by": "env", "status": st}
            continue
        pat = hints.get(label)
        if not pat:
            continue
        for vm in vms:
            name = str(vm.get("name") or "")
            if pat.search(name):
                vid = int(vm.get("vmid") or 0)
                matched[label] = {"vmid": vid, "name": name, "by": "name", "status": get_vm_status(vid)}
                break
    return {"ok": True, "host": proxmox_host(), "matched": matched, "vm_count": len(vms)}
