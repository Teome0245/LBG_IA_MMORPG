"""
Exécuteur DevOps à liste blanche (phase B) — valide la chaîne orchestrateur → dispatch.

Actions supportées :
- ``http_get`` : GET HTTP uniquement si ``url`` figure dans ``LBG_DEVOPS_HTTP_ALLOWLIST``
  (sinon liste par défaut : healthz orchestrator + backend en 127.0.0.1).
- ``read_log_tail`` : lecture fichier si le chemin est dans ``LBG_DEVOPS_LOG_ALLOWLIST``
  (vide par défaut → action refusée).

**Dry-run global** : ``LBG_DEVOPS_DRY_RUN=1`` (ou ``true`` / ``yes`` / ``on``) — aucune requête
HTTP ni lecture disque ; les contrôles d’allowlist s’appliquent quand même.
``context.devops_dry_run: true`` force en plus le dry-run pour une requête (utile depuis ``/pilot/``).

**Audit** : une ligne JSON par action, ``event: agents.devops.audit`` (champ ``ts`` UTC).
Par défaut **stdout** (journald) ; en complément (ou seul si stdout désactivé) : fichier JSONL
via ``LBG_DEVOPS_AUDIT_LOG_PATH`` (append). ``LBG_DEVOPS_AUDIT_STDOUT=0`` désactive stdout.

**Approbation exécution réelle** : si ``LBG_DEVOPS_APPROVAL_TOKEN`` est défini (non vide), tout
``http_get`` / ``read_log_tail`` **hors dry-run** exige ``context.devops_approval`` identique au
jeton (comparaison ``secrets.compare_digest``). Le jeton n’est jamais écrit dans l’audit.

Aucun shell libre, pas d’autres méthodes HTTP.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import sys
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

_audit_file_error_logged = False


def _split_allowlist(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def _http_allowlist() -> list[str]:
    raw = os.environ.get("LBG_DEVOPS_HTTP_ALLOWLIST", "").strip()
    if raw:
        return _split_allowlist(raw)
    return [
        "http://127.0.0.1:8010/healthz",
        "http://127.0.0.1:8000/healthz",
    ]


def _log_allowlist() -> list[str]:
    raw = os.environ.get("LBG_DEVOPS_LOG_ALLOWLIST", "").strip()
    if not raw:
        return []
    return _split_allowlist(raw)


def _default_probe_url() -> str:
    u = os.environ.get("LBG_DEVOPS_DEFAULT_PROBE_URL", "").strip()
    if u:
        return u
    return "http://127.0.0.1:8010/healthz"


def _env_dry_run() -> bool:
    v = os.environ.get("LBG_DEVOPS_DRY_RUN", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def is_devops_dry_run(context: dict[str, Any]) -> bool:
    """Dry-run si variable d’environnement **ou** ``context.devops_dry_run`` est vrai."""
    if _env_dry_run():
        return True
    return context.get("devops_dry_run") is True


def _normalize_url(url: str) -> str:
    u = url.strip()
    p = urlparse(u)
    if p.scheme not in ("http", "https"):
        raise ValueError("schéma http(s) requis")
    if not p.netloc:
        raise ValueError("URL invalide")
    return u


def _url_allowed(url: str, allowed: list[str]) -> bool:
    n = _normalize_url(url)
    return n in allowed


def _path_allowed(path: str, allowed: list[str]) -> bool:
    p = os.path.normpath(path.strip())
    for a in allowed:
        if os.path.normpath(a.strip()) == p:
            return True
    return False


def _trace_id(context: dict[str, Any]) -> str | None:
    t = context.get("_trace_id")
    return t if isinstance(t, str) and t.strip() else None


def _audit_stdout_enabled() -> bool:
    v = os.environ.get("LBG_DEVOPS_AUDIT_STDOUT", "").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    return True


def _audit_log_file_path() -> str | None:
    p = os.environ.get("LBG_DEVOPS_AUDIT_LOG_PATH", "").strip()
    return p if p else None


def _append_audit_to_file(line: str) -> None:
    global _audit_file_error_logged
    path = _audit_log_file_path()
    if not path:
        return
    try:
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError as e:
        if not _audit_file_error_logged:
            _audit_file_error_logged = True
            print(
                json.dumps(
                    {
                        "event": "agents.devops.audit_file_error",
                        "path": path,
                        "error": f"{type(e).__name__}: {e}"[:300],
                    },
                    ensure_ascii=False,
                ),
                file=sys.stderr,
                flush=True,
            )


def _emit_devops_audit_record(rec: dict[str, Any]) -> None:
    rec = {**rec, "ts": datetime.now(timezone.utc).isoformat()}
    line = json.dumps(rec, ensure_ascii=False) + "\n"
    if _audit_stdout_enabled():
        print(line[:-1], file=sys.stdout, flush=True)
    _append_audit_to_file(line)


def _audit_devops(
    *,
    trace_id: str | None,
    actor_id: str,
    action_kind: str | None,
    dry_run: bool,
    dry_run_source: str,
    outcome: str,
    approval_gate_active: bool = False,
    url: str | None = None,
    path: str | None = None,
    max_bytes: int | None = None,
    http_status: int | None = None,
    error: str | None = None,
) -> None:
    rec: dict[str, Any] = {
        "event": "agents.devops.audit",
        "trace_id": trace_id,
        "actor_id": actor_id,
        "action_kind": action_kind,
        "dry_run": dry_run,
        "dry_run_source": dry_run_source,
        "outcome": outcome,
        "approval_gate_active": approval_gate_active,
    }
    if url is not None:
        rec["url"] = url
    if path is not None:
        rec["path"] = path
    if max_bytes is not None:
        rec["max_bytes"] = max_bytes
    if http_status is not None:
        rec["http_status"] = http_status
    if error:
        rec["error"] = error[:500]
    _emit_devops_audit_record(rec)


def _dry_run_source(context: dict[str, Any]) -> str:
    if _env_dry_run():
        return "env"
    if context.get("devops_dry_run") is True:
        return "context"
    return "off"


def _approval_token() -> str | None:
    t = os.environ.get("LBG_DEVOPS_APPROVAL_TOKEN", "").strip()
    return t if t else None


def execution_requires_approval() -> bool:
    """Vrai si une exécution réelle (non dry-run) exige ``context.devops_approval``."""
    return _approval_token() is not None


def _approval_granted(context: dict[str, Any]) -> bool:
    token = _approval_token()
    if token is None:
        return True
    got = context.get("devops_approval")
    if not isinstance(got, str):
        return False
    try:
        return secrets.compare_digest(got.strip(), token)
    except (TypeError, ValueError):
        return False


def _approval_error() -> str:
    return (
        "Exécution réelle refusée : renseigner context.devops_approval avec la valeur de "
        "LBG_DEVOPS_APPROVAL_TOKEN (ou activer le dry-run pour simuler sans jeton)."
    )


def _http_get(url: str, *, dry_run: bool, context: dict[str, Any]) -> dict[str, Any]:
    allowed = _http_allowlist()
    u_raw = url.strip()
    if not _url_allowed(url, allowed):
        return {
            "ok": False,
            "kind": "http_get",
            "url": u_raw,
            "error": "URL non autorisée (hors LBG_DEVOPS_HTTP_ALLOWLIST)",
            "allowed_count": len(allowed),
        }
    u = _normalize_url(url)
    if dry_run:
        return {
            "ok": True,
            "kind": "http_get",
            "url": u,
            "dry_run": True,
            "note": "Dry-run : aucune requête HTTP émise (voir LBG_DEVOPS_DRY_RUN ou context.devops_dry_run).",
        }
    if not _approval_granted(context):
        return {
            "ok": False,
            "kind": "http_get",
            "url": u,
            "approval_required": True,
            "error": _approval_error(),
        }
    timeout = httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0)
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            r = client.get(u)
        preview = r.text[:800] if r.text else ""
        return {
            "ok": True,
            "kind": "http_get",
            "url": u,
            "status_code": r.status_code,
            "body_preview": preview,
        }
    except Exception as e:
        return {
            "ok": False,
            "kind": "http_get",
            "url": u,
            "error": f"{type(e).__name__}: {e}",
        }


def _read_log_tail(path: str, max_bytes: int, *, dry_run: bool, context: dict[str, Any]) -> dict[str, Any]:
    allowed = _log_allowlist()
    pstrip = path.strip()
    if not allowed:
        return {
            "ok": False,
            "kind": "read_log_tail",
            "path": pstrip,
            "error": "LBG_DEVOPS_LOG_ALLOWLIST vide — lecture fichier désactivée",
        }
    if not _path_allowed(path, allowed):
        return {
            "ok": False,
            "kind": "read_log_tail",
            "path": pstrip,
            "error": "chemin non autorisé (hors LBG_DEVOPS_LOG_ALLOWLIST)",
        }
    cap = min(max(64, max_bytes), 65_536)
    if dry_run:
        return {
            "ok": True,
            "kind": "read_log_tail",
            "path": os.path.normpath(pstrip),
            "max_bytes": cap,
            "dry_run": True,
            "note": "Dry-run : aucune lecture disque (voir LBG_DEVOPS_DRY_RUN ou context.devops_dry_run).",
        }
    if not _approval_granted(context):
        return {
            "ok": False,
            "kind": "read_log_tail",
            "path": os.path.normpath(pstrip),
            "approval_required": True,
            "error": _approval_error(),
        }
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            if size <= cap:
                f.seek(0)
                data = f.read()
            else:
                f.seek(size - cap)
                data = f.read()
        text = data.decode("utf-8", errors="replace")
        return {
            "ok": True,
            "kind": "read_log_tail",
            "path": path,
            "bytes_read": len(data),
            "tail_preview": text[-2000:] if len(text) > 2000 else text,
        }
    except OSError as e:
        return {
            "ok": False,
            "kind": "read_log_tail",
            "path": pstrip,
            "error": f"{type(e).__name__}: {e}",
        }


def _outcome_from_http_result(res: dict[str, Any], *, dry_run: bool) -> str:
    if not res.get("ok"):
        if res.get("approval_required"):
            return "approval_denied"
        if "non autorisée" in (res.get("error") or ""):
            return "denied"
        return "executed_error"
    if dry_run or res.get("dry_run"):
        return "dry_run_planned"
    return "executed_ok"


def _outcome_from_log_result(res: dict[str, Any], *, dry_run: bool) -> str:
    if not res.get("ok"):
        if res.get("approval_required"):
            return "approval_denied"
        err = res.get("error") or ""
        if "vide" in err or "non autorisé" in err or "hors" in err:
            return "denied"
        return "executed_error"
    if dry_run or res.get("dry_run"):
        return "dry_run_planned"
    return "executed_ok"


def run_devops_action(
    *,
    actor_id: str,
    text: str,
    action: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    trace_id = _trace_id(context)
    dry_run = is_devops_dry_run(context)
    dr_src = _dry_run_source(context)
    gated = execution_requires_approval()
    kind = action.get("kind")

    if kind == "http_get":
        url = action.get("url")
        if not isinstance(url, str) or not url.strip():
            _audit_devops(
                trace_id=trace_id,
                actor_id=actor_id,
                action_kind="http_get",
                dry_run=dry_run,
                dry_run_source=dr_src,
                outcome="validation_error",
                approval_gate_active=gated,
                error="http_get requiert action.url (string)",
            )
            return {
                "agent": "devops_executor",
                "handler": "devops",
                "actor_id": actor_id,
                "request_text": text,
                "error": "http_get requiert action.url (string)",
                "devops_action": dict(action),
                "meta": {
                    "allowlist": True,
                    "dry_run": dry_run,
                    "dry_run_source": dr_src,
                    "execution_gated": gated,
                },
            }
        result = _http_get(url, dry_run=dry_run, context=context)
        oc = _outcome_from_http_result(result, dry_run=dry_run)
        _audit_devops(
            trace_id=trace_id,
            actor_id=actor_id,
            action_kind="http_get",
            dry_run=dry_run,
            dry_run_source=dr_src,
            outcome=oc,
            approval_gate_active=gated,
            url=result.get("url"),
            http_status=result.get("status_code"),
            error=result.get("error"),
        )
        return {
            "agent": "devops_executor",
            "handler": "devops",
            "actor_id": actor_id,
            "request_text": text,
            "devops_action": dict(action),
            "result": result,
            "meta": {
                "allowlist": True,
                "sterile": False,
                "dry_run": dry_run,
                "dry_run_source": dr_src,
                "execution_gated": gated,
            },
        }

    if kind == "read_log_tail":
        path = action.get("path")
        if not isinstance(path, str) or not path.strip():
            _audit_devops(
                trace_id=trace_id,
                actor_id=actor_id,
                action_kind="read_log_tail",
                dry_run=dry_run,
                dry_run_source=dr_src,
                outcome="validation_error",
                approval_gate_active=gated,
                error="read_log_tail requiert action.path (string)",
            )
            return {
                "agent": "devops_executor",
                "handler": "devops",
                "actor_id": actor_id,
                "request_text": text,
                "error": "read_log_tail requiert action.path (string)",
                "devops_action": dict(action),
                "meta": {
                    "allowlist": True,
                    "dry_run": dry_run,
                    "dry_run_source": dr_src,
                    "execution_gated": gated,
                },
            }
        raw_mb = action.get("max_bytes", 8192)
        try:
            max_bytes = int(raw_mb) if raw_mb is not None else 8192
        except (TypeError, ValueError):
            max_bytes = 8192
        result = _read_log_tail(path.strip(), max_bytes, dry_run=dry_run, context=context)
        oc = _outcome_from_log_result(result, dry_run=dry_run)
        _audit_devops(
            trace_id=trace_id,
            actor_id=actor_id,
            action_kind="read_log_tail",
            dry_run=dry_run,
            dry_run_source=dr_src,
            outcome=oc,
            approval_gate_active=gated,
            path=result.get("path"),
            max_bytes=max_bytes,
            error=result.get("error"),
        )
        return {
            "agent": "devops_executor",
            "handler": "devops",
            "actor_id": actor_id,
            "request_text": text,
            "devops_action": dict(action),
            "result": result,
            "meta": {
                "allowlist": True,
                "sterile": False,
                "dry_run": dry_run,
                "dry_run_source": dr_src,
                "execution_gated": gated,
            },
        }

    _audit_devops(
        trace_id=trace_id,
        actor_id=actor_id,
        action_kind=str(kind) if kind is not None else None,
        dry_run=dry_run,
        dry_run_source=dr_src,
        outcome="validation_error",
        approval_gate_active=gated,
        error=f"kind inconnu: {kind!r}",
    )
    return {
        "agent": "devops_executor",
        "handler": "devops",
        "actor_id": actor_id,
        "request_text": text,
        "error": f"kind inconnu: {kind!r} (attendu http_get | read_log_tail)",
        "devops_action": dict(action),
        "meta": {
            "allowlist": True,
            "dry_run": dry_run,
            "dry_run_source": dr_src,
            "execution_gated": gated,
        },
    }


def default_action_from_text(text: str) -> dict[str, Any] | None:
    """Si le texte indique une sonde sans ``context.devops_action``, propose un http_get par défaut."""
    t = text.strip().lower()
    if re.search(r"\b(sonde\s+devops|probe\s+devops|devops\s+healthz)\b", t):
        return {"kind": "http_get", "url": _default_probe_url()}
    if re.search(r"\bhealthz\s+backend\b", t):
        return {"kind": "http_get", "url": "http://127.0.0.1:8000/healthz"}
    if re.search(r"\bhealthz\s+orchestrator\b", t):
        return {"kind": "http_get", "url": "http://127.0.0.1:8010/healthz"}
    if re.search(r"\bdevops\b", t):
        return {"kind": "http_get", "url": _default_probe_url()}
    return None
