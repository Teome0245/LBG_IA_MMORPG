"""Périmètre plateforme Atlas — LLM dual (110 heavy / 111 light) + runtime (140/245/246)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from team.ollama_audit import audit_ollama_lan


def _host_ip(env_key: str, default: str) -> str:
    raw = os.environ.get(env_key, default).strip()
    return raw.split(":")[0].split("/")[0]


def admin_infra_perimeter() -> list[str]:
    """Hôtes obligatoires Atlas (front legacy .112 hors périmètre critique)."""
    return ["110", "111", "140", "245", "246"]


def platform_host_specs() -> list[dict[str, Any]]:
    ip110 = _host_ip("LBG_LAN_HOST_LLM_HEAVY", _host_ip("LBG_LAN_HOST_FRONT", "192.168.0.110"))
    ip111 = _host_ip(
        "LBG_LAN_HOST_LLM_LIGHT",
        os.environ.get("LBG_REASON_LIGHT_BASE_URL", "http://192.168.0.111:11434")
        .replace("http://", "")
        .replace("https://", "")
        .split(":")[0]
        or "192.168.0.111",
    )
    ip112 = _host_ip("LBG_LAN_HOST_FRONT_LEGACY", "192.168.0.112")
    ip140 = _host_ip("LBG_LAN_HOST_CORE", "192.168.0.140")
    ip245 = _host_ip("LBG_LAN_HOST_PRECU", _host_ip("LBG_LAN_HOST_MMO_SERVER", "192.168.0.245"))
    ip246 = _host_ip("LBG_LAN_HOST_CORE3_PRIME", _host_ip("LBG_LAN_HOST_MMO", "192.168.0.246"))

    sidecar = os.environ.get("LBG_CORE3_SIDECAR_URL", f"http://{ip246}:8791").strip().rstrip("/")
    gateway_http = os.environ.get("LBG_TEAM_GODOT_GATEWAY_HOST", ip246).strip().split(":")[0]
    gateway_health = f"http://{gateway_http}:8765/health"

    probe_front_legacy = os.environ.get("LBG_ATLAS_PROBE_FRONT_LEGACY", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )

    specs: list[dict[str, Any]] = [
        {
            "id": "llm_heavy_110",
            "label": "Ollama heavy (CT 110 / .110)",
            "host": ip110,
            "perimeter_id": "110",
            "role": "llm_heavy",
            "required": True,
            "ollama_primary": True,
            "ollama_tier": "heavy",
            "probes": [
                {"kind": "ollama_tags", "url": f"http://{ip110}:11434/api/tags"},
            ],
        },
        {
            "id": "llm_light_111",
            "label": "Ollama light (NUC CT / .111)",
            "host": ip111,
            "perimeter_id": "111",
            "role": "llm_light",
            "required": True,
            "ollama_primary": False,
            "ollama_tier": "light",
            "probes": [
                {"kind": "ollama_tags", "url": f"http://{ip111}:11434/api/tags"},
            ],
        },
        {
            "id": "core_140",
            "label": "Core orchestrateur + Pilot Nginx",
            "host": ip140,
            "perimeter_id": "140",
            "role": "orchestrator_team",
            "required": True,
            "probes": [
                {
                    "kind": "http",
                    "url": os.environ.get("LBG_ORCHESTRATOR_URL", f"http://{ip140}:8010").rstrip("/") + "/healthz",
                },
                {
                    "kind": "http",
                    "url": os.environ.get("LBG_PILOT_URL", f"http://{ip140}:8080").rstrip("/") + "/",
                },
            ],
        },
        {
            "id": "precu_245",
            "label": "PreCU sandbox / MMO HTTP",
            "host": ip245,
            "perimeter_id": "245",
            "role": "precu_runtime",
            "required": True,
            "probes": [
                {"kind": "http", "url": f"http://{ip245}:8050/healthz"},
            ],
        },
        {
            "id": "prime_246",
            "label": "Prime Core3 + gateway + sidecar IA",
            "host": ip246,
            "perimeter_id": "246",
            "role": "prime_runtime",
            "required": True,
            "probes": [
                {"kind": "http", "url": gateway_health},
                {"kind": "http", "url": f"{sidecar}/healthz"},
            ],
        },
    ]

    if probe_front_legacy:
        specs.append(
            {
                "id": "front_legacy_112",
                "label": "Front legacy Pilot/Nginx (ex-VM 110)",
                "host": ip112,
                "perimeter_id": "112",
                "role": "front_legacy",
                "required": False,
                "probes": [
                    {"kind": "http", "url": f"http://{ip112}:8080/"},
                ],
            }
        )

    return specs


def _probe_http(url: str, *, timeout: float = 4.0) -> dict[str, Any]:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json,text/html,*/*"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(512).decode("utf-8", errors="replace")
            return {
                "url": url,
                "ok": 200 <= resp.status < 300,
                "status": resp.status,
                "body_preview": body[:160],
            }
    except urllib.error.HTTPError as exc:
        return {"url": url, "ok": False, "status": exc.code, "error": str(exc)[:160]}
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return {"url": url, "ok": False, "status": None, "error": str(exc)[:160]}


def _probe_ollama_tags(url: str, *, timeout: float = 6.0) -> dict[str, Any]:
    probe = _probe_http(url, timeout=timeout)
    if not probe.get("ok"):
        return {**probe, "kind": "ollama_tags", "model_count": 0, "model_names": []}
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        models = data.get("models") if isinstance(data, dict) else []
        names: list[str] = []
        if isinstance(models, list):
            for m in models:
                if isinstance(m, dict) and m.get("name"):
                    names.append(str(m["name"]))
        return {
            **probe,
            "kind": "ollama_tags",
            "model_count": len(names),
            "model_names": names[:24],
        }
    except (json.JSONDecodeError, OSError, urllib.error.URLError, TimeoutError) as exc:
        return {**probe, "kind": "ollama_tags", "model_count": 0, "model_names": [], "parse_error": str(exc)[:120]}


def audit_platform_host(spec: dict[str, Any]) -> dict[str, Any]:
    probes_out: list[dict[str, Any]] = []
    for probe in spec.get("probes") or []:
        if not isinstance(probe, dict):
            continue
        url = str(probe.get("url") or "")
        kind = str(probe.get("kind") or "http")
        if kind == "ollama_tags":
            probes_out.append(_probe_ollama_tags(url))
        else:
            probes_out.append({**_probe_http(url), "kind": kind})
    ok = all(bool(p.get("ok")) for p in probes_out) if probes_out else False
    return {
        "id": spec.get("id"),
        "label": spec.get("label"),
        "host": spec.get("host"),
        "perimeter_id": spec.get("perimeter_id"),
        "role": spec.get("role"),
        "required": bool(spec.get("required", True)),
        "ok": ok,
        "probes": probes_out,
        "ollama_primary": bool(spec.get("ollama_primary")),
        "ollama_tier": spec.get("ollama_tier"),
    }


def audit_admin_infra_platform() -> dict[str, Any]:
    """Audit multi-hôtes Atlas — dual LLM 110/111 + runtime."""
    hosts = [audit_platform_host(spec) for spec in platform_host_specs()]
    ollama = audit_ollama_lan()
    required_hosts = [h for h in hosts if h.get("required", True)]
    host_ok = sum(1 for h in required_hosts if h.get("ok"))
    hosts_total = len(required_hosts)
    gaps: list[str] = []
    for h in hosts:
        if h.get("required", True) and not h.get("ok"):
            gaps.append(f"{h.get('perimeter_id')}: {h.get('id')} probe KO")
        elif not h.get("required", True) and not h.get("ok"):
            gaps.append(f"optional-{h.get('perimeter_id')}: {h.get('id')} probe KO")
    if ollama.get("gaps"):
        for g in ollama["gaps"]:
            gaps.append(f"ollama-config: {g}")

    recommendations: list[str] = list(ollama.get("recommendations") or [])
    if not any(h.get("id") == "llm_light_111" and h.get("ok") for h in hosts):
        recommendations.append(
            "111 light KO — vérifier CT ollama-light sur Proxmox 200 ; router/json basculent en failover 110."
        )
    if not any(h.get("id") == "llm_heavy_110" and h.get("ok") for h in hosts):
        recommendations.append("110 heavy KO — vérifier CT 110 ollama-110 sur Proxmox 201.")
    if not any(h.get("id") == "precu_245" and h.get("ok") for h in hosts):
        recommendations.append("245 PreCU : vérifier lbg-mmo / healthz :8050 (sandbox parallèle).")
    if not any(h.get("id") == "prime_246" and h.get("ok") for h in hosts):
        recommendations.append("246 Prime : vérifier gateway :8765/health et sidecar IA :8791/healthz.")
    if host_ok < hosts_total:
        recommendations.append("Périmètre Atlas incomplet — corriger les sondes critiques avant bench long.")

    topology = {
        "llm_heavy": "192.168.0.110:11434 (CT ollama, code/pm/forge/26b)",
        "llm_light": "192.168.0.111:11434 (NUC CT, Clean qwen2.5:3b / Fast llama3.2:3b)",
        "pilot": "192.168.0.140:8080 (Nginx Pilot canonique — proxy API locale)",
        "front_legacy": "192.168.0.112 (Traefik/:3000/:80 slim — Pilot Nginx optionnel)",
        "routing": "LBG_REASON_LIGHT_BASE_URL → 111 ; LBG_REASON_LOCAL_BASE_URL → 110",
    }

    return {
        "ok": host_ok == hosts_total and bool(ollama.get("ok", False) or not ollama.get("error")),
        "track": "admin_infra_platform",
        "perimeter": admin_infra_perimeter(),
        "hosts_ok": host_ok,
        "hosts_total": hosts_total,
        "hosts": hosts,
        "topology": topology,
        "ollama_primary": ollama,
        "gaps": gaps,
        "recommendations": recommendations,
    }
