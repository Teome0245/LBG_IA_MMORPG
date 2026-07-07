"""Outils assistant PM — grep repo, SSH lecture seule, sonde Core3."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Iterator

import httpx

from lbg_agents.repo_context import grep_repo
from lbg_agents.ssh_mcp_tools import list_ssh_targets, ssh_run_readonly

_TOOL_TAG_RE = re.compile(r"<lbg_tool>\s*(\{.*?\})\s*</lbg_tool>", re.DOTALL | re.IGNORECASE)

_SAFE_SSH_COMMANDS = (
    "uptime",
    "hostname",
    "systemctl is-active nginx",
    "systemctl is-active core3",
    "free -h",
    "df -h /",
)


def infer_tools_from_text(text: str) -> list[dict[str, Any]]:
    """Heuristiques — outils proposés avant le tour LLM."""
    t = (text or "").strip()
    if not t:
        return []
    low = t.lower()
    tools: list[dict[str, Any]] = []

    if re.search(r"\b(grep|cherche|où est|ou est|fichier|dans le code|dans le repo)\b", low):
        pat = _extract_grep_pattern(t)
        if pat:
            tools.append({"name": "grep", "args": {"pattern": pat}})

    host = _extract_host(t)
    if host and re.search(r"\b(ssh|health|healthz|diagnostic|sonde|systemd|uptime|mémoire|memoire)\b", low):
        cmd = "uptime"
        if "healthz" in low or "nginx" in low:
            cmd = "systemctl is-active nginx"
        elif "core3" in low and "mmo" not in low:
            cmd = "systemctl is-active core3"
        elif "mémoire" in low or "memoire" in low or "free" in low:
            cmd = "free -h"
        tools.append({"name": "ssh", "args": {"server_id": host, "command": cmd}})

    if re.search(r"\b(core3|mmo|sidecar|lia)\b", low) and re.search(
        r"\b(sonde|status|état|etat|health|prime)\b", low
    ):
        tools.append({"name": "core3", "args": {"action": "health"}})

    return tools[:3]


def parse_tool_calls_from_llm(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in _TOOL_TAG_RE.finditer(text or ""):
        try:
            obj = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("name"), str):
            args = obj.get("args") if isinstance(obj.get("args"), dict) else {}
            out.append({"name": obj["name"], "args": args})
    return out[:2]


def strip_tool_tags(text: str) -> str:
    return _TOOL_TAG_RE.sub("", text or "").strip()


def execute_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    tool = (name or "").strip().lower()
    a = args if isinstance(args, dict) else {}

    if tool == "grep":
        pattern = str(a.get("pattern") or "").strip()
        hits = grep_repo(pattern)
        lines = []
        for h in hits:
            if h.get("file"):
                lines.append(f"{h['file']}:{h.get('line', '?')}: {h.get('content', '')}")
            elif h.get("error"):
                lines.append(str(h["error"]))
        return {
            "tool": "grep",
            "ok": True,
            "args": {"pattern": pattern},
            "output": "\n".join(lines)[:6000] or "(aucun résultat)",
        }

    if tool == "ssh":
        server_id = str(a.get("server_id") or a.get("host") or "").strip()
        command = str(a.get("command") or "uptime").strip()
        if command not in _SAFE_SSH_COMMANDS:
            command = "uptime"
        res = ssh_run_readonly(server_id, command)
        output = (res.get("stdout") or res.get("stderr") or res.get("error") or "")[:4000]
        return {
            "tool": "ssh",
            "ok": bool(res.get("ok")),
            "args": {"server_id": server_id, "command": command},
            "output": output,
            "meta": {"exit_code": res.get("exit_code"), "host": res.get("host")},
        }

    if tool == "core3":
        base = os.environ.get("LBG_CORE3_IA_SIDECAR_URL", "").strip().rstrip("/")
        if not base:
            return {
                "tool": "core3",
                "ok": False,
                "args": a,
                "output": "LBG_CORE3_IA_SIDECAR_URL non défini.",
            }
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get(f"{base}/healthz")
            body = r.text[:2000]
            return {
                "tool": "core3",
                "ok": r.status_code == 200,
                "args": {"action": "health", "url": f"{base}/healthz"},
                "output": f"HTTP {r.status_code}\n{body}",
            }
        except Exception as e:
            return {"tool": "core3", "ok": False, "args": a, "output": str(e)[:500]}

    if tool == "list_ssh_targets":
        rows = list_ssh_targets()
        return {
            "tool": "list_ssh_targets",
            "ok": True,
            "args": {},
            "output": json.dumps(rows, ensure_ascii=False, indent=2)[:4000],
        }

    return {"tool": tool or "unknown", "ok": False, "args": a, "output": f"outil inconnu : {tool}"}


def run_tool_pipeline(
    text: str,
    *,
    extra_tools: list[dict[str, Any]] | None = None,
) -> Iterator[dict[str, Any]]:
    """Exécute les outils inférés ; yield événements tool_start / tool_result."""
    seen: set[str] = set()
    queue = list(extra_tools or []) + infer_tools_from_text(text)
    for spec in queue:
        name = str(spec.get("name") or "")
        args = spec.get("args") if isinstance(spec.get("args"), dict) else {}
        key = f"{name}:{json.dumps(args, sort_keys=True)}"
        if key in seen:
            continue
        seen.add(key)
        yield {"kind": "tool_start", "tool": name, "args": args}
        result = execute_tool(name, args)
        yield {
            "kind": "tool_result",
            "tool": name,
            "args": args,
            "ok": result.get("ok"),
            "output": result.get("output", ""),
        }


def format_tools_for_llm(results: list[dict[str, Any]]) -> str:
    if not results:
        return ""
    lines = ["## Résultats outils (lecture seule)", ""]
    for r in results:
        lines.append(f"### {r.get('tool')} {r.get('args')}")
        lines.append(str(r.get("output") or "")[:4000])
        lines.append("")
    return "\n".join(lines)


def _extract_host(text: str) -> str | None:
    m = re.search(r"\blinux-(\d{1,3})\b", text, re.I)
    if m:
        return f"linux-{m.group(1)}"
    m = re.search(r"\b(?:sur|la|vm|host|core|front)\s+(?:la\s+)?(\d{2,3})\b", text, re.I)
    if m:
        return f"linux-{m.group(1)}"
    m = re.search(r"\b(\d{2,3})\s*\??\s*$", text.strip())
    if m and int(m.group(1)) >= 100:
        return f"linux-{m.group(1)}"
    return None


def _extract_grep_pattern(text: str) -> str | None:
    m = re.search(r"`([^`]{2,60})`", text)
    if m:
        return m.group(1).strip()
    m = re.search(r'grep\s+["\']?([^\s"\']{2,40})', text, re.I)
    if m:
        return m.group(1).strip()
    for kw in ("pilot_chat", "assistant/chat", "core3", "orchestrator", "plan_de_route"):
        if kw in text.lower():
            return kw
    return None
