"""Inventaire réseau LAN read-only — scan sous-réseau + hôtes connus + sondes HTTP."""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import urlparse

import httpx

from lbg_agents.remote_targets import canonical_role, resolve_host

# Phase 1 : détecter les hôtes vivants (rapide).
_DISCOVERY_PORTS = (22, 80, 443, 445)
# Phase 2 : fingerprint sur hôtes répondants.
_DETAIL_PORTS = (
    22, 80, 443, 445, 3389, 5000, 5001, 548, 8006, 902, 8080, 11434, 5005, 6000, 8010, 8050, 8773, 7733,
    44453, 44462, 44463,
)
_PORT_HINTS: dict[int, str] = {
    22: "ssh",
    80: "http",
    443: "https",
    445: "smb",
    3389: "rdp",
    5000: "synology/nas",
    5001: "synology/nas-https",
    548: "afp/nas",
    8006: "proxmox",
    902: "vmware-esxi",
    8080: "http-alt",
    11434: "ollama",
    5005: "agent-windows",
    6000: "agent-linux",
    8010: "orchestrator",
    8050: "mmo-http",
    8773: "mmmorpg-internal",
    7733: "mmmorpg-ws",
    44453: "core3-precu-login",
    44462: "core3-precu-status",
    44463: "core3-precu-ping",
}

# Capabilities suggérées par rôle / type d'appareil (croisement avec le registry orchestrateur).
_ROLE_SUGGESTIONS: dict[str, tuple[str, ...]] = {
    "core": ("devops_probe", "network_inventory", "project_pm"),
    "front": ("devops_probe", "npc_dialogue", "network_inventory"),
    "mmo": ("devops_probe", "core3_bot_action", "network_inventory"),
    "precu": ("devops_probe", "network_inventory"),
    "desktop": ("desktop_control", "devops_probe"),
    "ad": ("desktop_control", "devops_probe"),
    "mail": ("devops_probe",),
    "router": ("network_inventory",),
    "nas": ("devops_probe",),
    "hypervisor": ("devops_probe", "network_inventory"),
    "discovered": ("devops_probe", "network_inventory"),
}
_HINT_SUGGESTIONS: dict[str, tuple[str, ...]] = {
    "synology/nas": ("devops_probe",),
    "synology-nas": ("devops_probe",),
    "proxmox": ("devops_probe", "network_inventory"),
    "vmware-esxi": ("devops_probe", "network_inventory"),
    "windows": ("desktop_control", "devops_probe"),
    "windows-ad": ("desktop_control", "devops_probe"),
    "windows-server": ("devops_probe",),
    "freebox-routeur": ("network_inventory",),
}
_PORT_SUGGESTIONS: dict[int, tuple[str, ...]] = {
    5005: ("desktop_control",),
    6000: ("devops_probe",),
    8010: ("devops_probe", "project_pm"),
    8020: ("npc_dialogue",),
    8050: ("devops_probe", "core3_bot_action"),
    8055: ("project_pm",),
    8080: ("devops_probe",),
    11434: ("npc_dialogue",),
    7733: ("core3_bot_action",),
    8006: ("devops_probe",),
    902: ("devops_probe",),
    5000: ("devops_probe",),
    5001: ("devops_probe",),
}

_URL_ENV_LABELS: dict[str, tuple[str, str]] = {
    "LBG_AGENT_DESKTOP_URL": ("desktop", "pc-windows"),
    "AGENT_WINDOWS_URL": ("desktop", "pc-windows"),
    "AGENT_WINDOWS_SRV_AD_URL": ("ad", "serveur-ad"),
    "AGENT_LINUX_MAIL_URL": ("mail", "serveur-mail"),
    "AGENT_LINUX_IA_URL": ("ia-agent", "agent-linux-ia"),
    "AGENT_LINUX_MMMORPG_URL": ("mmo-agent", "agent-linux-mmo"),
    "AGENT_DEVOPS_VM_URL": ("devops-vm", "devops-vm"),
    "OLLAMA_BASE_URL": ("ollama", "ollama"),
    "LBG_ORCHESTRATOR_URL": ("orchestrator", "orchestrateur"),
    "LBG_MMO_SERVER_URL": ("mmo", "mmo-server"),
}


