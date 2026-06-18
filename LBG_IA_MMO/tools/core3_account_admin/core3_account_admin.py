#!/usr/bin/env python3
"""UI web minimale pour gérer les comptes Core3 / SWGEmu (MariaDB swgemu)."""

from __future__ import annotations

import concurrent.futures
import hashlib
import html
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

try:
    import pymysql
    from pymysql.cursors import DictCursor
except ImportError:
    pymysql = None  # type: ignore[assignment]
    DictCursor = None  # type: ignore[assignment,misc]

DEFAULT_BIND = ("127.0.0.1", 8792)
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{2,32}$")
LBG_ADMIN_MAX = 4

# ADR 0006 — échelle LBG 0–4
LBG_LEVELS: dict[int, dict[str, str]] = {
    0: {
        "name": "player",
        "tag": "—",
        "account": "Joueur ; pas d’accès UI staff.",
        "ingame": "Aucun skill staff. Pas de god.",
    },
    1: {
        "name": "gm",
        "tag": "LBG-GM",
        "account": "Compte joueur (pas CRUD comptes UI).",
        "ingame": "Animation terrain : teleport, spawn léger, revive, quêtes (lecture). Pas de god.",
    },
    2: {
        "name": "moderator",
        "tag": "LBG-Mod",
        "account": "Modération ; lecture comptes (selon politique).",
        "ingame": "Kick, bans IG, getAccountInfo, broadcast zone. Pas de god.",
    },
    3: {
        "name": "dev",
        "tag": "LBG-Dev",
        "account": "Debug / outils techniques.",
        "ingame": "Script, spawn avancé, stats — pas jedi ni économie globale. Pas de god.",
    },
    4: {
        "name": "admin",
        "tag": "LBG-Admin",
        "account": "CRUD comptes UI ; login si serveur verrouillé (Teome).",
        "ingame": "Kit complet + admin_base ; god **manuel** (/setGodMode) uniquement.",
    },
}


def normalize_admin_level(raw: int) -> int:
    """Map legacy SWGEmu 0–15 → LBG 0–4 (double lecture ADR 0006)."""
    if 0 <= raw <= LBG_ADMIN_MAX:
        return raw
    legacy_map = {
        1: 1,
        2: 1,
        3: 1,
        6: 1,
        7: 2,
        8: 2,
        9: 2,
        10: 2,
        11: 2,
        12: 2,
        13: 3,
        14: 3,
    }
    if raw in legacy_map:
        return legacy_map[raw]
    if raw >= 15:
        return 4
    return 0


def level_label(level: int, raw: int | None = None) -> str:
    n = normalize_admin_level(level)
    meta = LBG_LEVELS.get(n, LBG_LEVELS[0])
    suffix = f" (SQL brut: {raw})" if raw is not None and raw != n else ""
    return f"{n} — {meta['name']}{suffix}"


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def db_config() -> dict[str, Any]:
    return {
        "host": env("CORE3_DB_HOST", "127.0.0.1"),
        "port": int(env("CORE3_DB_PORT", "3306") or "3306"),
        "user": env("CORE3_DB_USER", "swgemu"),
        "password": env("CORE3_DB_PASS", ""),
        "database": env("CORE3_DB_NAME", "swgemu"),
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
        "autocommit": True,
    }


def prime_db_enabled() -> bool:
    return env("CORE3_PRIME_DB_ENABLED", "1").lower() in {"1", "true", "yes", "on"}


def precu_db_enabled() -> bool:
    return env("CORE3_PRECU_DB_ENABLED", "0").lower() in {"1", "true", "yes", "on"}


def local_server_id() -> str:
    return env("CORE3_LOCAL_SERVER_ID", "precu").strip().lower() or "precu"


def _remote_db_entry(
    *,
    server_id: str,
    label: str,
    galaxy_id: int,
    host: str,
    port_key: str,
    user_key: str,
    pass_key: str,
    name_key: str,
) -> dict[str, Any]:
    return {
        "id": server_id,
        "label": label,
        "short": label,
        "galaxy_id": galaxy_id,
        "host": host,
        "port": int(env(port_key, env("CORE3_DB_PORT", "3306")) or "3306"),
        "user": env(user_key, env("CORE3_DB_USER", "swgemu")),
        "password": env(pass_key, env("CORE3_DB_PASS", "")),
        "database": env(name_key, env("CORE3_DB_NAME", "swgemu")),
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
        "autocommit": True,
    }


