"""Client read-only API Proxmox VE (cluster / VMs)."""

from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import quote

import httpx

_DEFAULT_HOST = "192.168.0.201"
_DEFAULT_PORT = 8006


def _truthy(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def proxmox_configured() -> bool:
    return bool(proxmox_token().strip())


def proxmox_host() -> str:
    hosts = proxmox_hosts()
    return hosts[0] if hosts else _DEFAULT_HOST


def proxmox_hosts() -> list[str]:
    """Liste des hyperviseurs Proxmox (multi-PVE)."""
    raw = (
        os.environ.get("LBG_PROXMOX_HOSTS")
        or os.environ.get("LBG_PROXMOX_SSH_HOSTS")
        or ""
    ).strip()
    if raw:
        out: list[str] = []
        for part in raw.split(","):
            h = part.strip()
            if not h:
                continue
            h = h.removeprefix("https://").removeprefix("http://")
            h = h.split(":", 1)[0]
            if h and h not in out:
                out.append(h)
        if out:
            return out
    single = (
        os.environ.get("LBG_PROXMOX_HOST")
        or os.environ.get("PROXMOX_HOST")
    )
    if single:
        single = single.strip().removeprefix("https://").removeprefix("http://").split(":", 1)[0]
        return [single] if single else [_DEFAULT_HOST]
    return [_DEFAULT_HOST]


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


def _base_url_for(host: str | None = None) -> str:
    h = (host or proxmox_host()).strip()
    if h.startswith("http://") or h.startswith("https://"):
        return h.rstrip("/")
    return f"https://{h}:{proxmox_port()}"


def _base_url() -> str:
    return _base_url_for(proxmox_host())


def _headers() -> dict[str, str]:
    token = proxmox_token()
    if not token:
        raise ValueError("PROXMOX_TOKEN / LBG_PROXMOX_TOKEN non défini")
    return {"Authorization": f"PVEAPIToken={token}"}


def _request(
    method: str,
    path: str,
    *,
    host: str | None = None,
    timeout_s: float = 20.0,
) -> dict[str, Any]:
    path = path if path.startswith("/") else f"/{path}"
    url = f"{_base_url_for(host)}{path}"
    with httpx.Client(verify=proxmox_verify_ssl(), timeout=timeout_s) as client:
        resp = client.request(method, url, headers=_headers())
    try:
        payload = resp.json() if resp.content else {}
    except ValueError:
        payload = {}
    if resp.status_code >= 400:
        err = payload.get("errors") if isinstance(payload, dict) else None
        msg = payload.get("message") if isinstance(payload, dict) else None
        detail = err or msg or resp.text[:300]
        raise RuntimeError(f"Proxmox HTTP {resp.status_code}: {detail}")
    if isinstance(payload, dict) and "data" in payload:
        return {"ok": True, "data": payload["data"]}
    return {"ok": True, "data": payload}


def _safe_request(method: str, path: str, *, host: str | None = None) -> dict[str, Any]:
    try:
        return _request(method, path, host=host)
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


def probe_proxmox_host(host: str) -> dict[str, Any]:
    """Sonde read-only d'un hyperviseur (version, nœuds, heure si autorisé)."""
    if not proxmox_configured():
        return {"ok": False, "host": host, "error": "proxmox_not_configured"}
    version = _safe_request("GET", "/api2/json/version", host=host)
    nodes = _safe_request("GET", "/api2/json/nodes", host=host)
    resources = _safe_request("GET", "/api2/json/cluster/resources?type=vm", host=host)
    node_names: list[str] = []
    if nodes.get("ok"):
        for row in nodes.get("data") or []:
            if isinstance(row, dict) and row.get("node"):
                node_names.append(str(row["node"]))
    time_blocks: dict[str, Any] = {}
    for node in node_names[:4]:
        time_blocks[node] = _safe_request("GET", f"/api2/json/nodes/{quote(node)}/time", host=host)
    vdata = version.get("data") if isinstance(version.get("data"), dict) else {}
    rlist = resources.get("data") if isinstance(resources.get("data"), list) else []
    return {
        "ok": True,
        "host": host,
        "version": vdata.get("version"),
        "release": vdata.get("release"),
        "nodes": node_names,
        "vm_count": len(rlist) if isinstance(rlist, list) else None,
        "time": time_blocks,
        "permissions": {
            "version": version.get("ok", False),
            "nodes": nodes.get("ok", False),
            "cluster_vms": resources.get("ok", False),
            "node_time": any(
                isinstance(v, dict) and v.get("ok") for v in time_blocks.values()
            ),
        },
    }


def probe_all_proxmox_hosts() -> list[dict[str, Any]]:
    return [probe_proxmox_host(host) for host in proxmox_hosts()]


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


def get_nodes_status() -> dict[str, Any]:
    """RAM / CPU / charge des nœuds Proxmox (lecture seule)."""
    if not proxmox_configured():
        return {"ok": False, "error": "proxmox_not_configured"}
    nodes_resp = _safe_request("GET", "/api2/json/nodes")
    if not nodes_resp.get("ok"):
        return {"ok": False, "error": nodes_resp.get("error", "nodes_unavailable")}
    rows: list[dict[str, Any]] = []
    for node_row in nodes_resp.get("data") or []:
        if not isinstance(node_row, dict):
            continue
        node = str(node_row.get("node") or "")
        if not node:
            continue
        st = _safe_request("GET", f"/api2/json/nodes/{quote(node)}/status")
        data = st.get("data") if isinstance(st.get("data"), dict) else {}
        mem_block = data.get("memory")
        if isinstance(mem_block, dict):
            mem_pct = _pct(mem_block.get("used"), mem_block.get("total"))
        else:
            mem_pct = _pct(data.get("mem"), data.get("maxmem"))
        cpu_pct = None
        try:
            cpu_pct = round(float(data.get("cpu", 0)) * 100.0, 2)
        except (TypeError, ValueError):
            pass
        rows.append(
            {
                "node": node,
                "status": data.get("status") or node_row.get("status"),
                "mem_pct": mem_pct,
                "cpu_pct": cpu_pct,
                "loadavg": data.get("loadavg"),
                "uptime": data.get("uptime") or node_row.get("uptime"),
            }
        )
    return {"ok": True, "host": proxmox_host(), "nodes": rows}


def _lan_vm_defaults() -> dict[str, int]:
    """VMID LAN fixes (surcharge via LBG_PROXMOX_VM_LABELS)."""
    return {"core": 140, "front": 110, "precu": 245, "prime": 246}


def match_lan_vms() -> dict[str, Any]:
    """Associe les VM Proxmox aux rôles LAN connus (vmid explicite ou nom)."""
    raw = os.environ.get("LBG_PROXMOX_VM_LABELS", "").strip()
    labels: dict[str, int] = dict(_lan_vm_defaults())
    if raw:
        for part in raw.split(","):
            if "=" not in part:
                continue
            label, vid = part.split("=", 1)
            try:
                labels[label.strip()] = int(vid.strip())
            except ValueError:
                continue
    hints = {
        "core": re.compile(r"core|140|orchestr|mmorpg", re.I),
        "front": re.compile(r"front|110|ollama|pilot|lbg-ia\b", re.I),
        "precu": re.compile(r"precu|245|swgemu|serveurswg", re.I),
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
