from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# -----------------------------------------------------------------------------
# Config hot-reload (linux.env)
# -----------------------------------------------------------------------------

CFG_CACHE: dict[str, object] = {"mtime": None, "vars": {}}


def env_path() -> Path:
    raw = os.environ.get("LBG_LINUX_ENV_PATH", "").strip()
    if raw:
        return Path(raw)
    return Path("linux.env")


def load_env_vars() -> dict[str, str]:
    p = env_path()
    try:
        st = p.stat()
    except Exception:
        CFG_CACHE["mtime"] = None
        CFG_CACHE["vars"] = {}
        return {}

    mtime = getattr(st, "st_mtime", None)
    if mtime is not None and CFG_CACHE.get("mtime") == mtime:
        return CFG_CACHE.get("vars") or {}  # type: ignore[return-value]

    out: dict[str, str] = {}
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
            out[k] = v
    CFG_CACHE["mtime"] = mtime
    CFG_CACHE["vars"] = out
    return out


def get_cfg(key: str) -> str:
    v = os.environ.get(key)
    if v is not None:
        return v
    return load_env_vars().get(key, "")


def split_csv(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def truthy(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def linux_dry_run(context: dict[str, Any] | None = None) -> bool:
    env = get_cfg("LBG_LINUX_DRY_RUN").strip()
    if env:
        return truthy(env)
    return bool(isinstance(context, dict) and context.get("desktop_dry_run") is True)


def linux_requires_approval() -> bool:
    return bool(get_cfg("LBG_LINUX_APPROVAL_TOKEN").strip())


def linux_approval_ok(context: dict[str, Any] | None = None) -> bool:
    token = get_cfg("LBG_LINUX_APPROVAL_TOKEN").strip()
    if not token:
        return True
    if not isinstance(context, dict):
        return False
    got = context.get("desktop_approval")
    return isinstance(got, str) and secrets.compare_digest(got, token)


def audit_write(line: dict[str, Any]) -> None:
    line = dict(line)
    line["ts"] = datetime.now(timezone.utc).isoformat()
    raw = json.dumps(line, ensure_ascii=False)

    if truthy(get_cfg("LBG_LINUX_AUDIT_STDOUT") or "1"):
        print(raw)

    path = get_cfg("LBG_LINUX_AUDIT_LOG_PATH").strip()
    if not path:
        return
    try:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.open("a", encoding="utf-8").write(raw + "\n")
    except Exception as e:
        print(
            json.dumps({"event": "agents.linux.audit_file_error", "error": f"{type(e).__name__}: {e}"}),
            file=sys.stderr,
        )


def url_allowlist() -> list[str]:
    raw = get_cfg("LBG_LINUX_URL_ALLOWLIST").strip()
    return split_csv(raw) if raw else []


def url_host_allowlist() -> list[str]:
    raw = get_cfg("LBG_LINUX_URL_HOST_ALLOWLIST").strip()
    return split_csv(raw) if raw else []


def host_matches(needle: str, rule: str) -> bool:
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


def url_allowed_by_host(url: str) -> bool:
    allow = url_host_allowlist()
    if not allow:
        return False
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.scheme not in {"http", "https"}:
        return False
    host = (p.hostname or "").strip().lower()
    return any(host_matches(host, rule) for rule in allow)


def url_is_allowed(url: str) -> bool:
    if url in url_allowlist():
        return True
    return url_allowed_by_host(url)


def web_search_enabled() -> bool:
    return truthy(get_cfg("LBG_LINUX_WEB_SEARCH"))


def linux_search_engine() -> str:
    v = get_cfg("LBG_LINUX_SEARCH_ENGINE").strip().lower()
    if v in ("google",):
        return "google"
    return "duckduckgo"


def build_web_search_url(query: str) -> tuple[str | None, str | None]:
    from urllib.parse import quote_plus

    q = (query or "").strip()
    if not q:
        return None, "requête vide"
    if len(q) > 220:
        q = q[:220]
    if linux_search_engine() == "google":
        return "https://www.google.com/search?q=" + quote_plus(q), None
    return "https://duckduckgo.com/?q=" + quote_plus(q), None


def web_search_url_trusted(url: str) -> bool:
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.scheme != "https":
        return False
    host = (p.hostname or "").lower()
    if linux_search_engine() == "google":
        return host in ("www.google.com", "google.com")
    return host in ("duckduckgo.com", "www.duckduckgo.com", "lite.duckduckgo.com")


def file_allowlist_dirs() -> list[Path]:
    raw = get_cfg("LBG_LINUX_FILE_ALLOWLIST_DIRS").strip()
    if not raw:
        return []
    out: list[Path] = []
    for item in split_csv(raw):
        try:
            out.append(Path(item).expanduser().resolve())
        except Exception:
            continue
    return out


def path_is_allowed(path_str: str) -> bool:
    dirs = file_allowlist_dirs()
    if not dirs:
        return False
    try:
        p = Path(path_str).expanduser().resolve()
    except Exception:
        return False
    return any(p == d or d in p.parents for d in dirs)


def env_set_key(text: str, key: str, value: str) -> str:
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


def learn_enabled() -> bool:
    return truthy((get_cfg("LBG_LINUX_LEARN_ENABLED") or "").strip() or "0")


def learn_allowlist() -> list[str]:
    raw = (get_cfg("LBG_LINUX_LEARN_APP_ALLOWLIST") or "").strip()
    return split_csv(raw) if raw else []


def persist_learned_app(app_id: str, exe_path: str) -> tuple[bool, str | None]:
    p = env_path()
    try:
        current = p.read_text(encoding="utf-8") if p.exists() else ""
    except Exception as e:
        return (False, f"read_env_failed: {e}")

    allow = split_csv((get_cfg("LBG_LINUX_APP_ALLOWLIST") or "").strip())
    if app_id not in allow:
        allow.append(app_id)

    map_raw = (get_cfg("LBG_LINUX_APP_MAP_JSON") or "").strip()
    try:
        mapping = json.loads(map_raw) if map_raw else {}
        if not isinstance(mapping, dict):
            mapping = {}
    except Exception:
        mapping = {}
    mapping[app_id] = [exe_path]

    new_text = current
    new_text = env_set_key(new_text, "LBG_LINUX_APP_ALLOWLIST", ",".join(allow))
    new_text = env_set_key(new_text, "LBG_LINUX_APP_MAP_JSON", json.dumps(mapping, ensure_ascii=False))

    try:
        p.write_text(new_text, encoding="utf-8")
        CFG_CACHE["mtime"] = None
        CFG_CACHE["vars"] = {}
        return (True, None)
    except Exception as e:
        return (False, f"write_env_failed: {e}")


def popen_quiet(argv: list[str]) -> None:
    subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def mail_imap_enabled() -> bool:
    return truthy(get_cfg("LBG_LINUX_MAIL_ENABLED"))


def mail_imap_credentials() -> tuple[str, int, str, str, bool]:
    host = get_cfg("LBG_LINUX_MAIL_IMAP_HOST").strip()
    pr = (get_cfg("LBG_LINUX_MAIL_IMAP_PORT").strip() or "993")
    try:
        port = int(pr) if pr else 993
    except ValueError:
        port = 993
    user = get_cfg("LBG_LINUX_MAIL_IMAP_USER").strip()
    password = get_cfg("LBG_LINUX_MAIL_IMAP_PASSWORD").strip()
    use_ssl = not truthy(get_cfg("LBG_LINUX_MAIL_IMAP_NO_SSL").strip())
    return host, port, user, password, use_ssl


def _mail_imap_parse_int_local(action: dict[str, Any], key: str, default: int, lo: int, hi: int) -> int:
    v = action.get(key, default)
    if isinstance(v, bool):
        return default
    if isinstance(v, int):
        n = v
    elif isinstance(v, str) and v.strip().lstrip("-").isdigit():
        try:
            n = int(v.strip())
        except ValueError:
            return default
    else:
        try:
            n = int(v)  # type: ignore[arg-type]
        except Exception:
            return default
    return max(lo, min(hi, n))


def mail_imap_parse_action(action: dict[str, Any]) -> tuple[str, str, int, int, int, str | None]:
    fc = action.get("from_contains")
    sc = action.get("subject_contains")
    fc_s = fc.strip() if isinstance(fc, str) else ""
    sc_s = sc.strip() if isinstance(sc, str) else ""
    if len(fc_s) > 80:
        fc_s = fc_s[:80]
    if len(sc_s) > 120:
        sc_s = sc_s[:120]
    if not fc_s and not sc_s:
        return "", "", 0, 0, 0, "Champs `from_contains` et/ou `subject_contains` requis"
    fold = action.get("folder")
    if isinstance(fold, str) and fold.strip() and fold.strip().upper() != "INBOX":
        return "", "", 0, 0, 0, "Dossier non supporté (MVP : INBOX seulement)"
    max_m = _mail_imap_parse_int_local(action, "max_messages", 3, 1, 10)
    max_b = _mail_imap_parse_int_local(action, "max_body_chars", 800, 0, 4000)
    max_sc = _mail_imap_parse_int_local(action, "max_scan", 200, 10, 500)
    return fc_s, sc_s, max_m, max_b, max_sc, None


def which(exe: str) -> str:
    return shutil.which(exe) or ""

