"""Registre des workers desktop Windows — routage ciblé par machine (PC, AD, …)."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

# Alias logiques → identifiant de cible.
_ALIASES: dict[str, str] = {
    "pc": "pc",
    "desktop": "pc",
    "windows": "pc",
    "pc-windows": "pc",
    "mon-pc": "pc",
    "ad": "ad",
    "srv-ad": "ad",
    "serveur-ad": "ad",
    "server-ad": "ad",
    "active-directory": "ad",
    "windows-ad": "ad",
    "default": "default",
}


@dataclass(frozen=True)
class DesktopTarget:
    target_id: str
    label: str
    host: str
    url: str
    aliases: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, str]:
        return {
            "id": self.target_id,
            "label": self.label,
            "host": self.host,
            "url": self.url,
        }


@dataclass(frozen=True)
class ResolvedDesktopTarget:
    target_id: str
    label: str
    host: str
    url: str
    source: str  # explicit | host | text | default


def _normalize_id(raw: str) -> str | None:
    s = (raw or "").strip().lower()
    if not s:
        return None
    return _ALIASES.get(s, s)


def _parse_targets_json() -> list[DesktopTarget]:
    raw = os.environ.get("LBG_DESKTOP_TARGETS", "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[DesktopTarget] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        tid = str(row.get("id") or row.get("target_id") or "").strip()
        url = str(row.get("url") or "").strip().rstrip("/")
        host = str(row.get("host") or "").strip()
        if not url:
            continue
        if not host:
            host = urlparse(url).hostname or ""
        if not tid:
            tid = host or "target"
        aliases_raw = row.get("aliases") or []
        aliases = tuple(str(a).strip().lower() for a in aliases_raw if str(a).strip()) if isinstance(aliases_raw, list) else ()
        out.append(
            DesktopTarget(
                target_id=tid,
                label=str(row.get("label") or row.get("name") or tid),
                host=host.split(":")[0],
                url=url,
                aliases=aliases,
            )
        )
    return out


def _targets_from_legacy_env() -> list[DesktopTarget]:
    """Construit le registre à partir des variables historiques."""
    rows: list[DesktopTarget] = []
    seen_urls: set[str] = set()

    def _add(*, tid: str, label: str, env_key: str, aliases: tuple[str, ...]) -> None:
        raw = os.environ.get(env_key, "").strip().rstrip("/")
        if not raw or raw in seen_urls:
            return
        host = urlparse(raw).hostname or ""
        if not host:
            return
        seen_urls.add(raw)
        rows.append(DesktopTarget(target_id=tid, label=label, host=host, url=raw, aliases=aliases))

    _add(tid="pc", label="pc-windows", env_key="AGENT_WINDOWS_URL", aliases=("pc", "desktop", "windows"))
    default_url = os.environ.get("LBG_AGENT_DESKTOP_URL", "").strip().rstrip("/")
    if default_url and default_url not in seen_urls:
        host = urlparse(default_url).hostname or ""
        if host:
            seen_urls.add(default_url)
            rows.append(
                DesktopTarget(
                    target_id="default",
                    label="desktop-default",
                    host=host.split(":")[0],
                    url=default_url,
                    aliases=("default",),
                )
            )
    elif default_url in seen_urls:
        # LBG_AGENT_DESKTOP_URL identique à AGENT_WINDOWS_URL → alias default → pc
        pass

    _add(
        tid="ad",
        label="serveur-ad",
        env_key="AGENT_WINDOWS_SRV_AD_URL",
        aliases=("ad", "srv-ad", "serveur-ad", "active-directory"),
    )

    # Si default manquant mais pc présent, default = pc
    if not any(t.target_id == "default" for t in rows):
        pc = next((t for t in rows if t.target_id == "pc"), None)
        if pc is not None:
            rows.append(
                DesktopTarget(
                    target_id="default",
                    label=pc.label,
                    host=pc.host,
                    url=pc.url,
                    aliases=("default",),
                )
            )
    return rows


def list_desktop_targets() -> list[DesktopTarget]:
    explicit = _parse_targets_json()
    if explicit:
        return explicit
    return _targets_from_legacy_env()


def _by_id(targets: list[DesktopTarget]) -> dict[str, DesktopTarget]:
    index: dict[str, DesktopTarget] = {}
    for t in targets:
        index[t.target_id] = t
        index[t.target_id.lower()] = t
        for alias in t.aliases:
            index[alias.lower()] = t
        if t.host:
            index[t.host.lower()] = t
    return index


def infer_desktop_target_from_text(text: str) -> str | None:
    """Déduit la cible depuis le langage naturel (ex. « sur le serveur AD »)."""
    norm = (text or "").strip().lower()
    if not norm:
        return None
    if re.search(r"\b(serveur ad|srv[- ]?ad|sur l['']?ad|sur le serveur ad|active directory)\b", norm):
        return "ad"
    if re.search(r"\b192\.168\.0\.100\b", text):
        return "ad"
    if re.search(r"\b(sur mon pc|mon pc|pc windows|poste windows)\b", norm):
        return "pc"
    if re.search(r"\b192\.168\.0\.10\b", text):
        return "pc"
    return None


def resolve_desktop_target(
    context: dict[str, Any] | None = None,
    text: str = "",
) -> ResolvedDesktopTarget | None:
    """
    Résout l'URL du worker desktop.

    Priorité : ``context.desktop_target`` / ``desktop_target_host`` / IP dans le texte
    / inférence NL / ``LBG_AGENT_DESKTOP_URL`` (default).
    """
    ctx = context if isinstance(context, dict) else {}
    targets = list_desktop_targets()
    if not targets:
        legacy = os.environ.get("LBG_AGENT_DESKTOP_URL", "").strip().rstrip("/")
        if not legacy:
            return None
        host = urlparse(legacy).hostname or ""
        return ResolvedDesktopTarget("default", "desktop-default", host, legacy, "default")

    index = _by_id(targets)

    explicit = ctx.get("desktop_target")
    if isinstance(explicit, str) and explicit.strip():
        tid = _normalize_id(explicit) or explicit.strip().lower()
        hit = index.get(tid)
        if hit is not None:
            return ResolvedDesktopTarget(hit.target_id, hit.label, hit.host, hit.url, "explicit")

    host_raw = ctx.get("desktop_target_host")
    if isinstance(host_raw, str) and host_raw.strip():
        host = host_raw.strip().split(":")[0].lower()
        hit = index.get(host)
        if hit is not None:
            return ResolvedDesktopTarget(hit.target_id, hit.label, hit.host, hit.url, "host")

    action = ctx.get("desktop_action")
    if isinstance(action, dict):
        for key in ("target", "machine", "desktop_target", "host"):
            raw = action.get(key)
            if isinstance(raw, str) and raw.strip():
                tid = _normalize_id(raw) or raw.strip().lower()
                hit = index.get(tid)
                if hit is not None:
                    return ResolvedDesktopTarget(hit.target_id, hit.label, hit.host, hit.url, "explicit")

    inferred = infer_desktop_target_from_text(text)
    if inferred:
        hit = index.get(inferred)
        if hit is not None:
            return ResolvedDesktopTarget(hit.target_id, hit.label, hit.host, hit.url, "text")

    # IP littérale dans le texte
    for ip in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text or ""):
        hit = index.get(ip.lower())
        if hit is not None:
            return ResolvedDesktopTarget(hit.target_id, hit.label, hit.host, hit.url, "text")

    default = index.get("default") or index.get("pc") or targets[0]
    return ResolvedDesktopTarget(default.target_id, default.label, default.host, default.url, "default")