def account_db_servers() -> list[dict[str, Any]]:
    """MariaDB gérées par l'UI — locale (CORE3_DB_HOST) + distante optionnelle."""
    sid = local_server_id()
    if sid == "prime":
        local_meta = {"id": "prime", "label": "Prime", "short": "Prime", "galaxy_id": 3}
    else:
        local_meta = {"id": "precu", "label": "PreCU", "short": "PreCU", "galaxy_id": 2}

    custom_label = env("CORE3_LOCAL_SERVER_LABEL", "")
    if custom_label:
        local_meta["label"] = local_meta["short"] = custom_label

    servers: list[dict[str, Any]] = [{**local_meta, **db_config()}]

    if sid == "precu" and prime_db_enabled():
        prime_host = env("CORE3_PRIME_DB_HOST", "192.168.0.246")
        if prime_host:
            servers.append(
                _remote_db_entry(
                    server_id="prime",
                    label="Prime",
                    galaxy_id=3,
                    host=prime_host,
                    port_key="CORE3_PRIME_DB_PORT",
                    user_key="CORE3_PRIME_DB_USER",
                    pass_key="CORE3_PRIME_DB_PASS",
                    name_key="CORE3_PRIME_DB_NAME",
                )
            )
    elif sid == "prime" and precu_db_enabled():
        precu_host = env("CORE3_PRECU_DB_HOST", "192.168.0.245")
        if precu_host:
            servers.append(
                _remote_db_entry(
                    server_id="precu",
                    label="PreCU",
                    galaxy_id=2,
                    host=precu_host,
                    port_key="CORE3_PRECU_DB_PORT",
                    user_key="CORE3_PRECU_DB_USER",
                    pass_key="CORE3_PRECU_DB_PASS",
                    name_key="CORE3_PRECU_DB_NAME",
                )
            )
    return servers


def get_account_db_server(server_id: str) -> dict[str, Any]:
    sid = (server_id or "precu").strip().lower()
    for srv in account_db_servers():
        if srv["id"] == sid:
            return srv
    raise ValueError(f"serveur inconnu : {server_id}")


def connect():
    if pymysql is None:
        raise RuntimeError("pymysql manquant : pip install -r requirements.txt")
    return pymysql.connect(**db_config())


def connect_server(server_id: str):
    if pymysql is None:
        raise RuntimeError("pymysql manquant : pip install -r requirements.txt")
    srv = get_account_db_server(server_id)
    return pymysql.connect(
        host=srv["host"],
        port=srv["port"],
        user=srv["user"],
        password=srv["password"],
        database=srv["database"],
        charset=srv["charset"],
        cursorclass=srv["cursorclass"],
        autocommit=srv["autocommit"],
    )


def db_secret() -> str:
    return env("CORE3_DB_SECRET", "swgemus3cr37!")


def admin_token() -> str:
    return env("CORE3_ADMIN_TOKEN", "")


def random_salt_hex() -> str:
    return secrets.token_hex(16)


def hash_password(password: str, salt: str, secret: str | None = None) -> str:
    payload = (secret or db_secret()) + password + salt
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: Any) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def html_response(handler: BaseHTTPRequestHandler, status: int, content: str) -> None:
    body = content.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def parse_bind() -> tuple[str, int]:
    raw = env("CORE3_ADMIN_BIND", "")
    if not raw:
        return DEFAULT_BIND
    host, _, port = raw.partition(":")
    return host or "127.0.0.1", int(port or "8792")


def precu_status_host() -> str:
    """Hôte SSH pour sonder PreCU (local sur VM 245 après split)."""
    return env("CORE3_PRECU_STATUS_HOST", "127.0.0.1")


def prime_status_host() -> str:
    """Hôte SSH pour sonder Prime (VM 246 après split)."""
    return env("CORE3_PRIME_STATUS_HOST", "192.168.0.246")


def is_local_host(host: str) -> bool:
    h = (host or "").strip().lower()
    return not h or h in {"127.0.0.1", "localhost", "::1"}


DEFAULT_CORE3_INSTANCES: list[dict[str, Any]] = [
    {
        "id": "swgemu",
        "label": "LBG SWGEMU PreCu",
        "host": precu_status_host(),
        "client_ip": env("CORE3_PRECU_CLIENT_IP", "192.168.0.245"),
        "process": "core3-swgemu",
        "galaxy_id": 2,
        "login_port": 44453,
        "log_path": "/tmp/core3-swgemu.log",
    },
    {
        "id": "prime",
        "label": "LBG MMO Serveur Prime",
        "host": prime_status_host(),
        "client_ip": env("CORE3_PRIME_CLIENT_IP", "192.168.0.246"),
        "process": "core3-clean",
        "galaxy_id": 3,
        "login_port": 44553,
        "log_path": "/tmp/core3-clean.log",
    },
]


def core3_instances_config() -> list[dict[str, Any]]:
    raw = env("CORE3_STATUS_INSTANCES", "")
    if not raw:
        return list(DEFAULT_CORE3_INSTANCES)
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else DEFAULT_CORE3_INSTANCES
    except json.JSONDecodeError:
        return list(DEFAULT_CORE3_INSTANCES)


def _run_text(cmd: list[str], timeout: float = 3.0) -> str:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return (proc.stdout or "") + (proc.stderr or "")
    except (OSError, subprocess.TimeoutExpired):
        return ""


def process_pid(process_name: str) -> int | None:
    out = _run_text(["pgrep", "-x", process_name]).strip()
    if not out:
        return None
    try:
        return int(out.splitlines()[0].strip())
    except (ValueError, IndexError):
        return None


def log_has_ready(log_path: str, tail_bytes: int = 65536) -> bool:
    path = Path(log_path)
    if not path.is_file():
        return False
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > tail_bytes:
                fh.seek(size - tail_bytes)
            chunk = fh.read().decode("utf-8", errors="replace")
        return any("READY" in line for line in chunk.splitlines()[-80:])
    except OSError:
        return False


def udp_port_open(port: int) -> bool:
    out = _run_text(["ss", "-H", "-uln", f"sport = :{port}"])
    return f":{port}" in out


