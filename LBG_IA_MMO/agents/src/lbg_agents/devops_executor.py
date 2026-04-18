"""
Exécuteur DevOps à liste blanche (phase B) — valide la chaîne orchestrateur → dispatch.

Actions supportées :
- ``http_get`` : GET HTTP uniquement si ``url`` figure dans ``LBG_DEVOPS_HTTP_ALLOWLIST``
  (sinon liste par défaut : healthz orchestrator + backend en 127.0.0.1).
- ``read_log_tail`` : lecture fichier si le chemin est dans ``LBG_DEVOPS_LOG_ALLOWLIST``
  (vide par défaut → action refusée).
- ``systemd_is_active`` : ``systemctl is-active <unit>`` uniquement si ``unit`` figure dans
  ``LBG_DEVOPS_SYSTEMD_UNIT_ALLOWLIST`` (virgules ; **vide par défaut** → refus).
- ``systemd_restart`` : ``systemctl restart <unit>`` uniquement si ``unit`` figure dans
  ``LBG_DEVOPS_SYSTEMD_RESTART_ALLOWLIST`` (virgules ; **vide par défaut** → refus).
  Quotas : ``LBG_DEVOPS_SYSTEMD_RESTART_MAX_PER_WINDOW`` (défaut **8**) tentatives réelles
  max par fenêtre glissante ``LBG_DEVOPS_SYSTEMD_RESTART_WINDOW_S`` (défaut **3600** s).
  Fenêtre UTC optionnelle : ``LBG_DEVOPS_SYSTEMD_RESTART_MAINTENANCE_UTC=HH:MM-HH:MM`` —
  si définie, les redémarrages **réels** ne sont autorisés que lorsque l’heure UTC courante
  est dans cet intervalle (traverse minuit si ``HH:MM`` début > fin).
- ``selfcheck`` : enchaîne **uniquement** des sondes dérivées de l’environnement (HTTP healthz
  autorisés, puis unités systemd autorisées), chacune soumise aux **mêmes** garde-fous
  (allowlist, dry-run, approbation). Réponse agrégée + ``remediation_hints`` (texte, **sans**
  exécution de correctifs destructeurs). URLs optionnelles : ``LBG_DEVOPS_SELFCHECK_HTTP`` ;
  unités optionnelles : ``LBG_DEVOPS_SELFCHECK_SYSTEMD`` (sous-ensemble de l’allowlist systemd).

**Dry-run global** : ``LBG_DEVOPS_DRY_RUN=1`` (ou ``true`` / ``yes`` / ``on``) — aucune requête
HTTP ni lecture disque ; **aucun** ``systemctl`` ; les contrôles d’allowlist s’appliquent quand même.
``context.devops_dry_run: true`` force en plus le dry-run pour une requête (utile depuis ``/pilot/``).

**Audit** : une ligne JSON par action, ``event: agents.devops.audit`` (champ ``ts`` UTC).
Par défaut **stdout** (journald) ; en complément (ou seul si stdout désactivé) : fichier JSONL
via ``LBG_DEVOPS_AUDIT_LOG_PATH`` (append). ``LBG_DEVOPS_AUDIT_STDOUT=0`` désactive stdout.

**Approbation exécution réelle** : si ``LBG_DEVOPS_APPROVAL_TOKEN`` est défini (non vide), tout
``http_get`` / ``read_log_tail`` / ``systemd_is_active`` / ``systemd_restart`` / ``selfcheck`` **hors dry-run** exige ``context.devops_approval`` identique au
jeton (comparaison ``secrets.compare_digest``). Le jeton n’est jamais écrit dans l’audit.

Aucun shell libre, pas d’autres méthodes HTTP.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import sys
import time
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


def _systemd_unit_allowlist() -> list[str]:
    raw = os.environ.get("LBG_DEVOPS_SYSTEMD_UNIT_ALLOWLIST", "").strip()
    if not raw:
        return []
    return _split_allowlist(raw)


def _systemd_restart_allowlist() -> list[str]:
    """
    Allowlist dédiée aux redémarrages.

    Par défaut vide → `systemd_restart` refusé, même si `systemd_is_active` est autorisé.
    """
    raw = os.environ.get("LBG_DEVOPS_SYSTEMD_RESTART_ALLOWLIST", "").strip()
    if not raw:
        return []
    return _split_allowlist(raw)


# Tentatives réelles (hors dry-run) — fenêtre glissante par processus (best-effort si plusieurs workers).
_restart_real_ts: list[float] = []


def _restart_max_per_window() -> int:
    raw = os.environ.get("LBG_DEVOPS_SYSTEMD_RESTART_MAX_PER_WINDOW", "8").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 8
    return max(1, min(n, 50))


def _restart_window_s() -> int:
    raw = os.environ.get("LBG_DEVOPS_SYSTEMD_RESTART_WINDOW_S", "3600").strip()
    try:
        s = int(raw)
    except ValueError:
        s = 3600
    return max(60, min(s, 86400 * 7))


def _minutes_since_midnight_utc(now: datetime) -> int:
    return now.hour * 60 + now.minute


def _parse_hhmm_to_minutes(s: str) -> int | None:
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", s.strip())
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        return None
    return h * 60 + mi


def _restart_maintenance_allows(now: datetime | None = None) -> tuple[bool, str | None]:
    raw = os.environ.get("LBG_DEVOPS_SYSTEMD_RESTART_MAINTENANCE_UTC", "").strip()
    if not raw:
        return True, None
    parts = raw.replace("–", "-").split("-", 1)
    if len(parts) != 2:
        return (
            False,
            "LBG_DEVOPS_SYSTEMD_RESTART_MAINTENANCE_UTC invalide (attendu HH:MM-HH:MM UTC)",
        )
    sm = _parse_hhmm_to_minutes(parts[0])
    em = _parse_hhmm_to_minutes(parts[1])
    if sm is None or em is None:
        return False, "LBG_DEVOPS_SYSTEMD_RESTART_MAINTENANCE_UTC : heures invalides"
    dt = now or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    cur = _minutes_since_midnight_utc(dt)
    if sm <= em:
        ok = sm <= cur <= em
    else:
        ok = cur >= sm or cur <= em
    if ok:
        return True, None
    return (
        False,
        "hors fenêtre de maintenance UTC (LBG_DEVOPS_SYSTEMD_RESTART_MAINTENANCE_UTC)",
    )


def _restart_quota_reserve() -> tuple[bool, str | None]:
    max_n = _restart_max_per_window()
    win = float(_restart_window_s())
    now = time.time()
    global _restart_real_ts
    _restart_real_ts = [t for t in _restart_real_ts if now - t < win]
    if len(_restart_real_ts) >= max_n:
        return False, f"quota systemd_restart ({max_n} tentatives / {int(win)}s)"
    _restart_real_ts.append(now)
    return True, None


_SYSTEMD_UNIT_RE = re.compile(r"^[a-zA-Z0-9@._-]+\.(service|socket)$")

_SELFCHECK_MAX_HTTP = 8
_SELFCHECK_MAX_SYSTEMD = 6


def _valid_systemd_unit(unit: str) -> bool:
    u = unit.strip()
    return bool(_SYSTEMD_UNIT_RE.fullmatch(u))


def _unit_in_systemd_allowlist(unit: str, allowed: list[str]) -> bool:
    u = unit.strip()
    for a in allowed:
        if a.strip() == u:
            return True
    return False


def _default_probe_url() -> str:
    u = os.environ.get("LBG_DEVOPS_DEFAULT_PROBE_URL", "").strip()
    if u:
        return u
    return "http://127.0.0.1:8010/healthz"


def _origin_healthz(url: str) -> str | None:
    try:
        n = _normalize_url(url.strip())
    except ValueError:
        return None
    p = urlparse(n)
    if not p.scheme or not p.netloc:
        return None
    return f"{p.scheme}://{p.netloc}/healthz"


def _dedupe_urls_preserve(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        try:
            nu = _normalize_url(u.strip())
        except ValueError:
            continue
        if nu in seen:
            continue
        seen.add(nu)
        out.append(nu)
    return out


def _collect_selfcheck_http_urls() -> list[str]:
    raw = os.environ.get("LBG_DEVOPS_SELFCHECK_HTTP", "").strip()
    candidates: list[str] = []
    if raw:
        candidates.extend(_split_allowlist(raw))
    else:
        candidates.append(_default_probe_url())
        ou = os.environ.get("LBG_ORCHESTRATOR_URL", "").strip()
        if ou:
            h = _origin_healthz(ou)
            if h:
                candidates.append(h)
        bu = os.environ.get("MMMORPG_IA_BACKEND_URL", "").strip()
        if bu:
            h = _origin_healthz(bu)
            if h:
                candidates.append(h)
    candidates = _dedupe_urls_preserve(candidates)
    allowed = _http_allowlist()
    out: list[str] = []
    for u in candidates:
        if not _url_allowed(u, allowed):
            continue
        out.append(u)
        if len(out) >= _SELFCHECK_MAX_HTTP:
            break
    return out


def _collect_selfcheck_systemd_units() -> list[str]:
    allowed = _systemd_unit_allowlist()
    if not allowed:
        return []
    raw = os.environ.get("LBG_DEVOPS_SELFCHECK_SYSTEMD", "").strip()
    if raw:
        want = _split_allowlist(raw)
        picked = []
        for u in want:
            uu = u.strip()
            if _valid_systemd_unit(uu) and _unit_in_systemd_allowlist(uu, allowed):
                picked.append(uu)
    else:
        # Par défaut : cœur stack uniquement (évite mmo/mmmorpg absents sur VM core).
        preferred = ("lbg-backend.service", "lbg-orchestrator.service")
        picked = [u for u in preferred if _unit_in_systemd_allowlist(u, allowed)]
        if not picked:
            picked = list(allowed)
    out: list[str] = []
    seen: set[str] = set()
    for u in picked:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
        if len(out) >= _SELFCHECK_MAX_SYSTEMD:
            break
    return out


def _step_http_healthy(res: dict[str, Any], *, dry_run: bool) -> bool:
    if not res.get("ok"):
        return False
    if dry_run or res.get("dry_run"):
        return True
    sc = res.get("status_code")
    return isinstance(sc, int) and 200 <= sc < 300


def _step_systemd_healthy(res: dict[str, Any], *, dry_run: bool) -> bool:
    if not res.get("ok"):
        return False
    if dry_run or res.get("dry_run"):
        return True
    st = (res.get("active_state") or "").strip().lower()
    ec = res.get("exit_code")
    return st == "active" and ec == 0


def _selfcheck_remediation_hints(steps: list[dict[str, Any]]) -> list[str]:
    hints: list[str] = []
    for s in steps:
        if s.get("healthy") is True:
            continue
        res = s.get("result") or {}
        kind = s.get("kind")
        if kind == "http_get":
            err = str(res.get("error") or "")
            url = str(res.get("url") or "")
            if "non autorisée" in err:
                hints.append(
                    "Élargir LBG_DEVOPS_HTTP_ALLOWLIST (ou LBG_DEVOPS_SELFCHECK_HTTP) pour inclure les URLs healthz du selfcheck."
                )
            elif res.get("status_code") is not None:
                try:
                    code = int(res["status_code"])
                except (TypeError, ValueError):
                    code = 0
                if not (200 <= code < 300):
                    hints.append(f"Vérifier le service derrière {url} (HTTP {code}).")
            elif err:
                hints.append(f"Erreur HTTP sur {url}: {err[:180]}")
        elif kind == "systemd_is_active":
            u = str(res.get("unit") or "?")
            err = str(res.get("error") or "")
            if err and ("vide" in err or "hors" in err or "allowlist" in err.lower()):
                hints.append(
                    "Configurer LBG_DEVOPS_SYSTEMD_UNIT_ALLOWLIST (et LBG_DEVOPS_SELFCHECK_SYSTEMD si besoin) pour les unités à sonder."
                )
            else:
                hints.append(
                    f"Unité {u} non saine — voir journalctl -u {u} -n 80 ; redémarrage hors exécuteur : sudo systemctl restart {u}"
                )
    seen: set[str] = set()
    ordered: list[str] = []
    for h in hints:
        if h not in seen:
            seen.add(h)
            ordered.append(h)
    return ordered


def _run_devops_selfcheck(
    *,
    actor_id: str,
    text: str,
    context: dict[str, Any],
    dry_run: bool,
    dr_src: str,
    gated: bool,
    trace_id: str | None,
) -> dict[str, Any]:
    http_urls = _collect_selfcheck_http_urls()
    units = _collect_selfcheck_systemd_units()
    if not http_urls and not units:
        msg = (
            "selfcheck: aucune étape (URLs HTTP absentes ou hors allowlist, "
            "et aucune unité systemd dans LBG_DEVOPS_SYSTEMD_UNIT_ALLOWLIST)"
        )
        _audit_devops(
            trace_id=trace_id,
            actor_id=actor_id,
            action_kind="selfcheck",
            dry_run=dry_run,
            dry_run_source=dr_src,
            outcome="validation_error",
            approval_gate_active=gated,
            error=msg,
        )
        return {
            "agent": "devops_executor",
            "handler": "devops",
            "actor_id": actor_id,
            "request_text": text,
            "devops_action": {"kind": "selfcheck"},
            "error": msg,
            "meta": {
                "allowlist": True,
                "dry_run": dry_run,
                "dry_run_source": dr_src,
                "execution_gated": gated,
            },
        }

    steps: list[dict[str, Any]] = []
    for url in http_urls:
        result = _http_get(url, dry_run=dry_run, context=context)
        oc = _outcome_from_http_result(result, dry_run=dry_run)
        _audit_devops(
            trace_id=trace_id,
            actor_id=actor_id,
            action_kind="selfcheck_http_get",
            dry_run=dry_run,
            dry_run_source=dr_src,
            outcome=oc,
            approval_gate_active=gated,
            url=result.get("url"),
            http_status=result.get("status_code"),
            error=result.get("error"),
        )
        h = _step_http_healthy(result, dry_run=dry_run)
        steps.append({"kind": "http_get", "url": url, "outcome": oc, "healthy": h, "result": result})

    for unit in units:
        result = _systemd_is_active(unit, dry_run=dry_run, context=context)
        oc = _outcome_from_systemd_result(result, dry_run=dry_run)
        ures = result.get("unit")
        _audit_devops(
            trace_id=trace_id,
            actor_id=actor_id,
            action_kind="selfcheck_systemd_is_active",
            dry_run=dry_run,
            dry_run_source=dr_src,
            outcome=oc,
            approval_gate_active=gated,
            unit=ures if isinstance(ures, str) else None,
            error=result.get("error"),
        )
        h = _step_systemd_healthy(result, dry_run=dry_run)
        steps.append(
            {"kind": "systemd_is_active", "unit": unit, "outcome": oc, "healthy": h, "result": result}
        )

    overall = all(bool(s.get("healthy")) for s in steps)
    hints = _selfcheck_remediation_hints(steps)
    if dry_run:
        sum_oc = "dry_run_planned"
    else:
        sum_oc = "executed_ok" if overall else "executed_error"
    _audit_devops(
        trace_id=trace_id,
        actor_id=actor_id,
        action_kind="selfcheck_summary",
        dry_run=dry_run,
        dry_run_source=dr_src,
        outcome=sum_oc,
        approval_gate_active=gated,
        error=None if overall or dry_run else "une ou plusieurs étapes selfcheck non saines",
    )
    bundle: dict[str, Any] = {
        "kind": "selfcheck",
        "ok": overall,
        "dry_run": dry_run,
        "steps": steps,
        "remediation_hints": hints,
        "http_checked": len(http_urls),
        "systemd_checked": len(units),
    }
    return {
        "agent": "devops_executor",
        "handler": "devops",
        "actor_id": actor_id,
        "request_text": text,
        "devops_action": {"kind": "selfcheck"},
        "result": bundle,
        "meta": {
            "allowlist": True,
            "sterile": False,
            "dry_run": dry_run,
            "dry_run_source": dr_src,
            "execution_gated": gated,
        },
    }


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
    unit: str | None = None,
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
    if unit is not None:
        rec["unit"] = unit
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


def _outcome_from_systemd_result(res: dict[str, Any], *, dry_run: bool) -> str:
    if not res.get("ok"):
        if res.get("approval_required"):
            return "approval_denied"
        err = res.get("error") or ""
        el = err.lower()
        if (
            "vide" in err
            or "non autoris" in err
            or "hors" in err
            or "allowlist" in el
            or "invalide" in el
            or "quota" in el
            or "maintenance" in el
        ):
            return "denied"
        return "executed_error"
    if dry_run or res.get("dry_run"):
        return "dry_run_planned"
    return "executed_ok"


def _systemd_is_active(unit: str, *, dry_run: bool, context: dict[str, Any]) -> dict[str, Any]:
    allowed = _systemd_unit_allowlist()
    u = unit.strip()
    if not allowed:
        return {
            "ok": False,
            "kind": "systemd_is_active",
            "unit": u,
            "error": "LBG_DEVOPS_SYSTEMD_UNIT_ALLOWLIST vide — systemd_is_active désactivé",
        }
    if not _valid_systemd_unit(u):
        return {
            "ok": False,
            "kind": "systemd_is_active",
            "unit": u,
            "error": "nom d’unité invalide (attendu ex. lbg-backend.service)",
        }
    if not _unit_in_systemd_allowlist(u, allowed):
        return {
            "ok": False,
            "kind": "systemd_is_active",
            "unit": u,
            "error": "unité hors LBG_DEVOPS_SYSTEMD_UNIT_ALLOWLIST",
        }
    if dry_run:
        return {
            "ok": True,
            "kind": "systemd_is_active",
            "unit": u,
            "dry_run": True,
            "note": "Dry-run : aucun systemctl (voir LBG_DEVOPS_DRY_RUN ou context.devops_dry_run).",
        }
    if not _approval_granted(context):
        return {
            "ok": False,
            "kind": "systemd_is_active",
            "unit": u,
            "approval_required": True,
            "error": _approval_error(),
        }
    try:
        cp = subprocess.run(
            ["systemctl", "is-active", u],
            capture_output=True,
            text=True,
            timeout=12.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {
            "ok": False,
            "kind": "systemd_is_active",
            "unit": u,
            "error": f"{type(e).__name__}: {e}",
        }
    out = (cp.stdout or "").strip()
    err = (cp.stderr or "").strip()
    # 0 = active ; 3 = inactive / failed selon versions ; 4 = unknown unit (souvent)
    return {
        "ok": True,
        "kind": "systemd_is_active",
        "unit": u,
        "active_state": out or "(vide)",
        "exit_code": int(cp.returncode),
        "stderr_preview": err[:400] if err else "",
    }


def _systemd_restart(unit: str, *, dry_run: bool, context: dict[str, Any]) -> dict[str, Any]:
    """
    Redémarrage systemd ultra-borné : `systemctl restart <unit>`.

    - unit doit être valide (regex)
    - unit doit être dans `LBG_DEVOPS_SYSTEMD_RESTART_ALLOWLIST` (vide par défaut → refus)
    - dry-run / approbation : mêmes garde-fous que `systemd_is_active`
    """
    allowed = _systemd_restart_allowlist()
    u = unit.strip()
    if not allowed:
        return {
            "ok": False,
            "kind": "systemd_restart",
            "unit": u,
            "error": "LBG_DEVOPS_SYSTEMD_RESTART_ALLOWLIST vide — systemd_restart désactivé",
        }
    if not _valid_systemd_unit(u):
        return {
            "ok": False,
            "kind": "systemd_restart",
            "unit": u,
            "error": "nom d’unité invalide (attendu ex. lbg-backend.service)",
        }
    if not _unit_in_systemd_allowlist(u, allowed):
        return {
            "ok": False,
            "kind": "systemd_restart",
            "unit": u,
            "error": "unité hors LBG_DEVOPS_SYSTEMD_RESTART_ALLOWLIST",
        }
    if dry_run:
        return {
            "ok": True,
            "kind": "systemd_restart",
            "unit": u,
            "dry_run": True,
            "note": "Dry-run : aucun systemctl restart (voir LBG_DEVOPS_DRY_RUN ou context.devops_dry_run).",
        }
    if not _approval_granted(context):
        return {
            "ok": False,
            "kind": "systemd_restart",
            "unit": u,
            "approval_required": True,
            "error": _approval_error(),
        }
    ok_m, err_m = _restart_maintenance_allows()
    if not ok_m:
        return {
            "ok": False,
            "kind": "systemd_restart",
            "unit": u,
            "error": err_m or "fenêtre de maintenance",
        }
    ok_q, err_q = _restart_quota_reserve()
    if not ok_q:
        return {
            "ok": False,
            "kind": "systemd_restart",
            "unit": u,
            "error": err_q or "quota systemd_restart",
        }
    try:
        cp = subprocess.run(
            ["sudo", "-n", "systemctl", "restart", u],
            capture_output=True,
            text=True,
            timeout=45.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {
            "ok": False,
            "kind": "systemd_restart",
            "unit": u,
            "error": f"{type(e).__name__}: {e}",
        }
    err = (cp.stderr or "").strip()
    return {
        "ok": cp.returncode == 0,
        "kind": "systemd_restart",
        "unit": u,
        "exit_code": int(cp.returncode),
        "stderr_preview": err[:400] if err else "",
    }


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

    if kind == "selfcheck":
        return _run_devops_selfcheck(
            actor_id=actor_id,
            text=text,
            context=context,
            dry_run=dry_run,
            dr_src=dr_src,
            gated=gated,
            trace_id=trace_id,
        )

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

    if kind == "systemd_is_active":
        raw_unit = action.get("unit")
        if not isinstance(raw_unit, str) or not raw_unit.strip():
            _audit_devops(
                trace_id=trace_id,
                actor_id=actor_id,
                action_kind="systemd_is_active",
                dry_run=dry_run,
                dry_run_source=dr_src,
                outcome="validation_error",
                approval_gate_active=gated,
                error="systemd_is_active requiert action.unit (string)",
            )
            return {
                "agent": "devops_executor",
                "handler": "devops",
                "actor_id": actor_id,
                "request_text": text,
                "error": "systemd_is_active requiert action.unit (string)",
                "devops_action": dict(action),
                "meta": {
                    "allowlist": True,
                    "dry_run": dry_run,
                    "dry_run_source": dr_src,
                    "execution_gated": gated,
                },
            }
        result = _systemd_is_active(raw_unit.strip(), dry_run=dry_run, context=context)
        oc = _outcome_from_systemd_result(result, dry_run=dry_run)
        ures = result.get("unit")
        _audit_devops(
            trace_id=trace_id,
            actor_id=actor_id,
            action_kind="systemd_is_active",
            dry_run=dry_run,
            dry_run_source=dr_src,
            outcome=oc,
            approval_gate_active=gated,
            unit=ures if isinstance(ures, str) else None,
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

    if kind == "systemd_restart":
        raw_unit = action.get("unit")
        if not isinstance(raw_unit, str) or not raw_unit.strip():
            _audit_devops(
                trace_id=trace_id,
                actor_id=actor_id,
                action_kind="systemd_restart",
                dry_run=dry_run,
                dry_run_source=dr_src,
                outcome="validation_error",
                approval_gate_active=gated,
                error="systemd_restart requiert action.unit (string)",
            )
            return {
                "agent": "devops_executor",
                "handler": "devops",
                "actor_id": actor_id,
                "request_text": text,
                "error": "systemd_restart requiert action.unit (string)",
                "devops_action": dict(action),
                "meta": {
                    "allowlist": True,
                    "dry_run": dry_run,
                    "dry_run_source": dr_src,
                    "execution_gated": gated,
                },
            }
        result = _systemd_restart(raw_unit.strip(), dry_run=dry_run, context=context)
        oc = _outcome_from_systemd_result(result, dry_run=dry_run)
        ures = result.get("unit")
        _audit_devops(
            trace_id=trace_id,
            actor_id=actor_id,
            action_kind="systemd_restart",
            dry_run=dry_run,
            dry_run_source=dr_src,
            outcome=oc,
            approval_gate_active=gated,
            unit=ures if isinstance(ures, str) else None,
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
        "error": f"kind inconnu: {kind!r} (attendu http_get | read_log_tail | systemd_is_active | systemd_restart | selfcheck)",
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
    if re.search(
        r"\b(auto[-\s]?diagnostic|diagnostic\s+complet|sonde\s+complète|stack\s+health|health\s+check\s+complet)\b",
        t,
    ):
        return {"kind": "selfcheck"}
    if re.search(r"\b(sonde\s+devops|probe\s+devops|devops\s+healthz)\b", t):
        return {"kind": "http_get", "url": _default_probe_url()}
    if re.search(r"\bhealthz\s+backend\b", t):
        return {"kind": "http_get", "url": "http://127.0.0.1:8000/healthz"}
    if re.search(r"\bhealthz\s+orchestrator\b", t):
        return {"kind": "http_get", "url": "http://127.0.0.1:8010/healthz"}
    if re.search(r"\bdevops\b", t):
        return {"kind": "http_get", "url": _default_probe_url()}
    return None
