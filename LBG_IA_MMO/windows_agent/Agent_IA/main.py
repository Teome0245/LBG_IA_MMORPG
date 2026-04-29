import importlib
import inspect
import logging
import subprocess
import re
import json
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException

import executor
from executor import resolve_program
from models import ActionRequest, InstallRequest
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Agent_IA")

app = FastAPI(title="Windows Agent Managed (Auto-Learning)")

# -----------------------------------------------------------------------------
# Desktop config hot-reload (sans relancer uvicorn)
# -----------------------------------------------------------------------------

_DESKTOP_CFG_CACHE: dict[str, object] = {"mtime": None, "vars": {}}


def _desktop_env_path() -> Path:
    raw = os.environ.get("LBG_DESKTOP_ENV_PATH", "").strip()
    if raw:
        return Path(raw)
    # défaut : à côté de ce script (ou cwd si lancé depuis C:\Agent_IA)
    return Path("desktop.env")


def _load_desktop_env_vars() -> dict[str, str]:
    """
    Charge un fichier `.env` minimal (KEY=VALUE), ignore lignes vides / commentaires `#`.
    Re-charge automatiquement si le fichier a changé (mtime).
    """
    p = _desktop_env_path()
    try:
        st = p.stat()
    except Exception:
        _DESKTOP_CFG_CACHE["mtime"] = None
        _DESKTOP_CFG_CACHE["vars"] = {}
        return {}

    mtime = getattr(st, "st_mtime", None)
    if mtime is not None and _DESKTOP_CFG_CACHE.get("mtime") == mtime:
        return _DESKTOP_CFG_CACHE.get("vars") or {}  # type: ignore[return-value]

    vars_out: dict[str, str] = {}
    try:
        raw = p.read_text(encoding="utf-8")
    except Exception:
        raw = ""
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k:
            vars_out[k] = v

    _DESKTOP_CFG_CACHE["mtime"] = mtime
    _DESKTOP_CFG_CACHE["vars"] = vars_out
    return vars_out


def _get_desktop_cfg(key: str) -> str:
    """
    Priorité :
    1) variables d’environnement process (set dans .cmd)
    2) fichier `desktop.env` (hot-reload)
    """
    v = os.environ.get(key)
    if v is not None:
        return v
    return _load_desktop_env_vars().get(key, "")


def get_dynamic_actions():
    importlib.reload(executor)
    actions = {}
    for name, obj in inspect.getmembers(executor):
        if inspect.isfunction(obj) and obj.__module__ == executor.__name__:
            actions[name] = obj
    return actions


@app.get("/capabilities")
async def get_capabilities():
    actions = get_dynamic_actions()
    return {"capabilities": list(actions.keys())}