def udp_port_open_remote(host: str, port: int) -> bool:
    if is_local_host(host):
        return udp_port_open(port)
    out = _run_text(["nc", "-zvu", "-w2", host, str(port)], timeout=5.0).lower()
    return "succeeded" in out or "open" in out


def remote_ssh_status(
    host: str,
    process: str,
    log_path: str,
    *,
    user: str | None = None,
) -> tuple[int | None, bool, bool]:
    """Retourne (pid, login_udp_proxy, ready) via SSH — évite les sondes UDP invalides."""
    ssh_user = user or env("CORE3_STATUS_SSH_USER", "lbg")
    script = (
        f"pid=$(pgrep -x {process} 2>/dev/null | head -1); "
        f"ready=0; "
        f"if [ -f {log_path} ] && tail -c 65536 {log_path} | grep -q READY; then ready=1; fi; "
        f"echo PID:${{pid:-}}; echo READY:$ready"
    )
    out = _run_text(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=5",
            "-o",
            "StrictHostKeyChecking=accept-new",
            f"{ssh_user}@{host}",
            script,
        ],
        timeout=8.0,
    )
    pid: int | None = None
    ready = False
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("PID:") and line != "PID:":
            try:
                pid = int(line.split(":", 1)[1])
            except ValueError:
                pid = None
        elif line == "READY:1":
            ready = True
    if pid is None and not ready:
        return None, False, False
    return pid, True, ready


def status_label(online: bool, ready: bool) -> str:
    if not online:
        return "offline"
    return "ready" if ready else "starting"


_STATUS_CACHE_LOCK = threading.Lock()
_STATUS_CACHE: tuple[float, list[dict[str, Any]]] | None = None


def _status_cache_ttl() -> float:
    try:
        return max(0.0, float(env("CORE3_STATUS_CACHE_TTL", "4")))
    except ValueError:
        return 4.0


def probe_core3_instance(inst: dict[str, Any]) -> dict[str, Any]:
    proc = str(inst.get("process", ""))
    host = str(inst.get("host", "127.0.0.1") or "127.0.0.1")
    login_port = int(inst.get("login_port", 0) or 0)
    log_path = str(inst.get("log_path", ""))
    remote = not is_local_host(host)

    if remote:
        pid, login_udp, ready = remote_ssh_status(host, proc, log_path)
        if pid is None and not ready:
            login_udp = udp_port_open_remote(host, login_port) if login_port else False
            pid = None
            online = login_udp
            ready = login_udp
        else:
            online = pid is not None or ready
            if online and not ready and login_port:
                ready = udp_port_open_remote(host, login_port)
    else:
        pid = process_pid(proc) if proc else None
        online = pid is not None
        login_udp = udp_port_open(login_port) if login_port else False
        ready = online and (log_has_ready(log_path) if log_path else login_udp)
        if online and not ready and login_udp:
            ready = True

    client_ip = str(
        inst.get("client_ip")
        or (host if not is_local_host(host) else env("CORE3_PRECU_CLIENT_IP", "192.168.0.245"))
    )
    return {
        "id": inst.get("id", proc),
        "label": inst.get("label", proc),
        "host": host,
        "client_ip": client_ip,
        "process": proc,
        "galaxy_id": inst.get("galaxy_id"),
        "login_port": login_port,
        "online": online,
        "ready": ready,
        "login_udp": login_udp,
        "status": status_label(online, ready),
        "pid": pid,
        "remote": remote,
    }


def fetch_core3_server_status(*, use_cache: bool = True) -> list[dict[str, Any]]:
    global _STATUS_CACHE
    now = time.monotonic()
    if use_cache:
        with _STATUS_CACHE_LOCK:
            cached = _STATUS_CACHE
            if cached and now - cached[0] < _status_cache_ttl():
                return list(cached[1])

    instances = core3_instances_config()
    if len(instances) <= 1:
        rows = [probe_core3_instance(inst) for inst in instances]
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(instances)) as pool:
            rows = list(pool.map(probe_core3_instance, instances))

    with _STATUS_CACHE_LOCK:
        _STATUS_CACHE = (now, rows)
    return rows


def _fetch_account_rows(conn: Any) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.account_id, a.username, a.admin_level, a.active,
                   UNIX_TIMESTAMP(a.created) AS created_ts,
                   (SELECT COUNT(*) FROM characters c WHERE c.account_id = a.account_id) AS char_count
            FROM accounts a
            ORDER BY a.account_id
            """
        )
        return list(cur.fetchall())


def _decorate_account_rows(rows: list[dict[str, Any]], server: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        raw = int(row["admin_level"])
        row["admin_level_raw"] = raw
        row["admin_level"] = normalize_admin_level(raw)
        row["admin_level_label"] = level_label(row["admin_level"], raw)
        row["server_id"] = server["id"]
        row["server_label"] = server["short"]
        row["galaxy_id"] = server.get("galaxy_id")
        out.append(row)
    return out


def list_accounts() -> dict[str, Any]:
    accounts: list[dict[str, Any]] = []
    db_errors: list[dict[str, str]] = []
    for server in account_db_servers():
        try:
            with connect_server(server["id"]) as conn:
                accounts.extend(_decorate_account_rows(_fetch_account_rows(conn), server))
        except Exception as exc:
            db_errors.append({"server_id": server["id"], "server_label": server["short"], "error": str(exc)})
    accounts.sort(key=lambda r: (str(r.get("server_id", "")), int(r["account_id"])))
    return {"accounts": accounts, "db_errors": db_errors}


def list_characters(server_id: str, account_id: int) -> list[dict[str, Any]]:
    with connect_server(server_id) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT character_oid, galaxy_id, firstname, surname, creation_date
                FROM characters
                WHERE account_id = %s
                ORDER BY galaxy_id, firstname
                """,
                (account_id,),
            )
            return list(cur.fetchall())


