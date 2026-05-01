import importlib
import inspect
import logging
import subprocess
import re
import json
import os
import secrets
import sys
import base64
import uuid
import urllib.request
import urllib.error
from urllib.parse import urlencode
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


def _bounded_int(x: object, *, lo: int, hi: int) -> int | None:
    try:
        v = int(x)  # type: ignore[arg-type]
    except Exception:
        return None
    if v < lo or v > hi:
        return None
    return v


def _bounded_float(x: object, *, lo: float, hi: float) -> float | None:
    try:
        v = float(x)  # type: ignore[arg-type]
    except Exception:
        return None
    if v < lo or v > hi:
        return None
    return v


def _computer_use_enabled() -> bool:
    return _truthy((_get_desktop_cfg("LBG_DESKTOP_COMPUTER_USE_ENABLED") or "").strip() or "0")


def _observe_requires_approval() -> bool:
    raw = (_get_desktop_cfg("LBG_DESKTOP_OBSERVE_REQUIRES_APPROVAL") or "").strip()
    if raw:
        return _truthy(raw)
    return _desktop_requires_approval()


def _screenshot_dir() -> Path:
    raw = (_get_desktop_cfg("LBG_DESKTOP_SCREENSHOT_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path("screenshots")


def _screenshot_return_mode() -> str:
    raw = (_get_desktop_cfg("LBG_DESKTOP_SCREENSHOT_RETURN") or "").strip().lower()
    if raw in {"path", "base64", "none"}:
        return raw
    return "path"


def _screenshot_max_width() -> int:
    raw = (_get_desktop_cfg("LBG_DESKTOP_SCREENSHOT_MAX_WIDTH") or "").strip()
    v = _bounded_int(raw, lo=64, hi=4096) if raw else None
    return v or 1280


def _screenshot_quality() -> int:
    raw = (_get_desktop_cfg("LBG_DESKTOP_SCREENSHOT_JPEG_QUALITY") or "").strip()
    v = _bounded_int(raw, lo=10, hi=95) if raw else None
    return v or 65


def _screenshot_format() -> str:
    raw = (_get_desktop_cfg("LBG_DESKTOP_SCREENSHOT_FORMAT") or "").strip().lower()
    if raw in {"png", "jpeg", "jpg"}:
        return "jpeg" if raw == "jpg" else raw
    return "jpeg"


def _capture_screenshot(*, region: dict | None = None) -> tuple[bytes, str]:
    """
    Capture un screenshot. Retourne (bytes, mime).
    Préfère `mss` si dispo, sinon fallback PIL.ImageGrab.
    """
    fmt = _screenshot_format()
    mime = "image/png" if fmt == "png" else "image/jpeg"

    left = top = width = height = None
    if isinstance(region, dict):
        left = _bounded_int(region.get("x"), lo=0, hi=100000)
        top = _bounded_int(region.get("y"), lo=0, hi=100000)
        width = _bounded_int(region.get("w"), lo=1, hi=100000)
        height = _bounded_int(region.get("h"), lo=1, hi=100000)

    img = None

    try:
        import mss  # type: ignore[import-not-found]
        import mss.tools  # type: ignore[import-not-found]

        with mss.mss() as sct:
            if left is not None and top is not None and width is not None and height is not None:
                mon = {"left": left, "top": top, "width": width, "height": height}
            else:
                mon = sct.monitors[0]
            shot = sct.grab(mon)
            raw = mss.tools.to_png(shot.rgb, shot.size)
            from PIL import Image  # type: ignore[import-not-found]
            import io

            img = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        img = None

    if img is None:
        try:
            from PIL import ImageGrab  # type: ignore[import-not-found]

            bbox = None
            if left is not None and top is not None and width is not None and height is not None:
                bbox = (left, top, left + width, top + height)
            grabbed = ImageGrab.grab(bbox=bbox, all_screens=True)
            img = grabbed.convert("RGB")
        except Exception as e:
            raise RuntimeError(f"Screenshot capture failed: {type(e).__name__}: {e}")

    try:
        from PIL import Image  # type: ignore[import-not-found]
        import io

        max_w = _screenshot_max_width()
        if img.width > max_w:
            ratio = max_w / float(img.width)
            new_h = max(1, int(img.height * ratio))
            img = img.resize((max_w, new_h), resample=Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        if fmt == "png":
            img.save(buf, format="PNG", optimize=True)
        else:
            img.save(buf, format="JPEG", quality=_screenshot_quality(), optimize=True)
        return (buf.getvalue(), mime)
    except Exception as e:
        raise RuntimeError(f"Screenshot encode failed: {type(e).__name__}: {e}")


def _pyautogui_safe_import():
    import pyautogui  # type: ignore[import-not-found]

    pyautogui.FAILSAFE = False
    return pyautogui


def _desktop_comfyui_enabled() -> bool:
    return _truthy((_get_desktop_cfg("LBG_DESKTOP_COMFYUI_ENABLED") or "").strip() or "0")


def _desktop_comfyui_base_url() -> str:
    raw = (_get_desktop_cfg("LBG_COMFYUI_BASE_URL") or "").strip()
    return raw or "http://127.0.0.1:8188"


def _comfyui_url(path: str) -> str:
    base = _desktop_comfyui_base_url().rstrip("/")
    p = (path or "").strip()
    if not p.startswith("/"):
        p = "/" + p
    return base + p


def _comfyui_http_json(method: str, path: str, payload: dict | None = None, timeout_s: float = 60.0) -> dict:
    url = _comfyui_url(path)
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
        data = raw
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read()
            if not body:
                return {"ok": True, "status_code": getattr(resp, "status", 200)}
            return json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = e.read()
            msg = body.decode("utf-8", errors="replace") if body else str(e)
        except Exception:
            msg = str(e)
        raise RuntimeError(f"ComfyUI HTTPError {e.code}: {msg}")
    except Exception as e:
        raise RuntimeError(f"ComfyUI request failed: {type(e).__name__}: {e}")


def _comfyui_http_bytes(path: str, query: dict, timeout_s: float = 60.0) -> tuple[bytes, str]:
    url = _comfyui_url(path)
    qs = urlencode({k: v for k, v in query.items() if v is not None})
    url2 = url + ("?" + qs if qs else "")
    req = urllib.request.Request(url2, headers={"Accept": "*/*"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read()
            ctype = resp.headers.get("Content-Type") or "application/octet-stream"
            return body, ctype
    except urllib.error.HTTPError as e:
        try:
            body = e.read()
            msg = body.decode("utf-8", errors="replace") if body else str(e)
        except Exception:
            msg = str(e)
        raise RuntimeError(f"ComfyUI HTTPError {e.code}: {msg}")
    except Exception as e:
        raise RuntimeError(f"ComfyUI request failed: {type(e).__name__}: {e}")


def _workflow_apply_ops(workflow: dict, ops: list[dict]) -> dict:
    """
    Patches minimalistes sur un workflow "API export" ComfyUI (dict id->node).
    Ops supportées :
    - set_input: {op:"set_input", node:"205", key:"seed", value:123}
    - set_inputs: {op:"set_inputs", node:"205", values:{...}}
    """
    if not isinstance(workflow, dict):
        raise ValueError("workflow doit être un objet")
    out = json.loads(json.dumps(workflow))  # deep copy JSON-safe
    for op in ops:
        if not isinstance(op, dict):
            raise ValueError("op doit être un objet")
        kind = str(op.get("op") or "").strip()
        node_id = str(op.get("node") or "").strip()
        if not kind or not node_id:
            raise ValueError("op.op et op.node requis")
        node = out.get(node_id)
        if not isinstance(node, dict):
            raise ValueError(f"node introuvable: {node_id}")
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            inputs = {}
            node["inputs"] = inputs

        if kind == "set_input":
            key = op.get("key")
            if not isinstance(key, str) or not key.strip():
                raise ValueError("set_input.key requis")
            inputs[key] = op.get("value")
            continue

        if kind == "set_inputs":
            values = op.get("values")
            if not isinstance(values, dict):
                raise ValueError("set_inputs.values requis (objet)")
            for k, v in values.items():
                if isinstance(k, str) and k.strip():
                    inputs[k] = v
            continue

        raise ValueError(f"op non supportée: {kind}")
    return out


def _handle_computer_use_action(
    *,
    kind: str,
    action: dict,
    ctx: dict,
    base: dict,
    trace_id: str | None,
    dry_run: bool,
    audit_event: str = "agents.desktop.audit",
    step_index: int | None = None,
) -> dict:
    def _audit(out: dict) -> None:
        line = {"event": audit_event, "trace_id": trace_id, **out}
        if step_index is not None:
            line["step_index"] = step_index
        _audit_write(line)

    if not _computer_use_enabled():
        out = {
            **base,
            "ok": False,
            "outcome": "feature_disabled",
            "error": "Computer Use désactivé (LBG_DESKTOP_COMPUTER_USE_ENABLED=0).",
            "kind": kind,
        }
        _audit(out)
        return out

    if kind == "observe_screen" and _observe_requires_approval() and not _desktop_approval_ok(ctx):
        out = {
            **base,
            "ok": False,
            "outcome": "approval_denied",
            "error": "Approval token requis pour observe_screen (context.desktop_approval).",
            "kind": kind,
        }
        _audit(out)
        return out

    if kind != "observe_screen" and not dry_run and _desktop_requires_approval() and not _desktop_approval_ok(ctx):
        out = {**base, "ok": False, "outcome": "approval_denied", "error": "Approval token requis", "kind": kind}
        _audit(out)
        return out

    if kind == "wait_ms":
        ms = _bounded_int(action.get("ms"), lo=0, hi=60_000)
        if ms is None:
            out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `ms` requis (0..60000)", "kind": kind}
            _audit(out)
            return out
        if dry_run:
            out = {**base, "ok": True, "outcome": "dry_run", "kind": kind, "ms": ms}
            _audit(out)
            return out
        try:
            import time

            time.sleep(ms / 1000.0)
            out = {**base, "ok": True, "outcome": "ok", "kind": kind, "ms": ms}
            _audit(out)
            return out
        except Exception as e:
            out = {**base, "ok": False, "outcome": "error", "error": str(e), "kind": kind, "ms": ms}
            _audit(out)
            return out

    if kind == "observe_screen":
        region = action.get("region") if isinstance(action.get("region"), dict) else None
        if dry_run:
            out = {**base, "ok": True, "outcome": "dry_run", "kind": kind, "region": region}
            _audit(out)
            return out
        try:
            data, mime = _capture_screenshot(region=region)
            mode = _screenshot_return_mode()
            out = {**base, "ok": True, "outcome": "ok", "kind": kind, "mime": mime, "bytes": len(data), "return": mode}

            if mode == "none":
                _audit(out)
                return out

            sdir = _screenshot_dir()
            sdir.mkdir(parents=True, exist_ok=True)
            ext = "png" if mime == "image/png" else "jpg"
            fn = f"shot_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}.{ext}"
            p = (sdir / fn)
            p.write_bytes(data)
            out["path"] = str(p)

            if mode == "base64":
                out["base64"] = base64.b64encode(data).decode("ascii")

            _audit(out)
            return out
        except Exception as e:
            out = {**base, "ok": False, "outcome": "error", "error": str(e), "kind": kind}
            _audit(out)
            return out

    try:
        pag = None if dry_run else _pyautogui_safe_import()
    except Exception as e:
        out = {
            **base,
            "ok": False,
            "outcome": "missing_dependency",
            "error": f"pyautogui indisponible: {type(e).__name__}: {e}",
            "kind": kind,
        }
        _audit(out)
        return out

    def _screen_size() -> tuple[int, int]:
        if pag is None:
            return (10_000, 10_000)
        w, h = pag.size()
        return (int(w), int(h))

    sw, sh = _screen_size()

    if kind in {"click_xy", "move_xy"}:
        x = _bounded_int(action.get("x"), lo=0, hi=max(0, sw - 1))
        y = _bounded_int(action.get("y"), lo=0, hi=max(0, sh - 1))
        if x is None or y is None:
            out = {**base, "ok": False, "outcome": "bad_request", "error": "Champs `x`,`y` requis (dans l’écran)", "kind": kind}
            _audit(out)
            return out
        duration = _bounded_float(action.get("duration_s"), lo=0.0, hi=10.0) or 0.0
        if kind == "move_xy":
            if dry_run:
                out = {**base, "ok": True, "outcome": "dry_run", "kind": kind, "x": x, "y": y, "duration_s": duration}
                _audit(out)
                return out
            try:
                pag.moveTo(x, y, duration=duration)
                out = {**base, "ok": True, "outcome": "ok", "kind": kind, "x": x, "y": y, "duration_s": duration}
                _audit(out)
                return out
            except Exception as e:
                out = {**base, "ok": False, "outcome": "error", "error": str(e), "kind": kind, "x": x, "y": y}
                _audit(out)
                return out

        button = str(action.get("button") or "left").strip().lower()
        if button not in {"left", "right", "middle"}:
            out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `button` invalide (left|right|middle)", "kind": kind}
            _audit(out)
            return out
        clicks = _bounded_int(action.get("clicks"), lo=1, hi=10) or 1
        interval = _bounded_float(action.get("interval_s"), lo=0.0, hi=2.0) or 0.0
        if dry_run:
            out = {
                **base,
                "ok": True,
                "outcome": "dry_run",
                "kind": kind,
                "x": x,
                "y": y,
                "button": button,
                "clicks": clicks,
                "interval_s": interval,
            }
            _audit(out)
            return out
        try:
            pag.click(x=x, y=y, button=button, clicks=clicks, interval=interval)
            out = {**base, "ok": True, "outcome": "ok", "kind": kind, "x": x, "y": y, "button": button, "clicks": clicks}
            _audit(out)
            return out
        except Exception as e:
            out = {**base, "ok": False, "outcome": "error", "error": str(e), "kind": kind, "x": x, "y": y, "button": button}
            _audit(out)
            return out

    if kind == "drag_xy":
        x1 = _bounded_int(action.get("x1"), lo=0, hi=max(0, sw - 1))
        y1 = _bounded_int(action.get("y1"), lo=0, hi=max(0, sh - 1))
        x2 = _bounded_int(action.get("x2"), lo=0, hi=max(0, sw - 1))
        y2 = _bounded_int(action.get("y2"), lo=0, hi=max(0, sh - 1))
        if None in {x1, y1, x2, y2}:
            out = {**base, "ok": False, "outcome": "bad_request", "error": "Champs `x1`,`y1`,`x2`,`y2` requis (dans l’écran)", "kind": kind}
            _audit(out)
            return out
        duration = _bounded_float(action.get("duration_s"), lo=0.0, hi=10.0) or 0.2
        button = str(action.get("button") or "left").strip().lower()
        if button not in {"left", "right", "middle"}:
            out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `button` invalide (left|right|middle)", "kind": kind}
            _audit(out)
            return out
        if dry_run:
            out = {
                **base,
                "ok": True,
                "outcome": "dry_run",
                "kind": kind,
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "duration_s": duration,
                "button": button,
            }
            _audit(out)
            return out
        try:
            pag.moveTo(x1, y1, duration=0.0)
            pag.dragTo(x2, y2, duration=duration, button=button)
            out = {**base, "ok": True, "outcome": "ok", "kind": kind, "x1": x1, "y1": y1, "x2": x2, "y2": y2, "button": button}
            _audit(out)
            return out
        except Exception as e:
            out = {**base, "ok": False, "outcome": "error", "error": str(e), "kind": kind}
            _audit(out)
            return out

    if kind == "type_text":
        txt = action.get("text")
        if not isinstance(txt, str):
            out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `text` requis (string)", "kind": kind}
            _audit(out)
            return out
        max_len = _bounded_int((_get_desktop_cfg("LBG_DESKTOP_TYPE_MAX_CHARS") or "").strip() or "400", lo=1, hi=10_000) or 400
        if len(txt) > max_len:
            out = {**base, "ok": False, "outcome": "limit_exceeded", "error": f"text trop long (max {max_len})", "kind": kind, "chars": len(txt)}
            _audit(out)
            return out
        interval = _bounded_float(action.get("interval_s"), lo=0.0, hi=1.0) or 0.02
        if dry_run:
            out = {**base, "ok": True, "outcome": "dry_run", "kind": kind, "chars": len(txt), "interval_s": interval}
            _audit(out)
            return out
        try:
            pag.typewrite(txt, interval=interval)
            out = {**base, "ok": True, "outcome": "ok", "kind": kind, "chars": len(txt)}
            _audit(out)
            return out
        except Exception as e:
            out = {**base, "ok": False, "outcome": "error", "error": str(e), "kind": kind}
            _audit(out)
            return out

    if kind == "hotkey":
        keys = action.get("keys")
        if not (isinstance(keys, list) and all(isinstance(k, str) and k.strip() for k in keys)):
            out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `keys` requis (list[string])", "kind": kind}
            _audit(out)
            return out
        keys2 = [k.strip().lower() for k in keys][:6]
        if dry_run:
            out = {**base, "ok": True, "outcome": "dry_run", "kind": kind, "keys": keys2}
            _audit(out)
            return out
        try:
            pag.hotkey(*keys2)
            out = {**base, "ok": True, "outcome": "ok", "kind": kind, "keys": keys2}
            _audit(out)
            return out
        except Exception as e:
            out = {**base, "ok": False, "outcome": "error", "error": str(e), "kind": kind, "keys": keys2}
            _audit(out)
            return out

    if kind == "scroll":
        clicks = _bounded_int(action.get("clicks"), lo=-2000, hi=2000)
        if clicks is None:
            out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `clicks` requis (-2000..2000)", "kind": kind}
            _audit(out)
            return out
        if dry_run:
            out = {**base, "ok": True, "outcome": "dry_run", "kind": kind, "clicks": clicks}
            _audit(out)
            return out
        try:
            pag.scroll(clicks)
            out = {**base, "ok": True, "outcome": "ok", "kind": kind, "clicks": clicks}
            _audit(out)
            return out
        except Exception as e:
            out = {**base, "ok": False, "outcome": "error", "error": str(e), "kind": kind, "clicks": clicks}
            _audit(out)
            return out

    out = {**base, "ok": False, "outcome": "unknown_kind", "error": "Action computer_use inconnue", "kind": kind}
    _audit(out)
    return out


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

    def _importable(mod: str) -> bool:
        try:
            __import__(mod)
            return True
        except Exception:
            return False

    def _file_sha256(path: str) -> str | None:
        try:
            import hashlib

            b = Path(path).read_bytes()
            return hashlib.sha256(b).hexdigest()
        except Exception:
            return None

    return {
        "status": "ok",
        "service": "agent_ia_windows",
        "version": "0.1.0",
        "python": {"executable": sys.executable, "version": sys.version},
        "code": {
            "main_file": __file__,
            "main_sha256": _file_sha256(__file__),
        },
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
        "computer_use": {
            "enabled_env": _get_desktop_cfg("LBG_DESKTOP_COMPUTER_USE_ENABLED").strip() or None,
            "observe_requires_approval_env": _get_desktop_cfg("LBG_DESKTOP_OBSERVE_REQUIRES_APPROVAL").strip() or None,
            "pyautogui_importable": _importable("pyautogui"),
            "mss_importable": _importable("mss"),
            "pillow_importable": _importable("PIL"),
        },
        "comfyui": {
            "enabled_env": _get_desktop_cfg("LBG_DESKTOP_COMFYUI_ENABLED").strip() or None,
            "base_url": _desktop_comfyui_base_url(),
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

    if kind in {"comfyui_queue", "comfyui_history", "comfyui_view", "comfyui_patch_and_queue"}:
        # Sécurité : feature flag + approval requis (actions réelles / données locales)
        if not _desktop_comfyui_enabled():
            out = {
                **base,
                "ok": False,
                "outcome": "feature_disabled",
                "error": "ComfyUI désactivé (LBG_DESKTOP_COMFYUI_ENABLED=0).",
                "kind": kind,
            }
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out

        if not _desktop_approval_ok(ctx):
            out = {
                **base,
                "ok": False,
                "outcome": "approval_denied",
                "error": "Approval token requis (context.desktop_approval).",
                "kind": kind,
            }
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out

        base_url = _desktop_comfyui_base_url()
        timeout_s = _bounded_float((_get_desktop_cfg("LBG_COMFYUI_TIMEOUT_S") or "").strip() or "120", lo=1.0, hi=600.0) or 120.0

        if kind == "comfyui_queue":
            workflow = action.get("workflow")
            client_id = action.get("client_id")
            if not isinstance(workflow, dict):
                out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `workflow` requis (objet JSON)", "kind": kind}
                _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
                return out
            if client_id is not None and not isinstance(client_id, str):
                out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `client_id` doit être string", "kind": kind}
                _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
                return out

            if dry_run:
                out = {**base, "ok": True, "outcome": "dry_run", "kind": kind, "comfyui_base_url": base_url}
                _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
                return out

            try:
                payload2 = {"prompt": workflow}
                if isinstance(client_id, str) and client_id.strip():
                    payload2["client_id"] = client_id.strip()
                resp = _comfyui_http_json("POST", "/prompt", payload2, timeout_s=timeout_s)
                out = {**base, "ok": True, "outcome": "ok", "kind": kind, "comfyui_base_url": base_url, "remote": resp}
                _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
                return out
            except Exception as e:
                out = {**base, "ok": False, "outcome": "error", "kind": kind, "error": str(e), "comfyui_base_url": base_url}
                _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
                return out

        if kind == "comfyui_history":
            prompt_id = action.get("prompt_id")
            if not isinstance(prompt_id, str) or not prompt_id.strip():
                out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `prompt_id` requis", "kind": kind}
                _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
                return out
            if dry_run:
                out = {**base, "ok": True, "outcome": "dry_run", "kind": kind, "prompt_id": prompt_id.strip(), "comfyui_base_url": base_url}
                _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
                return out
            try:
                resp = _comfyui_http_json("GET", f"/history/{prompt_id.strip()}", None, timeout_s=timeout_s)
                out = {**base, "ok": True, "outcome": "ok", "kind": kind, "prompt_id": prompt_id.strip(), "comfyui_base_url": base_url, "remote": resp}
                _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
                return out
            except Exception as e:
                out = {**base, "ok": False, "outcome": "error", "kind": kind, "error": str(e), "prompt_id": prompt_id.strip(), "comfyui_base_url": base_url}
                _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
                return out

        if kind == "comfyui_view":
            # GET /view?filename=...&subfolder=...&type=output
            filename = action.get("filename")
            subfolder = action.get("subfolder")
            typ = action.get("type")
            if not isinstance(filename, str) or not filename.strip():
                out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `filename` requis", "kind": kind}
                _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
                return out
            if subfolder is not None and not isinstance(subfolder, str):
                out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `subfolder` doit être string", "kind": kind}
                _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
                return out
            if typ is not None and not isinstance(typ, str):
                out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `type` doit être string", "kind": kind}
                _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
                return out

            # Mode retour : path|base64|none
            ret = str(action.get("return") or "path").strip().lower()
            if ret not in {"path", "base64", "none"}:
                ret = "path"

            if dry_run:
                out = {**base, "ok": True, "outcome": "dry_run", "kind": kind, "filename": filename.strip(), "return": ret, "comfyui_base_url": base_url}
                _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
                return out

            try:
                body, ctype = _comfyui_http_bytes(
                    "/view",
                    {"filename": filename.strip(), "subfolder": (subfolder or "").strip() or None, "type": (typ or "output").strip()},
                    timeout_s=timeout_s,
                )
                out = {**base, "ok": True, "outcome": "ok", "kind": kind, "filename": filename.strip(), "return": ret, "content_type": ctype, "bytes": len(body)}

                if ret == "none":
                    _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
                    return out

                d = Path((_get_desktop_cfg("LBG_COMFYUI_DOWNLOAD_DIR") or "").strip() or "comfyui_downloads").expanduser()
                d.mkdir(parents=True, exist_ok=True)
                safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename.strip()).name)
                p = (d / safe_name)
                p.write_bytes(body)
                out["path"] = str(p)
                if ret == "base64":
                    out["base64"] = base64.b64encode(body).decode("ascii")
                _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
                return out
            except Exception as e:
                out = {**base, "ok": False, "outcome": "error", "kind": kind, "error": str(e), "filename": filename.strip(), "comfyui_base_url": base_url}
                _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
                return out

        # comfyui_patch_and_queue
        ops = action.get("ops")
        workflow = action.get("workflow")
        client_id = action.get("client_id")
        if not isinstance(workflow, dict):
            out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `workflow` requis (objet JSON)", "kind": kind}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out
        if not (isinstance(ops, list) and all(isinstance(x, dict) for x in ops)):
            out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `ops` requis (list[object])", "kind": kind}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out
        if client_id is not None and not isinstance(client_id, str):
            out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `client_id` doit être string", "kind": kind}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out

        try:
            patched = _workflow_apply_ops(workflow, ops)
        except Exception as e:
            out = {**base, "ok": False, "outcome": "bad_request", "kind": kind, "error": str(e)}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out

        if dry_run:
            out = {**base, "ok": True, "outcome": "dry_run", "kind": kind, "comfyui_base_url": base_url, "ops_count": len(ops)}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out

        try:
            payload2 = {"prompt": patched}
            if isinstance(client_id, str) and client_id.strip():
                payload2["client_id"] = client_id.strip()
            resp = _comfyui_http_json("POST", "/prompt", payload2, timeout_s=timeout_s)
            out = {**base, "ok": True, "outcome": "ok", "kind": kind, "comfyui_base_url": base_url, "ops_count": len(ops), "remote": resp}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out
        except Exception as e:
            out = {**base, "ok": False, "outcome": "error", "kind": kind, "error": str(e), "comfyui_base_url": base_url}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out

    if kind == "run_steps":
        steps = action.get("steps")
        if not (isinstance(steps, list) and all(isinstance(s, dict) for s in steps)):
            out = {**base, "ok": False, "outcome": "bad_request", "error": "Champ `steps` requis (list[object])", "kind": kind}
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out
        stop_on_fail = action.get("stop_on_fail")
        if stop_on_fail is None:
            stop_on_fail_bool = True
        elif isinstance(stop_on_fail, bool):
            stop_on_fail_bool = stop_on_fail
        else:
            out = {
                **base,
                "ok": False,
                "outcome": "bad_request",
                "error": "Champ `stop_on_fail` doit être un booléen",
                "kind": kind,
            }
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out

        max_steps = _bounded_int((_get_desktop_cfg("LBG_DESKTOP_RUN_STEPS_MAX") or "").strip() or "12", lo=1, hi=200) or 12
        timeout_ms = _bounded_int((_get_desktop_cfg("LBG_DESKTOP_RUN_STEPS_TIMEOUT_MS") or "").strip() or "30000", lo=100, hi=600_000) or 30000
        if len(steps) > max_steps:
            out = {
                **base,
                "ok": False,
                "outcome": "limit_exceeded",
                "error": f"trop d'étapes (max {max_steps})",
                "kind": kind,
                "steps": len(steps),
            }
            _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
            return out

        import time

        started = time.monotonic()
        results: list[dict] = []
        step_outputs: list[dict] = []
        errors: list[dict] = []

        for i, step in enumerate(steps):
            if (time.monotonic() - started) * 1000.0 > timeout_ms:
                results.append({"ok": False, "outcome": "timeout", "kind": "run_steps", "step_index": i})
                step_outputs.append({"ok": False, "outcome": "timeout", "kind": "run_steps", "step_index": i})
                errors.append({"step_index": i, "kind": "run_steps", "outcome": "timeout"})
                if stop_on_fail_bool:
                    break
                else:
                    continue

            step_kind = str(step.get("kind") or "").strip()
            if not step_kind:
                results.append({"ok": False, "outcome": "bad_request", "error": "step.kind requis", "step_index": i})
                step_outputs.append({"ok": False, "outcome": "bad_request", "error": "step.kind requis", "step_index": i})
                errors.append({"step_index": i, "kind": None, "outcome": "bad_request", "error": "step.kind requis"})
                if stop_on_fail_bool:
                    break
                else:
                    continue

            # Support minimal : `open_url` + primitives computer_use existantes
            if step_kind == "open_url":
                url = step.get("url")
                step_base = {**base, "kind": "open_url", "step_index": i}
                if not isinstance(url, str) or not url.strip():
                    out_step = {**step_base, "ok": False, "outcome": "bad_request", "error": "Champ `url` requis"}
                    _audit_write({"event": "agents.desktop.step", "trace_id": trace_id, **out_step})
                    results.append({"ok": False, "outcome": "bad_request", "kind": "open_url", "step_index": i})
                    step_outputs.append({k: v for k, v in out_step.items() if k not in {"event", "trace_id"}})
                    errors.append({"step_index": i, "kind": "open_url", "outcome": "bad_request", "error": "Champ `url` requis"})
                    if stop_on_fail_bool:
                        break
                    else:
                        continue
                url = url.strip()
                if not _url_is_allowed(url):
                    out_step = {**step_base, "ok": False, "outcome": "allowlist_denied", "error": "URL non autorisée", "url": url}
                    _audit_write({"event": "agents.desktop.step", "trace_id": trace_id, **out_step})
                    results.append({"ok": False, "outcome": "allowlist_denied", "kind": "open_url", "step_index": i})
                    step_outputs.append({k: v for k, v in out_step.items() if k not in {"event", "trace_id"}})
                    errors.append({"step_index": i, "kind": "open_url", "outcome": "allowlist_denied", "url": url})
                    if stop_on_fail_bool:
                        break
                    else:
                        continue
                if not dry_run and _desktop_requires_approval() and not _desktop_approval_ok(ctx):
                    out_step = {**step_base, "ok": False, "outcome": "approval_denied", "error": "Approval token requis", "url": url}
                    _audit_write({"event": "agents.desktop.step", "trace_id": trace_id, **out_step})
                    results.append({"ok": False, "outcome": "approval_denied", "kind": "open_url", "step_index": i})
                    step_outputs.append({k: v for k, v in out_step.items() if k not in {"event", "trace_id"}})
                    errors.append({"step_index": i, "kind": "open_url", "outcome": "approval_denied", "url": url})
                    if stop_on_fail_bool:
                        break
                    else:
                        continue
                if dry_run:
                    out_step = {**step_base, "ok": True, "outcome": "dry_run", "url": url}
                    _audit_write({"event": "agents.desktop.step", "trace_id": trace_id, **out_step})
                    results.append({"ok": True, "outcome": "dry_run", "kind": "open_url", "step_index": i})
                    step_outputs.append({k: v for k, v in out_step.items() if k not in {"event", "trace_id"}})
                    continue
                try:
                    import webbrowser

                    ok = bool(webbrowser.open(url, new=2))
                    out_step = {**step_base, "ok": ok, "outcome": "ok" if ok else "error", "url": url}
                    _audit_write({"event": "agents.desktop.step", "trace_id": trace_id, **out_step})
                    results.append({"ok": ok, "outcome": "ok" if ok else "error", "kind": "open_url", "step_index": i})
                    step_outputs.append({k: v for k, v in out_step.items() if k not in {"event", "trace_id"}})
                    if not ok:
                        errors.append({"step_index": i, "kind": "open_url", "outcome": "error", "url": url})
                        if stop_on_fail_bool:
                            break
                    continue
                except Exception as e:
                    out_step = {**step_base, "ok": False, "outcome": "error", "error": str(e), "url": url}
                    _audit_write({"event": "agents.desktop.step", "trace_id": trace_id, **out_step})
                    results.append({"ok": False, "outcome": "error", "kind": "open_url", "step_index": i})
                    step_outputs.append({k: v for k, v in out_step.items() if k not in {"event", "trace_id"}})
                    errors.append({"step_index": i, "kind": "open_url", "outcome": "error", "url": url, "error": str(e)})
                    if stop_on_fail_bool:
                        break
                    else:
                        continue

            if step_kind in {"observe_screen", "click_xy", "move_xy", "drag_xy", "type_text", "hotkey", "scroll", "wait_ms"}:
                step_base = {**base, "kind": step_kind, "step_index": i}
                out_step = _handle_computer_use_action(
                    kind=step_kind,
                    action=step,
                    ctx=ctx,
                    base=step_base,
                    trace_id=trace_id,
                    dry_run=dry_run,
                    audit_event="agents.desktop.step",
                    step_index=i,
                )
                results.append({"ok": bool(out_step.get("ok")), "outcome": out_step.get("outcome"), "kind": step_kind, "step_index": i})
                step_outputs.append({k: v for k, v in out_step.items() if k not in {"event", "trace_id"}})
                if not out_step.get("ok"):
                    errors.append(
                        {
                            "step_index": i,
                            "kind": step_kind,
                            "outcome": out_step.get("outcome"),
                            "error": out_step.get("error"),
                        }
                    )
                    if stop_on_fail_bool:
                        break
                continue

            out_step = {**base, "ok": False, "outcome": "unknown_kind", "error": "kind non supporté dans run_steps", "kind": step_kind, "step_index": i}
            _audit_write({"event": "agents.desktop.step", "trace_id": trace_id, **out_step})
            results.append({"ok": False, "outcome": "unknown_kind", "kind": step_kind, "step_index": i})
            step_outputs.append({k: v for k, v in out_step.items() if k not in {"event", "trace_id"}})
            errors.append({"step_index": i, "kind": step_kind, "outcome": "unknown_kind"})
            if stop_on_fail_bool:
                break
            else:
                continue

        elapsed_ms = int((time.monotonic() - started) * 1000.0)
        ok_all = (len(errors) == 0) and (len(results) == len(steps)) and all(r.get("ok") is True for r in results)
        out = {
            **base,
            "ok": ok_all,
            "outcome": "ok" if ok_all else ("error" if stop_on_fail_bool else "partial"),
            "kind": "run_steps",
            "stop_on_fail": stop_on_fail_bool,
            "steps_requested": len(steps),
            "steps_executed": len(results),
            "elapsed_ms": elapsed_ms,
            "results": results,
            "step_outputs": step_outputs,
            "errors": errors,
        }
        _audit_write({"event": "agents.desktop.audit", "trace_id": trace_id, **out})
        return out

    if kind in {"observe_screen", "click_xy", "move_xy", "drag_xy", "type_text", "hotkey", "scroll", "wait_ms"}:
        return _handle_computer_use_action(kind=kind, action=action, ctx=ctx, base=base, trace_id=trace_id, dry_run=dry_run)

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