def _split_csv(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def _truthy(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _desktop_dry_run(context: dict | None = None) -> bool:
    env = _get_desktop_cfg("LBG_DESKTOP_DRY_RUN").strip()
    if env:
        return _truthy(env)
    if isinstance(context, dict) and context.get("desktop_dry_run") is True:
        return True
    return False


def _desktop_requires_approval() -> bool:
    return bool(_get_desktop_cfg("LBG_DESKTOP_APPROVAL_TOKEN").strip())


def _desktop_approval_ok(context: dict | None = None) -> bool:
    token = _get_desktop_cfg("LBG_DESKTOP_APPROVAL_TOKEN").strip()
    if not token:
        return True
    if not isinstance(context, dict):
        return False
    got = context.get("desktop_approval")
    if not isinstance(got, str):
        return False
    return secrets.compare_digest(got, token)


def _url_allowlist() -> list[str]:
    raw = _get_desktop_cfg("LBG_DESKTOP_URL_ALLOWLIST").strip()
    if not raw:
        return []
    return _split_csv(raw)


def _url_host_allowlist() -> list[str]:
    raw = _get_desktop_cfg("LBG_DESKTOP_URL_HOST_ALLOWLIST").strip()
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
    raw = _get_desktop_cfg("LBG_DESKTOP_FILE_ALLOWLIST_DIRS").strip()
    if not raw:
        return []
    out = []
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


def _audit_write(line: dict) -> None:
    line = dict(line)
    line["ts"] = datetime.now(timezone.utc).isoformat()
    raw = json.dumps(line, ensure_ascii=False)
    if _truthy(_get_desktop_cfg("LBG_DESKTOP_AUDIT_STDOUT") or "1"):
        print(raw)
    path = _get_desktop_cfg("LBG_DESKTOP_AUDIT_LOG_PATH").strip()
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


def _editor_choice() -> str:
    raw = (_get_desktop_cfg("LBG_DESKTOP_EDITOR") or "").strip().lower()
    if raw in {"notepad", "notepad++", "word", "default"}:
        return raw
    return "notepad"


def _editor_cmd_for(choice: str) -> list[str] | None:
    if choice == "notepad":
        return ["notepad.exe"]
    if choice == "notepad++":
        p = (_get_desktop_cfg("LBG_DESKTOP_NOTEPADPP_PATH") or "").strip()
        return [p] if p else ["notepad++.exe"]
    if choice == "word":
        p = (_get_desktop_cfg("LBG_DESKTOP_WORD_PATH") or "").strip()
        return [p] if p else ["winword.exe"]
    return None


def _open_file_in_editor(path: Path) -> None:
    if os.name != "nt":
        return
    choice = _editor_choice()
    cmd = _editor_cmd_for(choice)
    try:
        if cmd is None or choice == "default":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.Popen([*cmd, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
        except Exception:
            return


def _desktop_env_set_key(text: str, key: str, value: str) -> str:
    """
    Remplace ou ajoute une ligne `KEY=...` (sans guillemets) dans un fichier `.env`.
    Conserve commentaires et ordre autant que possible.
    """
    lines = text.splitlines()
    out = []
    found = False
    for ln in lines:
        if ln.strip().startswith(key + "="):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(ln)
    if not found:
        if out and out[-1].strip() != "":
            out.append("")
        out.append(f"{key}={value}")
    return "\n".join(out) + ("\n" if not text.endswith("\n") else "")


def _desktop_env_learn_enabled() -> bool:
    return _truthy((_get_desktop_cfg("LBG_DESKTOP_LEARN_ENABLED") or "").strip() or "0")


def _desktop_env_learn_allowlist() -> list[str]:
    raw = (_get_desktop_cfg("LBG_DESKTOP_LEARN_APP_ALLOWLIST") or "").strip()
    return _split_csv(raw) if raw else []


def _persist_learned_app_mapping(app_id: str, exe_path: str) -> tuple[bool, str | None]:
    """
    Ajoute/merge app_id dans allowlist + mapping JSON dans `desktop.env`.
    """
    p = _desktop_env_path()
    try:
        current = p.read_text(encoding="utf-8") if p.exists() else ""
    except Exception as e:
        return (False, f"read_env_failed: {e}")

    # merge allowlist
    allow = _split_csv((_get_desktop_cfg("LBG_DESKTOP_APP_ALLOWLIST") or "").strip())
    if app_id not in allow:
        allow.append(app_id)

    # merge mapping
    map_raw = (_get_desktop_cfg("LBG_DESKTOP_APP_MAP_JSON") or "").strip()
    try:
        mapping = json.loads(map_raw) if map_raw else {}
        if not isinstance(mapping, dict):
            mapping = {}
    except Exception:
        mapping = {}
    mapping[app_id] = [exe_path]

    new_text = current
    new_text = _desktop_env_set_key(new_text, "LBG_DESKTOP_APP_ALLOWLIST", ",".join(allow))
    new_text = _desktop_env_set_key(new_text, "LBG_DESKTOP_APP_MAP_JSON", json.dumps(mapping, ensure_ascii=False))

    try:
        p.write_text(new_text, encoding="utf-8")
        # invalider cache (hot-reload)
        _DESKTOP_CFG_CACHE["mtime"] = None
        _DESKTOP_CFG_CACHE["vars"] = {}
        return (True, None)
    except Exception as e:
        return (False, f"write_env_failed: {e}")


class InvokeRequest(BaseModel):
    actor_id: str
    text: str = Field(default="")
    context: dict = Field(default_factory=dict)


@app.get("/healthz")
async def healthz():
    allow_urls = _url_allowlist()
    allow_hosts = _url_host_allowlist()
    allow_dirs = _file_allowlist_dirs()
    return {
        "status": "ok",
        "service": "agent_ia_windows",
        "version": "0.1.0",
        "desktop": {
            "dry_run_env": _get_desktop_cfg("LBG_DESKTOP_DRY_RUN").strip() or None,
            "url_allowlist_count": len(allow_urls),
            "url_allowlist_preview": allow_urls[:5],
            "url_host_allowlist_count": len(allow_hosts),
            "url_host_allowlist_preview": allow_hosts[:5],
            "file_allowlist_dirs_count": len(allow_dirs),
            "file_allowlist_dirs_preview": [str(p) for p in allow_dirs[:5]],
            "approval_gate_active": bool(_get_desktop_cfg("LBG_DESKTOP_APPROVAL_TOKEN").strip()),
            "audit_log_path_set": bool(_get_desktop_cfg("LBG_DESKTOP_AUDIT_LOG_PATH").strip()),
            "env_file": str(_desktop_env_path()),
            "editor": _editor_choice(),
        },
    }


@app.post("/invoke")
async def invoke(payload: InvokeRequest):
    ctx = payload.context if isinstance(payload.context, dict) else {}
    action = ctx.get("desktop_action")
    trace_id = ctx.get("_trace_id") if isinstance(ctx.get("_trace_id"), str) else None
    dry_run = _desktop_dry_run(ctx)

    base = {
        "agent": "agent_ia_windows",
        "handler": "desktop",
        "actor_id": payload.actor_id,
        "request_text": payload.text,
        "meta": {"dry_run": dry_run, "execution_gated": _desktop_requires_approval()},
    }
    if not isinstance(action, dict):
        out = {**base, "ok": False, "outcome": "bad_request", "error": "Aucune desktop_action dans context."}
        _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
        return out

    kind = str(action.get("kind") or "").strip()
    if kind == "open_url":
        url = action.get("url")
        if not isinstance(url, str) or not url.strip():
            out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `url` requis"}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out
        url = url.strip()
        if not _url_is_allowed(url):
            allow_urls = _url_allowlist()
            allow_hosts = _url_host_allowlist()
            out = {
                **base,
                "ok": False,
                "outcome": "allowlist_denied",
                "error": "URL non autorisée",
                "url": url,
                "url_allowlist_count": len(allow_urls),
                "url_allowlist_preview": allow_urls[:5],
                "url_host_allowlist_count": len(allow_hosts),
                "url_host_allowlist_preview": allow_hosts[:5],
                "hint": "Définir LBG_DESKTOP_URL_ALLOWLIST (URLs exactes) ou LBG_DESKTOP_URL_HOST_ALLOWLIST (domaines/hosts) puis relancer l’agent.",
            }
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out
        if not dry_run and _desktop_requires_approval() and not _desktop_approval_ok(ctx):
            out = {**base, "ok": False, "outcome": "approval_denied", "error": "Approval token requis", "url": url}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out
        if dry_run:
            out = {**base, "ok": True, "outcome": "dry_run", "url": url}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out
        try:
            import webbrowser

            ok = bool(webbrowser.open(url, new=2))
            out = {**base, "ok": ok, "outcome": "ok" if ok else "error", "url": url}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out
        except Exception as e:
            out = {**base, "ok": False, "outcome": "error", "error": str(e), "url": url}
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
            out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `text` requis"}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out
        path = path.strip()
        if not _path_is_allowed(path):
            allow_dirs = _file_allowlist_dirs()
            out = {
                **base,
                "ok": False,
                "outcome": "allowlist_denied",
                "error": "Chemin non autorisé",
                "path": path,
                "file_allowlist_dirs_count": len(allow_dirs),
                "file_allowlist_dirs_preview": [str(p) for p in allow_dirs[:5]],
                "hint": "Définir LBG_DESKTOP_FILE_ALLOWLIST_DIRS (répertoires parents, virgules) puis relancer l’agent.",
            }
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out
        if not dry_run and _desktop_requires_approval() and not _desktop_approval_ok(ctx):
            out = {**base, "ok": False, "outcome": "approval_denied", "error": "Approval token requis", "path": path}
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
            _open_file_in_editor(p)
            out = {**base, "ok": True, "outcome": "ok", "path": str(p), "bytes": len(content.encode("utf-8"))}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out
        except Exception as e:
            out = {**base, "ok": False, "outcome": "error", "error": str(e), "path": path}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out

    if kind == "open_app":
        """
        Lance une application allowlistée (générique).

        Champs:
        - app: string (id logique)
        - args: list[string] (optionnel)

        Config:
        - LBG_DESKTOP_APP_ALLOWLIST : ids autorisés (CSV)
        - LBG_DESKTOP_APP_MAP_JSON : mapping JSON id->commande (string ou liste)
          Ex: {"notepadpp":["notepad++.exe"],"word":["winword.exe"]}
        """
        app_id = action.get("app")
        args = action.get("args")
        want_learn = action.get("learn") is True
        if not isinstance(app_id, str) or not app_id.strip():
            out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `app` requis"}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out
        app_id = app_id.strip()
        allow_raw = _get_desktop_cfg("LBG_DESKTOP_APP_ALLOWLIST").strip()
        allow = _split_csv(allow_raw) if allow_raw else []

        # Apprentissage contrôlé : on peut autoriser une app inconnue via une allowlist dédiée,
        # sans l'ajouter à la liste d'exécution "normale" à l'avance.
        learn_allow = _desktop_env_learn_allowlist()
        learn_can_bypass = want_learn and _desktop_env_learn_enabled() and (not learn_allow or app_id in learn_allow)

        if app_id not in allow and not learn_can_bypass:
            out = {
                **base,
                "ok": False,
                "outcome": "allowlist_denied",
                "error": "Application non autorisée",
                "app": app_id,
                "app_allowlist_count": len(allow),
                "app_allowlist_preview": allow[:10],
                "hint": "Ajouter l'app à LBG_DESKTOP_APP_ALLOWLIST + LBG_DESKTOP_APP_MAP_JSON, ou activer learn (LBG_DESKTOP_LEARN_ENABLED=1 + LBG_DESKTOP_LEARN_APP_ALLOWLIST) et envoyer learn:true.",
            }
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out

        if args is None:
            args_list: list[str] = []
        elif isinstance(args, list) and all(isinstance(x, str) for x in args):
            args_list = [x for x in args if x.strip()]
        else:
            out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `args` doit être list[string]"}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out

        if not dry_run and _desktop_requires_approval() and not _desktop_approval_ok(ctx):
            out = {**base, "ok": False, "outcome": "approval_denied", "error": "Approval token requis", "app": app_id}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out
        if dry_run:
            out = {**base, "ok": True, "outcome": "dry_run", "app": app_id, "args": args_list}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out

        map_raw = _get_desktop_cfg("LBG_DESKTOP_APP_MAP_JSON").strip()
        try:
            mapping = json.loads(map_raw) if map_raw else {}
        except Exception:
            mapping = {}
        cmd = mapping.get(app_id) if isinstance(mapping, dict) else None

        cmd_list: list[str] | None = None
        if isinstance(cmd, str) and cmd.strip():
            cmd_list = [cmd.strip()]
        elif isinstance(cmd, list) and all(isinstance(x, str) for x in cmd) and cmd:
            cmd_list = [x.strip() for x in cmd if x.strip()]
        else:
            # fallback: essayer l'id comme exécutable
            cmd_list = [app_id]

        try:
            subprocess.Popen([*cmd_list, *args_list], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            out = {**base, "ok": True, "outcome": "ok", "app": app_id, "args": args_list}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out
        except Exception as e:
            # Apprentissage contrôlé : tenter de résoudre l’exe et persister dans desktop.env
            if (
                want_learn
                and os.name == "nt"
                and not dry_run
                and _desktop_env_learn_enabled()
                and (not learn_allow or app_id in learn_allow)
                and (not _desktop_requires_approval() or _desktop_approval_ok(ctx))
            ):
                try:
                    resolved = resolve_program(app_id)
                except Exception:
                    resolved = None
                if isinstance(resolved, str) and resolved.strip():
                    okp, errp = _persist_learned_app_mapping(app_id, resolved.strip())
                    if okp:
                        try:
                            subprocess.Popen([resolved.strip(), *args_list], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            out = {
                                **base,
                                "ok": True,
                                "outcome": "ok",
                                "app": app_id,
                                "args": args_list,
                                "learned": True,
                                "learned_path": resolved.strip(),
                            }
                            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
                            return out
                        except Exception as e2:
                            out = {
                                **base,
                                "ok": False,
                                "outcome": "error",
                                "error": str(e2),
                                "app": app_id,
                                "args": args_list,
                                "learned": True,
                                "learned_path": resolved.strip(),
                            }
                            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
                            return out
                    else:
                        out = {
                            **base,
                            "ok": False,
                            "outcome": "error",
                            "error": f"{e} | learn_persist_failed: {errp}",
                            "app": app_id,
                            "args": args_list,
                            "learned": False,
                        }
                        _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
                        return out

            out = {**base, "ok": False, "outcome": "error", "error": str(e), "app": app_id, "args": args_list}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out

    out = {**base, "ok": False, "outcome": "unknown_kind", "error": "Action desktop inconnue", "kind": kind}
    _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
    return out


@app.post("/execute")
async def execute_action(request: ActionRequest):
    actions = get_dynamic_actions()
    action = request.action
    params = request.parameters or {}

    if action.startswith("ouvrir_"):
        program_name = action.replace("ouvrir_", "").strip()

        logger.info(f"[AUTO] Tentative d'ouverture automatique : {program_name}")

        path_in_action = re.search(r"[A-Za-z]:\\\\[^ ]+", action)
        if path_in_action:
            detected_path = path_in_action.group(0)
            logger.info(f"[AUTO] Chemin détecté dans action : {detected_path}")
            try:
                subprocess.Popen([detected_path])
                return {
                    "status": "success",
                    "result": {"status": "ok", "message": "Programme lancé via chemin détecté dans action.", "path": detected_path},
                }
            except Exception as e:
                return {"status": "success", "result": {"status": "error", "message": str(e)}}

        if "path" in params:
            explicit_path = params["path"]
            logger.info(f"[AUTO] Chemin explicite fourni : {explicit_path}")
            try:
                subprocess.Popen([explicit_path])
                return {
                    "status": "success",
                    "result": {"status": "ok", "message": "Programme lancé via chemin explicite.", "path": explicit_path},
                }
            except Exception as e:
                return {"status": "success", "result": {"status": "error", "message": str(e)}}

        resolved = resolve_program(program_name)

        if resolved:
            logger.info(f"[AUTO] Programme détecté automatiquement : {program_name} -> {resolved}")
            try:
                subprocess.Popen([resolved])
                return {
                    "status": "success",
                    "result": {"status": "ok", "message": f"Programme '{program_name}' lancé automatiquement.", "path": resolved},
                }
            except Exception as e:
                return {"status": "success", "result": {"status": "error", "message": str(e)}}

        logger.warning(f"[AUTO] Aucun programme trouvé pour '{program_name}', fallback capability.")

    if action not in actions:
        logger.error(f"Action demandée inconnue : {action}")
        raise HTTPException(status_code=404, detail=f"Action '{action}' non trouvée. Disponibles: {list(actions.keys())}")

    try:
        logger.info(f"Exécution de : {action} avec {params}")
        result = actions[action](**params)
        return {"status": "success", "result": result}
    except Exception as e:
        logger.error(f"Erreur d'exécution : {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/install")
async def install_capability(request: InstallRequest):
    try:
        capability_name = request.action.strip()

        with open("executor.py", "r", encoding="utf-8") as f:
            content = f.read()

        if f"def {capability_name}" in content:
            return {"status": "exists", "message": f"La capability '{capability_name}' existe déjà."}

        with open("executor.py", "a", encoding="utf-8") as f:
            f.write("\n\n# --- Capability auto-installée ---\n")
            if request.description:
                f.write(f"# Description : {request.description}\n")
            f.write(request.code)
            f.write("\n")

        actions = get_dynamic_actions()

        logger.info(f"Capability '{capability_name}' installée. Total : {len(actions)}")
        return {"status": "installed", "current_capabilities": list(actions.keys())}

    except Exception as e:
        logger.error(f"Erreur d'installation : {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