def create_account(
    username: str,
    password: str,
    admin_level: int,
    *,
    server_id: str = "precu",
) -> dict[str, Any]:
    if not USERNAME_RE.match(username):
        raise ValueError("username invalide (2–32 caractères alphanum + _)")
    if len(password) < 4:
        raise ValueError("mot de passe trop court (min. 4)")
    admin_level = normalize_admin_level(int(admin_level))
    if not 0 <= admin_level <= LBG_ADMIN_MAX:
        raise ValueError(f"admin_level doit être entre 0 et {LBG_ADMIN_MAX}")

    server = get_account_db_server(server_id)
    salt = random_salt_hex()
    pwd_hash = hash_password(password, salt)
    station_id = secrets.randbelow(2**31 - 1)

    with connect_server(server_id) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT account_id FROM accounts WHERE LOWER(username) = LOWER(%s)", (username,))
            if cur.fetchone():
                raise ValueError(f"compte déjà existant sur {server['short']} : {username}")
            cur.execute(
                """
                INSERT INTO accounts (username, password, station_id, salt, admin_level, active)
                VALUES (%s, %s, %s, %s, %s, 1)
                """,
                (username, pwd_hash, station_id, salt, admin_level),
            )
            account_id = cur.lastrowid
    return {
        "account_id": account_id,
        "username": username,
        "admin_level": admin_level,
        "server_id": server["id"],
        "server_label": server["short"],
    }


def update_account(
    server_id: str,
    account_id: int,
    admin_level: int | None,
    active: int | None,
    password: str | None,
) -> None:
    sets: list[str] = []
    params: list[Any] = []

    if admin_level is not None:
        admin_level = normalize_admin_level(int(admin_level))
        if not 0 <= admin_level <= LBG_ADMIN_MAX:
            raise ValueError(f"admin_level invalide (0–{LBG_ADMIN_MAX})")
        sets.append("admin_level = %s")
        params.append(admin_level)
    if active is not None:
        sets.append("active = %s")
        params.append(1 if active else 0)
    if password:
        if len(password) < 4:
            raise ValueError("mot de passe trop court")
        salt = random_salt_hex()
        sets.append("password = %s")
        params.append(hash_password(password, salt))
        sets.append("salt = %s")
        params.append(salt)

    if not sets:
        raise ValueError("aucune modification demandée")

    params.append(account_id)
    with connect_server(server_id) as conn:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE accounts SET {', '.join(sets)} WHERE account_id = %s", params)
            if cur.rowcount == 0:
                raise ValueError("compte introuvable")


def delete_account(server_id: str, account_id: int) -> None:
    with connect_server(server_id) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT account_id FROM accounts WHERE account_id = %s", (account_id,))
            if not cur.fetchone():
                raise ValueError("compte introuvable")
            for sql in (
                "DELETE FROM sessions WHERE account_id = %s",
                "DELETE FROM account_bans WHERE account_id = %s OR issuer_id = %s",
                "DELETE FROM account_log WHERE account_id = %s",
                "DELETE FROM account_ips WHERE account_id = %s",
                "DELETE FROM galaxy_bans WHERE account_id = %s OR issuer_id = %s",
                "DELETE FROM character_bans WHERE account_id = %s OR issuer_id = %s",
                "DELETE FROM characters WHERE account_id = %s",
                "DELETE FROM characters_dirty WHERE account_id = %s",
                "DELETE FROM deleted_characters WHERE account_id = %s",
                "DELETE FROM accounts WHERE account_id = %s",
            ):
                if "issuer_id" in sql:
                    cur.execute(sql, (account_id, account_id))
                else:
                    cur.execute(sql, (account_id,))


