"""
Exécuteur Desktop (agent Windows dédié) — MVP "hybride".

Objectif :
- L’orchestrateur (VM) route une intention `desktop_control` → `agent.desktop`
- `agent.desktop` appelle un worker HTTP sur la machine Windows (UI automation / web / mail)
- Le worker applique **allowlists**, **dry-run**, **approval_token**, et écrit un audit JSONL.

⚠️ Par défaut, tout est en **dry-run**.
"""

from __future__ import annotations

import json
import os
import secrets
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def _split_csv(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def _truthy(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def desktop_dry_run(context: dict[str, Any] | None = None) -> bool:
    """
    Si `LBG_DESKTOP_DRY_RUN` est actif, il est prioritaire sur le contexte.
    Sinon, `context.desktop_dry_run: true` force le dry-run pour cet appel.
    """
    env = os.environ.get("LBG_DESKTOP_DRY_RUN", "").strip()
    if env:
        return _truthy(env)
    if isinstance(context, dict) and context.get("desktop_dry_run") is True:
        return True
    return False


def desktop_requires_approval() -> bool:
    return bool(os.environ.get("LBG_DESKTOP_APPROVAL_TOKEN", "").strip())


def desktop_approval_ok(context: dict[str, Any] | None = None) -> bool:
    token = os.environ.get("LBG_DESKTOP_APPROVAL_TOKEN", "").strip()
    if not token:
        return True
    if not isinstance(context, dict):
        return False
    got = context.get("desktop_approval")
    if not isinstance(got, str):
        return False
    return secrets.compare_digest(got, token)


def _url_allowlist() -> list[str]:
    raw = os.environ.get("LBG_DESKTOP_URL_ALLOWLIST", "").strip()
    if not raw:
        return []
    return _split_csv(raw)


def _url_host_allowlist() -> list[str]:
    """
    Liste de hosts/domaines autorisés pour `open_url`.

    Exemples :
    - `google.com` autorise `google.com` et `www.google.com`
    - `*.example.org` autorise tout sous-domaine de `example.org` (mais pas le domaine racine)
    """
    raw = os.environ.get("LBG_DESKTOP_URL_HOST_ALLOWLIST", "").strip()
    if not raw:
        return []
    return _split_csv(raw)


def _host_matches(needle: str, rule: str) -> bool:
    n = (needle or "").strip().lower().rstrip(".")
    r = (rule or "").strip().lower().rstrip(".")
    if not n or not r:
        return False
    if r.startswith("*."):
        suf = r[2:]
        return bool(suf) and n.endswith("." + suf)
    if n == r:
        return True
    # règle "domaine": autorise le domaine et ses sous-domaines
    return n.endswith("." + r)


def _url_allowed_by_host(url: str) -> bool:
    allow_hosts = _url_host_allowlist()
    if not allow_hosts:
        return False
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.scheme not in {"http", "https"}:
        return False
    host = (p.hostname or "").strip().lower()
    if not host:
        return False
    for rule in allow_hosts:
        if _host_matches(host, rule):
            return True
    return False


def _file_allowlist_dirs() -> list[Path]:
    raw = os.environ.get("LBG_DESKTOP_FILE_ALLOWLIST_DIRS", "").strip()
    if not raw:
        return []
    out: list[Path] = []
    for item in _split_csv(raw):
        try:
            out.append(Path(item).expanduser().resolve())
        except Exception:
            continue
    return out


def _url_is_allowed(url: str) -> bool:
    allow = _url_allowlist()
    if url in allow:
        return True
    return _url_allowed_by_host(url)


def _path_is_allowed(path_str: str) -> bool:
    dirs = _file_allowlist_dirs()
    if not dirs:
        return False
    try:
        p = Path(path_str).expanduser().resolve()
    except Exception:
        return False
    for d in dirs:
        try:
            if p == d or d in p.parents:
                return True
        except Exception:
            continue
    return False


def _audit_write(line: dict[str, Any]) -> None:
    """
    Écrit une ligne JSON audit sur stdout et/ou fichier JSONL.
    """
    line = dict(line)
    line["ts"] = datetime.now(timezone.utc).isoformat()
    raw = json.dumps(line, ensure_ascii=False)

    if _truthy(os.environ.get("LBG_DESKTOP_AUDIT_STDOUT", "1")):
        print(raw)

    path = os.environ.get("LBG_DESKTOP_AUDIT_LOG_PATH", "").strip()
    if not path:
        return
    try:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.open("a", encoding="utf-8").write(raw + "\n")
    except Exception as e:
        print(
            json.dumps(
                {"event": "agents.desktop.audit_file_error", "error": f"{type(e).__name__}: {e}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )


@dataclass(frozen=True)
class DesktopOutcome:
    ok: bool
    outcome: str
    detail: str | None = None


def _gate_or_dry_run(
    *,
    context: dict[str, Any],
    dry_run: bool,
) -> DesktopOutcome | None:
    if dry_run:
        return None
    if desktop_requires_approval() and not desktop_approval_ok(context):
        return DesktopOutcome(ok=False, outcome="approval_denied", detail="Approval token requis (context.desktop_approval)")
    return None


def run_desktop_action(
    *,
    actor_id: str,
    text: str,
    action: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    """
    Exécute une action Desktop allowlistée.

    Actions MVP :
    - `open_url` : ouvre une URL via navigateur (webbrowser)
      - champ `url` (string) doit être dans `LBG_DESKTOP_URL_ALLOWLIST` (match exact)
    - `notepad_append` : ouvre un éditeur sur un fichier et append du texte
      - champs `path` (string) + `text` (string)
      - `path` doit être sous un des répertoires `LBG_DESKTOP_FILE_ALLOWLIST_DIRS`
    """
    trace_id = context.get("_trace_id") if isinstance(context.get("_trace_id"), str) else None
    dry_run = desktop_dry_run(context)

    kind = (action.get("kind") or "").strip()
    base = {
        "agent": "desktop_executor",
        "handler": "desktop",
        "actor_id": actor_id,
        "request_text": text,
        "kind": kind,
        "meta": {"dry_run": dry_run, "execution_gated": desktop_requires_approval()},
    }

    if kind == "open_url":
        url = action.get("url")
        if not isinstance(url, str) or not url.strip():
            out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `url` requis"}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out
        url = url.strip()
        if not _url_is_allowed(url):
            allow_hosts = _url_host_allowlist()
            out = {
                **base,
                "ok": False,
                "outcome": "allowlist_denied",
                "error": "URL non autorisée (allowlist exacte)",
                "url": url,
                "url_host_allowlist_count": len(allow_hosts),
                "url_host_allowlist_preview": allow_hosts[:5],
                "url_hint": "Configurer LBG_DESKTOP_URL_ALLOWLIST (URLs exactes) ou LBG_DESKTOP_URL_HOST_ALLOWLIST (domaines/hosts).",
            }
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out
        gate = _gate_or_dry_run(context=context, dry_run=dry_run)
        if gate is not None:
            out = {**base, "ok": False, "outcome": gate.outcome, "error": gate.detail, "url": url}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out
        if dry_run:
            out = {**base, "ok": True, "outcome": "dry_run", "url": url}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out

        try:
            import webbrowser

            ok = bool(webbrowser.open(url, new=2))
            outcome = "ok" if ok else "error"
            out = {**base, "ok": ok, "outcome": outcome, "url": url}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out
        except Exception as e:
            out = {**base, "ok": False, "outcome": "error", "error": f"{type(e).__name__}: {e}", "url": url}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out

    if kind == "notepad_append":
        path = action.get("path")
        content = action.get("text")
        if not isinstance(path, str) or not path.strip():
            out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `path` requis"}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out
        if not isinstance(content, str):
            out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `text` requis (string)"}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out

        path = path.strip()
        if not _path_is_allowed(path):
            out = {
                **base,
                "ok": False,
                "outcome": "allowlist_denied",
                "error": "Chemin fichier non autorisé",
                "path": path,
                "path_hint": "Configurer LBG_DESKTOP_FILE_ALLOWLIST_DIRS (répertoires parents autorisés).",
            }
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out

        gate = _gate_or_dry_run(context=context, dry_run=dry_run)
        if gate is not None:
            out = {**base, "ok": False, "outcome": gate.outcome, "error": gate.detail, "path": path}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out
        if dry_run:
            out = {**base, "ok": True, "outcome": "dry_run", "path": path, "bytes": len(content.encode("utf-8"))}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out

        try:
            p = Path(path).expanduser()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.open("a", encoding="utf-8").write(content)

            # Windows : ouvrir l’éditeur configuré (best-effort). Si non-Windows, on se contente d’écrire.
            if os.name == "nt":
                import subprocess
                editor = os.environ.get("LBG_DESKTOP_EDITOR", "notepad").strip().lower()
                if editor == "notepad++":
                    exe = os.environ.get("LBG_DESKTOP_NOTEPADPP_PATH", "").strip() or "notepad++.exe"
                    subprocess.Popen([exe, str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                elif editor == "word":
                    exe = os.environ.get("LBG_DESKTOP_WORD_PATH", "").strip() or "winword.exe"
                    subprocess.Popen([exe, str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                elif editor == "default":
                    try:
                        os.startfile(str(p))  # type: ignore[attr-defined]
                    except Exception:
                        subprocess.Popen(["notepad.exe", str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    subprocess.Popen(["notepad.exe", str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            out = {**base, "ok": True, "outcome": "ok", "path": str(p), "bytes": len(content.encode("utf-8"))}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out
        except Exception as e:
            out = {**base, "ok": False, "outcome": "error", "error": f"{type(e).__name__}: {e}", "path": path}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out

    out = {
        **base,
        "ok": False,
        "outcome": "unknown_kind",
        "error": "Action desktop inconnue",
        "hint": (
            'Utiliser `context.desktop_action` avec `{"kind":"open_url","url":"..."}` '
            'ou `{"kind":"notepad_append","path":"...","text":"..."}`'
        ),
    }
    _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
    return out