def _env_bool(key: str, default: bool = True) -> bool:
    raw = os.environ.get(key, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _scan_timeout_s() -> float:
    try:
        return max(0.15, float(os.environ.get("LBG_NETWORK_SCAN_TIMEOUT_S", "0.45").strip()))
    except ValueError:
        return 0.45


def _scan_workers() -> int:
    try:
        return max(8, min(128, int(os.environ.get("LBG_NETWORK_SCAN_WORKERS", "64").strip())))
    except ValueError:
        return 64


def _scan_cidr() -> str:
    return os.environ.get("LBG_NETWORK_SCAN_CIDR", "192.168.0.0/24").strip() or "192.168.0.0/24"


def _reverse_dns_enabled() -> bool:
    return _env_bool("LBG_NETWORK_REVERSE_DNS", default=True)


def _reverse_dns_timeout_s() -> float:
    try:
        return max(0.2, float(os.environ.get("LBG_NETWORK_REVERSE_DNS_TIMEOUT_S", "1.0").strip()))
    except ValueError:
        return 1.0


def _resolve_hostname(ip: str) -> str | None:
    if not _reverse_dns_enabled():
        return None
    try:
        socket.setdefaulttimeout(_reverse_dns_timeout_s())
        name, _, _ = socket.gethostbyaddr(ip)
        cleaned = (name or "").strip().rstrip(".")
        return cleaned or None
    except OSError:
        return None
    finally:
        socket.setdefaulttimeout(None)


def _resolve_hostnames(devices: list[dict[str, Any]]) -> None:
    if not _reverse_dns_enabled():
        return
    ips = [str(d.get("host") or "") for d in devices if d.get("host")]
    if not ips:
        return
    workers = min(_scan_workers(), max(4, len(ips)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_resolve_hostname, ip): ip for ip in ips}
        names: dict[str, str | None] = {}
        for fut in as_completed(futures):
            ip = futures[fut]
            try:
                names[ip] = fut.result()
            except Exception:
                names[ip] = None
    for d in devices:
        host = str(d.get("host") or "")
        if host and names.get(host):
            d["hostname"] = names[host]


def _suggest_capabilities(device: dict[str, Any]) -> list[str]:
    caps: set[str] = set()
    role = str(device.get("role") or "")
    for cap in _ROLE_SUGGESTIONS.get(role, ()):
        caps.add(cap)
    hint = str(device.get("device_hint") or "")
    for cap in _HINT_SUGGESTIONS.get(hint, ()):
        caps.add(cap)
    label = str(device.get("label") or "").lower()
    if "ad" in label or "windows" in label:
        caps.update(("desktop_control", "devops_probe"))
    if "synology" in label or "nas" in label:
        caps.add("devops_probe")
    for port in device.get("open_ports") or []:
        if isinstance(port, int):
            for cap in _PORT_SUGGESTIONS.get(port, ()):
                caps.add(cap)
    if device.get("reachable"):
        caps.add("network_inventory")
    order = (
        "network_inventory",
        "devops_probe",
        "desktop_control",
        "npc_dialogue",
        "project_pm",
        "core3_bot_action",
    )
    return [c for c in order if c in caps]


def _devices_export_payload(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for d in devices:
        rows.append(
            {
                "host": d.get("host"),
                "hostname": d.get("hostname"),
                "label": d.get("label"),
                "role": d.get("role"),
                "device_hint": d.get("device_hint"),
                "reachable": d.get("reachable"),
                "open_ports": d.get("open_ports") or [],
                "action_suggestions": d.get("action_suggestions") or [],
                "source": d.get("source"),
            }
        )
    return rows


def _tcp_reachable(host: str, port: int, timeout_s: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def _http_probe(url: str, timeout_s: float = 2.5) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
            r = client.get(url)
        return {"ok": r.status_code < 400, "status_code": r.status_code, "url": url}
    except Exception as e:
        return {"ok": False, "url": url, "error": f"{type(e).__name__}: {e}"}


def _http_fingerprint(host: str, port: int = 80, timeout_s: float = 2.0) -> dict[str, Any]:
    scheme = "https" if port == 443 else "http"
    url = f"{scheme}://{host}:{port}/"
    try:
        with httpx.Client(timeout=timeout_s, follow_redirects=True, verify=False) as client:
            r = client.get(url)
        body = (r.text or "")[:1200].lower()
        server = (r.headers.get("server") or "").strip()
        hint = _hint_from_http(body, server)
        return {
            "ok": True,
            "url": url,
            "status_code": r.status_code,
            "server": server,
            "device_hint": hint,
        }
    except Exception as e:
        return {"ok": False, "url": url, "error": f"{type(e).__name__}: {e}"}


def _hint_from_http(body: str, server: str) -> str | None:
    blob = f"{body} {server.lower()}"
    for needle, label in (
        ("synology", "synology-nas"),
        ("diskstation", "synology-nas"),
        ("proxmox", "proxmox"),
        ("vmware", "vmware-esxi"),
        ("esxi", "vmware-esxi"),
        ("freebox", "freebox-routeur"),
        ("livebox", "livebox-routeur"),
        ("sfr", "box-sfr"),
        ("active directory", "windows-ad"),
        ("windows nt", "windows-server"),
    ):
        if needle in blob:
            return label
    if "nginx" in blob and "ollama" in blob:
        return "front-ollama"
    return None


def _hint_from_ports(open_ports: list[int]) -> str | None:
    if 8006 in open_ports:
        return "proxmox"
    if 902 in open_ports:
        return "vmware-esxi"
    if 5000 in open_ports or 5001 in open_ports:
        return "synology/nas"
    if 3389 in open_ports and 445 in open_ports:
        return "windows"
    if 445 in open_ports and 3389 not in open_ports:
        return "smb"
    return None


def _iter_hosts(cidr: str) -> list[str]:
    try:
        net = ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        return []
    return [str(ip) for ip in net.hosts()]


def _scan_ports(hosts: list[str], ports: tuple[int, ...], timeout_s: float, workers: int) -> dict[str, list[int]]:
    """Scan TCP parallèle ; retourne {ip: [ports ouverts]}."""
    if not hosts or not ports:
        return {}
    open_by_host: dict[str, set[int]] = {}
    tasks = [(h, p) for h in hosts for p in ports]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(_tcp_reachable, h, p, timeout_s): (h, p) for h, p in tasks}
        for fut in as_completed(future_map):
            host, port = future_map[fut]
            try:
                if fut.result():
                    open_by_host.setdefault(host, set()).add(port)
            except Exception:
                pass
    return {h: sorted(ps) for h, ps in open_by_host.items()}


def _scan_subnet(cidr: str) -> dict[str, list[int]]:
    if not _env_bool("LBG_NETWORK_SCAN_ENABLED", default=True):
        return {}
    hosts = _iter_hosts(cidr)
    if not hosts:
        return {}
    timeout_s = _scan_timeout_s()
    workers = _scan_workers()
    alive = _scan_ports(hosts, _DISCOVERY_PORTS, timeout_s, workers)
    if not alive:
        return {}
    detail_hosts = list(alive.keys())
    detailed = _scan_ports(detail_hosts, _DETAIL_PORTS, timeout_s, workers)
    for host, ports in alive.items():
        detailed.setdefault(host, [])
        for p in ports:
            if p not in detailed[host]:
                detailed[host].append(p)
        detailed[host].sort()
    return detailed


def _parse_known_devices_json() -> list[dict[str, Any]]:
    raw = os.environ.get("LBG_NETWORK_KNOWN_DEVICES", "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        host = str(row.get("host") or row.get("ip") or "").strip()
        if not host:
            continue
        out.append(
            {
                "host": host.split(":")[0],
                "server_id": str(row.get("server_id") or row.get("id") or row.get("label") or host),
                "role": str(row.get("role") or "known"),
                "label": str(row.get("label") or row.get("name") or row.get("server_id") or host),
            }
        )
    return out


def _router_host() -> str | None:
    raw = os.environ.get("LBG_NETWORK_ROUTER_HOST", "").strip()
    if not raw:
        return None
    return raw.split(":")[0] or None


def _apply_router_override(known: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Force l'étiquette routeur sur l'IP réelle (Freebox souvent .254, pas .1)."""
    router_ip = _router_host()
    if not router_ip:
        return known
    filtered = [
        row
        for row in known
        if not (row.get("role") == "router" and str(row.get("host") or "") != router_ip)
    ]
    router_row = {
        "host": router_ip,
        "server_id": "router",
        "role": "router",
        "label": "freebox-routeur",
        "device_hint": "freebox-routeur",
        "source": "env_router",
    }
    return [router_row] + filtered


def _known_from_env_urls() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for env_key, (role, label) in _URL_ENV_LABELS.items():
        raw = os.environ.get(env_key, "").strip()
        if not raw:
            continue
        host = urlparse(raw).hostname
        if not host or host in seen:
            continue
        seen.add(host)
        rows.append(
            {
                "host": host,
                "server_id": role,
                "role": role,
                "label": label,
                "source": "env_url",
            }
        )
    return rows


def _topology_probes() -> list[dict[str, Any]]:
    """Sondes HTTP ciblées sur la topologie LBG (core/front/mmo/desktop)."""
    rows: list[dict[str, Any]] = []
    for server_id, role_label in (("core", "core"), ("front", "front"), ("mmo", "mmo"), ("precu", "precu")):
        host = resolve_host(server_id)
        if not host:
            continue
        rows.append(
            {
                "server_id": server_id,
                "role": role_label,
                "label": f"lbg-{role_label}",
                "host": host,
                "probes": [{"kind": "tcp", "port": 22, "label": "ssh"}],
            }
        )
    http_by_role: dict[str, list[tuple[int, str, str]]] = {
        "core": [
            (8000, "/healthz", "backend"),
            (8010, "/healthz", "orchestrator"),
            (8020, "/healthz", "agent-dialogue"),
            (8055, "/healthz", "agent-pm"),
        ],
        "front": [(8080, "/", "pilot-nginx"), (11434, "/api/tags", "ollama")],
        "mmo": [(8050, "/healthz", "mmo-server"), (7733, "/", "mmmorpg-ws")],
        "precu": [],
    }
    for row in rows:
        host = row["host"]
        role = row["role"]
        for port, path, label in http_by_role.get(role, []):
            row["probes"].append(
                {"kind": "http", "port": port, "path": path, "label": label, "url": f"http://{host}:{port}{path}"}
            )
        if role == "precu":
            for port, label in ((44453, "core3-precu-login"), (44462, "core3-precu-status"), (44463, "core3-precu-ping")):
                row["probes"].append({"kind": "tcp", "port": port, "label": label})
    desktop = os.environ.get("LBG_AGENT_DESKTOP_URL", "").strip().rstrip("/")
    if desktop:
        parsed = urlparse(desktop)
        if parsed.hostname:
            rows.append(
                {
                    "server_id": "desktop",
                    "role": "desktop",
                    "label": "pc-windows",
                    "host": parsed.hostname,
                    "probes": [{"kind": "http", "url": f"{desktop.rstrip('/')}/healthz", "label": "agent-desktop"}],
                }
            )
    return rows


def _merge_catalog(
    known: list[dict[str, Any]],
    topology: list[dict[str, Any]],
    scan: dict[str, list[int]],
) -> list[dict[str, Any]]:
    by_ip: dict[str, dict[str, Any]] = {}

    def _upsert(entry: dict[str, Any]) -> None:
        host = str(entry.get("host") or "")
        if not host:
            return
        cur = by_ip.get(host)
        if cur is None:
            by_ip[host] = dict(entry)
            return
        for k, v in entry.items():
            if k == "probes" and isinstance(v, list):
                existing = cur.get("probes") if isinstance(cur.get("probes"), list) else []
                cur["probes"] = existing + v
            elif v and (k not in cur or not cur.get(k)):
                cur[k] = v

    for row in known:
        _upsert({**row, "source": row.get("source") or "known"})
    for row in topology:
        _upsert({**row, "source": row.get("source") or "topology"})

    for host, open_ports in sorted(scan.items(), key=lambda x: ipaddress.ip_address(x[0])):
        port_probes = [
            {"kind": "tcp", "port": p, "label": _PORT_HINTS.get(p, f"tcp-{p}"), "ok": True} for p in open_ports
        ]
        hint = _hint_from_ports(open_ports)
        if host in by_ip:
            entry = by_ip[host]
            entry["reachable"] = True
            entry["open_ports"] = open_ports
            if hint and not entry.get("device_hint"):
                entry["device_hint"] = hint
            existing_probes = entry.get("probe_results") if isinstance(entry.get("probe_results"), list) else []
            if not existing_probes:
                entry["probe_results"] = port_probes
            entry["source"] = entry.get("source") or "scan"
        else:
            by_ip[host] = {
                "server_id": f"discovered-{host.replace('.', '-')}",
                "role": "discovered",
                "label": hint or f"hôte-{host}",
                "host": host,
                "reachable": True,
                "open_ports": open_ports,
                "device_hint": hint,
                "probe_results": port_probes,
                "source": "scan",
            }

    return list(by_ip.values())


def _probe_entry(entry: dict[str, Any]) -> dict[str, Any]:
    host = str(entry.get("host") or "")
    probe_results: list[dict[str, Any]] = []
    if isinstance(entry.get("probe_results"), list):
        probe_results = list(entry["probe_results"])
    host_ok = bool(entry.get("reachable"))
    open_ports = entry.get("open_ports") if isinstance(entry.get("open_ports"), list) else []

    for probe in entry.get("probes") or []:
        if not isinstance(probe, dict):
            continue
        if probe.get("kind") == "http" and isinstance(probe.get("url"), str):
            res = _http_probe(probe["url"])
            probe_results.append({**probe, **res})
            host_ok = host_ok or bool(res.get("ok"))
        elif probe.get("kind") == "tcp" and isinstance(probe.get("port"), int):
            ok = _tcp_reachable(host, int(probe["port"]), _scan_timeout_s())
            probe_results.append({**probe, "ok": ok})
            host_ok = host_ok or ok

    if not host_ok and open_ports:
        host_ok = True

    device_hint = entry.get("device_hint")
    if not device_hint:
        device_hint = _hint_from_ports([int(p) for p in open_ports if isinstance(p, int)])
    if not device_hint and host_ok:
        for port in (80, 443, 8080, 5000, 8006):
            if port in open_ports or any(p.get("port") == port and p.get("ok") for p in probe_results):
                fp = _http_fingerprint(host, port)
                if fp.get("device_hint"):
                    device_hint = fp["device_hint"]
                    probe_results.append({"kind": "http", "port": port, "label": "fingerprint", **fp})
                    break

    device = {
        "server_id": entry.get("server_id"),
        "role": entry.get("role"),
        "label": entry.get("label") or entry.get("server_id") or host,
        "host": host,
        "canonical_role": canonical_role(str(entry.get("server_id") or "")),
        "reachable": host_ok,
        "open_ports": open_ports,
        "device_hint": device_hint,
        "probe_results": probe_results,
        "source": entry.get("source"),
    }
    device["action_suggestions"] = _suggest_capabilities(device)
    return device


def _format_devices_text(devices: list[dict[str, Any]], *, scan_cidr: str, n_scanned: int) -> str:
    lines = [
        f"Inventaire réseau LAN — {len(devices)} hôte(s) — scan {scan_cidr} ({n_scanned} IP) — instantané T",
        "",
    ]
    for d in devices:
        host = d.get("host", "?")
        label = d.get("label") or d.get("server_id") or "?"
        hint = d.get("device_hint")
        reachable = d.get("reachable")
        mark = "OK" if reachable else "KO"
        extra = f" [{hint}]" if hint else ""
        ports = d.get("open_ports") or []
        hostname = d.get("hostname")
        host_s = f"{host}" + (f" / {hostname}" if hostname else "")
        port_s = f" ports={','.join(str(p) for p in ports)}" if ports else ""
        sugg = d.get("action_suggestions") or []
        sugg_s = f" → caps: {', '.join(sugg)}" if sugg else ""
        lines.append(f"• {label} ({host_s}) — {mark}{extra}{port_s}{sugg_s}")
        for p in d.get("probe_results") or []:
            plabel = p.get("label", p.get("kind", "?"))
            if p.get("kind") == "http":
                st = "OK" if p.get("ok") else "KO"
                code = p.get("status_code", "")
                extra_p = f" HTTP {code}" if code else (f" — {p.get('error')}" if p.get("error") else "")
                lines.append(f"    - {plabel}: {st}{extra_p}")
            elif p.get("kind") == "tcp":
                st = "open" if p.get("ok") else "closed"
                lines.append(f"    - {plabel} :{p.get('port')} {st}")
    return "\n".join(lines)


def run_network_inventory(
    *,
    actor_id: str,
    text: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Scan sous-réseau + sondes sur hôtes connus (read-only)."""
    _ = actor_id, text
    ctx = context if isinstance(context, dict) else {}
    cidr = str(ctx.get("network_scan_cidr") or _scan_cidr())
    known = _apply_router_override(_parse_known_devices_json() + _known_from_env_urls())
    topology = _topology_probes()
    scan = _scan_subnet(cidr) if ctx.get("network_scan") is not False else {}
    catalog = _merge_catalog(known, topology, scan)
    devices = [_probe_entry(entry) for entry in catalog]
    _resolve_hostnames(devices)
    for d in devices:
        d["action_suggestions"] = _suggest_capabilities(d)
    devices.sort(
        key=lambda d: (
            0 if d.get("source") in ("known", "topology", "env_url", "env_router") else 1,
            ipaddress.ip_address(str(d.get("host") or "0.0.0.0")),
        )
    )
    n_scanned = len(_iter_hosts(cidr))
    devices_export = _devices_export_payload(devices)
    return {
        "ok": True,
        "agent": "network_inventory",
        "handler": "network_inventory",
        "devices": devices,
        "devices_export": devices_export,
        "n_devices": len(devices),
        "n_hosts_scanned": n_scanned,
        "scan_cidr": cidr,
        "n_hosts_alive": len(scan),
        "reply": _format_devices_text(devices, scan_cidr=cidr, n_scanned=n_scanned),
        "source": "lan_scan+probes",
        "ts": time.time(),
    }