PAGE_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>LBG-MMO-Core3 — Comptes</title>
  <style>
    :root { --bg:#0f1419; --card:#1a2332; --text:#e7ecf3; --muted:#94a3b8; --accent:#38bdf8; --danger:#f87171; --ok:#4ade80; }
    * { box-sizing: border-box; }
    body { margin:0; font-family: system-ui, sans-serif; background:var(--bg); color:var(--text); }
    header { padding:1rem 1.5rem; border-bottom:1px solid #243044; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:.5rem; }
    h1 { margin:0; font-size:1.15rem; }
    main { padding:1.5rem; max-width:1100px; margin:0 auto; }
    .grid { display:grid; grid-template-columns:1fr 1fr; gap:1rem; }
    @media (max-width:800px) { .grid { grid-template-columns:1fr; } }
    section { background:var(--card); border-radius:10px; padding:1rem; border:1px solid #243044; }
    h2 { margin:0 0 .75rem; font-size:.95rem; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }
    label { display:block; font-size:.8rem; color:var(--muted); margin:.4rem 0 .15rem; }
    input, select, button { font:inherit; }
    input, select { width:100%; padding:.45rem .55rem; border-radius:6px; border:1px solid #334155; background:#0b1220; color:var(--text); }
    button { margin-top:.6rem; padding:.45rem .9rem; border-radius:6px; border:none; background:var(--accent); color:#0b1220; font-weight:600; cursor:pointer; }
    button.danger { background:var(--danger); color:#fff; }
    button.secondary { background:#334155; color:var(--text); }
    table { width:100%; border-collapse:collapse; font-size:.85rem; }
    th, td { text-align:left; padding:.45rem .35rem; border-bottom:1px solid #243044; }
    tr:hover { background:#111827; }
    .badge { display:inline-block; padding:.1rem .45rem; border-radius:999px; font-size:.7rem; background:#334155; }
    .badge.on { background:#14532d; color:var(--ok); }
    .badge.off { background:#450a0a; color:var(--danger); }
    .badge.srv-precu { background:#1e3a5f; color:#7dd3fc; }
    .badge.srv-prime { background:#3b0764; color:#d8b4fe; }
    #flash { min-height:1.2rem; margin-bottom:.75rem; font-size:.85rem; }
    #flash.ok { color:var(--ok); }
    #flash.err { color:var(--danger); }
    .actions button { margin-top:0; margin-right:.25rem; font-size:.75rem; padding:.25rem .5rem; }
    .token-bar { background:#1e3a5f; border:1px solid var(--accent); border-radius:8px; padding:.75rem 1rem; margin-bottom:1rem; display:flex; flex-wrap:wrap; align-items:center; gap:.75rem; }
    .token-bar input { max-width:20rem; }
    .levels-ref { margin-top:1rem; font-size:.8rem; color:var(--muted); }
    .levels-ref summary { cursor:pointer; color:var(--accent); font-weight:600; }
    .levels-ref table { width:100%; margin-top:.5rem; font-size:.78rem; }
    .levels-ref th { color:var(--text); text-align:left; }
    .levels-ref td, .levels-ref th { padding:.25rem .4rem; border-bottom:1px solid #243044; }
    .levels-ref .hi { color:var(--ok); }
    .servers-bar { display:flex; flex-wrap:wrap; gap:.6rem; align-items:center; }
    .server-pill { display:flex; align-items:center; gap:.55rem; padding:.45rem .75rem; border-radius:8px; background:#111827; border:1px solid #334155; font-size:.8rem; }
    .server-pill .dot { flex-shrink:0; width:.95rem; height:.95rem; border-radius:50%; background:var(--muted); border:2px solid rgba(255,255,255,.15); }
    .server-pill.ready .dot { background:var(--ok); border-color:rgba(74,222,128,.5); box-shadow:0 0 10px var(--ok); }
    .server-pill.starting .dot { background:#fbbf24; border-color:rgba(251,191,36,.5); box-shadow:0 0 8px #fbbf24; }
    .server-pill.offline .dot { background:var(--danger); border-color:rgba(248,113,113,.4); box-shadow:0 0 6px rgba(248,113,113,.35); }
    .server-pill .meta { color:var(--muted); font-size:.72rem; }
    footer { text-align:center; color:var(--muted); font-size:.75rem; padding:1rem; }
  </style>
</head>
<body>
  <header>
    <h1>LBG-MMO-Core3 — Gestion des comptes</h1>
    <div class="servers-bar" id="serversBar" aria-live="polite">
      <span style="color:var(--muted);font-size:.8rem">Serveurs :</span>
      <span style="color:var(--muted);font-size:.8rem">chargement…</span>
    </div>
  </header>
  <main>
    <div class="token-bar" id="tokenRow">
      <strong>Token admin</strong>
      <input id="token" type="password" placeholder="ex. lbg-core3-admin-change-me" autocomplete="off" />
      <button type="button" id="saveTokenBtn" class="secondary">Valider le token</button>
      <span style="color:var(--muted);font-size:.8rem">Obligatoire pour charger les comptes (en-tête X-Admin-Token).</span>
    </div>
    <div id="flash"></div>
    <div class="grid">
      <section>
        <h2>Comptes</h2>
        <table>
          <thead><tr><th>Serveur</th><th>ID</th><th>Login</th><th>Admin</th><th>Actif</th><th>Persos</th><th></th></tr></thead>
          <tbody id="accounts"></tbody>
        </table>
        <button class="secondary" id="refresh">Rafraîchir</button>
      </section>
      <section>
        <h2>Nouveau compte</h2>
        <label>Serveur <select id="newServer"></select></label>
        <label>Username <input id="newUser" autocomplete="off" /></label>
        <label>Mot de passe <input id="newPass" type="password" /></label>
        <label>Niveau LBG <select id="newAdmin"></select></label>
        <button id="createBtn">Créer</button>
        <details class="levels-ref">
          <summary>Niveaux admin LBG (0–4) — ADR 0006</summary>
          <table>
            <thead><tr><th>Niv.</th><th>Nom</th><th>Tag</th><th>Compte / UI</th><th>En jeu</th></tr></thead>
            <tbody id="levelsHelpBody"></tbody>
          </table>
          <p style="margin:.5rem 0 0">Double lecture legacy 0–15 → 0–4 pendant 2 semaines. SQL brut affiché si différent. Héritage perso : <strong>désactivé</strong> (<code>inheritAccountAdminLevel = 0</code>). God : manuel, palier <strong>4</strong> uniquement.</p>
        </details>
      </section>
    </div>
    <section style="margin-top:1rem">
      <h2>Modifier le compte sélectionné</h2>
      <p id="selectedHint" style="color:var(--muted);font-size:.85rem">Cliquez sur un compte dans la liste.</p>
      <div class="grid">
        <div>
          <label>Niveau LBG <select id="editAdmin"></select></label>
          <label>Actif <select id="editActive"><option value="1">Oui</option><option value="0">Non</option></select></label>
          <label>Nouveau mot de passe (vide = inchangé) <input id="editPass" type="password" /></label>
          <button id="saveBtn">Enregistrer</button>
        </div>
        <div>
          <h2 style="margin-top:0">Personnages</h2>
          <ul id="chars" style="margin:0;padding-left:1.1rem;color:var(--muted)"></ul>
          <button class="danger" id="deleteBtn" style="margin-top:1rem">Supprimer le compte</button>
        </div>
      </div>
    </section>
  </main>
  <footer>Écoute locale par défaut — protéger avec CORE3_ADMIN_TOKEN sur le LAN</footer>
  <script>
    const TOKEN_KEY = "core3_admin_token";
    let selectedId = null;
    let selectedServer = null;
    let LBG_LEVELS = {};
    let DB_SERVERS = [];

    function fillServerSelect(id, value) {
      const sel = document.getElementById(id);
      sel.innerHTML = DB_SERVERS.map(s =>
        `<option value="${escapeHtml(s.id)}">${escapeHtml(s.label)}</option>`
      ).join("");
      if (value !== undefined) sel.value = String(value);
    }

    function fillAdminSelect(id, value) {
      const sel = document.getElementById(id);
      sel.innerHTML = Object.keys(LBG_LEVELS).sort((a,b) => +a - +b).map(k => {
        const m = LBG_LEVELS[k];
        return `<option value="${k}">${k} — ${escapeHtml(m.name)}</option>`;
      }).join("");
      if (value !== undefined) sel.value = String(value);
    }
    function fillLevelsHelp() {
      const tb = document.getElementById("levelsHelpBody");
      tb.innerHTML = Object.keys(LBG_LEVELS).sort((a,b) => +a - +b).map(k => {
        const m = LBG_LEVELS[k];
        return `<tr><td>${k}</td><td>${escapeHtml(m.name)}</td><td>${escapeHtml(m.tag)}</td><td>${escapeHtml(m.account)}</td><td>${escapeHtml(m.ingame)}</td></tr>`;
      }).join("");
    }
    async function initLevels() {
      const meta = await api("/api/meta");
      LBG_LEVELS = meta.levels || {};
      DB_SERVERS = meta.db_servers || [{ id: "precu", label: "PreCU" }];
      fillAdminSelect("newAdmin", 0);
      fillAdminSelect("editAdmin", 0);
      fillServerSelect("newServer", DB_SERVERS[0] ? DB_SERVERS[0].id : "precu");
      fillLevelsHelp();
    }

    function token() {
      return (document.getElementById("token").value || localStorage.getItem(TOKEN_KEY) || "").trim();
    }
    function saveToken() {
      const t = document.getElementById("token").value.trim();
      if (t) localStorage.setItem(TOKEN_KEY, t);
    }
    function flash(msg, ok) {
      const el = document.getElementById("flash");
      el.textContent = msg;
      el.className = ok ? "ok" : "err";
    }

    const SERVER_STATUS_FR = {
      ready: "En ligne",
      starting: "Démarrage",
      offline: "Hors ligne",
    };

    async function refreshServers() {
      const bar = document.getElementById("serversBar");
      try {
        const rows = await fetch("/api/servers").then(r => r.json());
        const pills = rows.map(s => {
          const st = s.status || "offline";
          const label = SERVER_STATUS_FR[st] || st;
          const pid = s.pid ? `PID ${s.pid}` : (s.remote ? "distant" : "—");
          const ip = s.client_ip || s.host || "—";
          const port = s.login_port ? `:${s.login_port}` : "";
          return `<div class="server-pill ${escapeHtml(st)}" title="${escapeHtml(s.process || "")}">
            <span class="dot"></span>
            <span><strong>${escapeHtml(s.label)}</strong><br><span class="meta">${escapeHtml(label)} · <strong>${escapeHtml(ip)}</strong>${escapeHtml(port)} · ${escapeHtml(pid)}</span></span>
          </div>`;
        }).join("");
        bar.innerHTML = '<span style="color:var(--muted);font-size:.8rem">Serveurs :</span>' + pills;
      } catch (e) {
        bar.innerHTML = '<span style="color:var(--danger);font-size:.8rem">État serveurs indisponible</span>';
      }
    }
    async function api(path, opts = {}) {
      const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
      const t = token();
      if (t) headers["X-Admin-Token"] = t;
      const res = await fetch(path, { ...opts, headers });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || res.statusText);
      return data;
    }
    function renderAccounts(payload) {
      const rows = Array.isArray(payload) ? payload : (payload.accounts || []);
      const tb = document.getElementById("accounts");
      tb.innerHTML = rows.map(a => `
        <tr data-id="${a.account_id}" data-server="${escapeHtml(a.server_id || 'precu')}" style="cursor:pointer">
          <td><span class="badge srv-${escapeHtml(a.server_id || 'precu')}">${escapeHtml(a.server_label || a.server_id || 'PreCU')}</span></td>
          <td>${a.account_id}</td>
          <td>${escapeHtml(a.username)}</td>
          <td title="${escapeHtml(a.admin_level_label || '')}">${escapeHtml(a.admin_level_label || a.admin_level)}</td>
          <td><span class="badge ${a.active ? "on" : "off"}">${a.active ? "oui" : "non"}</span></td>
          <td>${a.char_count}</td>
          <td class="actions"><button class="secondary" data-pick="${a.account_id}" data-server="${escapeHtml(a.server_id || 'precu')}">Éditer</button></td>
        </tr>`).join("");
      tb.querySelectorAll("[data-pick]").forEach(btn => btn.onclick = (e) => {
        e.stopPropagation();
        selectAccount(btn.dataset.server, +btn.dataset.pick, rows);
      });
      tb.querySelectorAll("tr").forEach(tr => tr.onclick = () => selectAccount(tr.dataset.server, +tr.dataset.id, rows));
    }
    function escapeHtml(s) {
      return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
    }
    async function selectAccount(serverId, id, rowsCache) {
      selectedId = id;
      selectedServer = serverId || "precu";
      const payload = rowsCache ? { accounts: rowsCache } : await api("/api/accounts");
      const rows = Array.isArray(payload) ? payload : (payload.accounts || []);
      const acc = rows.find(r => r.account_id === id && (r.server_id || "precu") === selectedServer);
      if (!acc) return;
      document.getElementById("selectedHint").textContent =
        `${acc.server_label || acc.server_id} — compte #${acc.account_id} — ${acc.username}`;
      document.getElementById("editAdmin").value = String(acc.admin_level);
      document.getElementById("editActive").value = acc.active ? "1" : "0";
      document.getElementById("editPass").value = "";
      const chars = await api(`/api/accounts/${selectedServer}/${id}/characters`);
      const ul = document.getElementById("chars");
      ul.innerHTML = chars.length
        ? chars.map(c => `<li>G${c.galaxy_id} — ${escapeHtml(c.firstname)} ${escapeHtml(c.surname || "")} (oid ${c.character_oid})</li>`).join("")
        : "<li>Aucun personnage</li>";
    }
    async function refresh() {
      saveToken();
      const payload = await api("/api/accounts");
      renderAccounts(payload);
      const errs = payload.db_errors || [];
      if (errs.length) {
        flash("Liste partielle : " + errs.map(e => `${e.server_label}: ${e.error}`).join(" ; "), false);
      } else {
        flash("Liste à jour.", true);
      }
    }
    document.getElementById("refresh").onclick = () => refresh().catch(e => flash(e.message, false));
    document.getElementById("createBtn").onclick = async () => {
      try {
        saveToken();
        const body = {
          username: document.getElementById("newUser").value.trim(),
          password: document.getElementById("newPass").value,
          admin_level: +document.getElementById("newAdmin").value,
          server_id: document.getElementById("newServer").value,
        };
        const r = await api("/api/accounts", { method: "POST", body: JSON.stringify(body) });
        flash(`Compte créé (${r.server_label || r.server_id}) : ${r.username} (#${r.account_id})`, true);
        document.getElementById("newUser").value = "";
        document.getElementById("newPass").value = "";
        await refresh();
      } catch (e) { flash(e.message, false); }
    };
    document.getElementById("saveBtn").onclick = async () => {
      if (!selectedId) return flash("Sélectionnez un compte.", false);
      try {
        saveToken();
        const body = {
          admin_level: +document.getElementById("editAdmin").value,
          active: +document.getElementById("editActive").value
        };
        const p = document.getElementById("editPass").value;
        if (p) body.password = p;
        await api(`/api/accounts/${selectedServer}/${selectedId}`, { method: "PATCH", body: JSON.stringify(body) });
        flash("Compte mis à jour.", true);
        await refresh();
        await selectAccount(selectedServer, selectedId);
      } catch (e) { flash(e.message, false); }
    };
    document.getElementById("deleteBtn").onclick = async () => {
      if (!selectedId) return flash("Sélectionnez un compte.", false);
      if (!confirm("Supprimer définitivement ce compte et ses données liées ?")) return;
      try {
        saveToken();
        await api(`/api/accounts/${selectedServer}/${selectedId}`, { method: "DELETE" });
        flash("Compte supprimé.", true);
        selectedId = null;
        selectedServer = null;
        document.getElementById("selectedHint").textContent = "Cliquez sur un compte dans la liste.";
        document.getElementById("chars").innerHTML = "";
        await refresh();
      } catch (e) { flash(e.message, false); }
    };
    if (localStorage.getItem(TOKEN_KEY)) {
      document.getElementById("token").value = localStorage.getItem(TOKEN_KEY);
    }
    document.getElementById("saveTokenBtn").onclick = () => {
      saveToken();
      initLevels().then(() => refresh()).catch(e => flash(e.message, false));
    };
    document.getElementById("token").addEventListener("keydown", (e) => {
      if (e.key === "Enter") { saveToken(); refresh().catch(err => flash(err.message, false)); }
    });
    refreshServers();
    setInterval(refreshServers, 15000);
    initLevels().then(() => {
      if (token()) refresh().catch(e => flash(e.message, false));
      else flash("Saisissez le token ci-dessus puis cliquez « Valider le token ».", false);
    }).catch(e => flash(e.message, false));
  </script>
</body>
</html>"""


def parse_account_api_path(path: str) -> tuple[str | None, int | None, str | None]:
    """Retourne (server_id, account_id, suffix) pour /api/accounts/..."""
    parts = path.strip("/").split("/")
    if len(parts) < 3 or parts[0] != "api" or parts[1] != "accounts":
        return None, None, None
    if len(parts) == 4 and parts[2].isdigit() and parts[3] == "characters":
        return "precu", int(parts[2]), "characters"
    if len(parts) == 3 and parts[2].isdigit():
        return "precu", int(parts[2]), None
    if len(parts) >= 4 and parts[2] in {"precu", "prime"} and parts[3].isdigit():
        suffix = parts[4] if len(parts) > 4 else None
        return parts[2], int(parts[3]), suffix
    return None, None, None


class AdminHandler(BaseHTTPRequestHandler):
    server_version = "Core3AccountAdmin/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _authorized(self) -> bool:
        required = admin_token()
        if not required:
            return True
        got = self.headers.get("X-Admin-Token", "")
        if not got:
            qs = parse_qs(urlparse(self.path).query)
            got = (qs.get("token") or [""])[0]
        return secrets.compare_digest(got, required)

    def _reject_auth(self) -> None:
        json_response(self, 401, {"error": "token admin invalide ou manquant (X-Admin-Token)"})

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("JSON invalide") from exc

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            return html_response(self, 200, PAGE_HTML)
        if path == "/api/levels":
            return json_response(self, 200, LBG_LEVELS)
        if path == "/api/meta":
            return json_response(
                self,
                200,
                {
                    "levels": LBG_LEVELS,
                    "db_servers": [
                        {"id": s["id"], "label": s["label"], "galaxy_id": s.get("galaxy_id")}
                        for s in account_db_servers()
                    ],
                },
            )
        if path == "/api/servers":
            try:
                return json_response(self, 200, fetch_core3_server_status())
            except Exception as exc:
                return json_response(self, 500, {"error": str(exc)})
        if not self._authorized():
            return self._reject_auth()
        try:
            if path == "/api/accounts":
                return json_response(self, 200, list_accounts())
            server_id, account_id, suffix = parse_account_api_path(path)
            if server_id and account_id is not None and suffix == "characters":
                return json_response(self, 200, list_characters(server_id, account_id))
            json_response(self, 404, {"error": "introuvable"})
        except Exception as exc:
            json_response(self, 500, {"error": str(exc)})

    def do_POST(self) -> None:
        if not self._authorized():
            return self._reject_auth()
        if urlparse(self.path).path != "/api/accounts":
            return json_response(self, 404, {"error": "introuvable"})
        try:
            data = self._read_json()
            result = create_account(
                str(data.get("username", "")).strip(),
                str(data.get("password", "")),
                int(data.get("admin_level", 0)),
                server_id=str(data.get("server_id", "precu")),
            )
            json_response(self, 201, result)
        except ValueError as exc:
            json_response(self, 400, {"error": str(exc)})
        except Exception as exc:
            json_response(self, 500, {"error": str(exc)})

    def do_PATCH(self) -> None:
        if not self._authorized():
            return self._reject_auth()
        path = urlparse(self.path).path
        server_id, account_id, suffix = parse_account_api_path(path)
        if account_id is None or suffix is not None:
            return json_response(self, 404, {"error": "introuvable"})
        try:
            data = self._read_json()
            update_account(
                server_id or "precu",
                account_id,
                int(data["admin_level"]) if "admin_level" in data else None,
                int(data["active"]) if "active" in data else None,
                str(data.get("password", "")) or None,
            )
            json_response(self, 200, {"ok": True})
        except ValueError as exc:
            json_response(self, 400, {"error": str(exc)})
        except Exception as exc:
            json_response(self, 500, {"error": str(exc)})

    def do_DELETE(self) -> None:
        if not self._authorized():
            return self._reject_auth()
        path = urlparse(self.path).path
        server_id, account_id, suffix = parse_account_api_path(path)
        if account_id is None or suffix is not None:
            return json_response(self, 404, {"error": "introuvable"})
        try:
            delete_account(server_id or "precu", account_id)
            json_response(self, 200, {"ok": True})
        except ValueError as exc:
            json_response(self, 400, {"error": str(exc)})
        except Exception as exc:
            json_response(self, 500, {"error": str(exc)})

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Admin-Token")
        self.end_headers()


def main() -> None:
    if pymysql is None:
        print("Installer pymysql : pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)
    if not env("CORE3_DB_PASS"):
        print("Avertissement : CORE3_DB_PASS non défini.", file=sys.stderr)
    bind = parse_bind()
    if bind[0] not in ("127.0.0.1", "::1", "localhost") and not admin_token():
        print(
            "Refus : écoute LAN sans CORE3_ADMIN_TOKEN. "
            "Définir un token ou lier 127.0.0.1 uniquement.",
            file=sys.stderr,
        )
        sys.exit(1)
    httpd = HTTPServer(bind, AdminHandler)
    print(f"Core3 Account Admin → http://{bind[0]}:{bind[1]}/")
    if admin_token():
        print("Auth : header X-Admin-Token (ou champ token sur la page)")
    else:
        print("Auth : désactivée (localhost uniquement recommandé)")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
