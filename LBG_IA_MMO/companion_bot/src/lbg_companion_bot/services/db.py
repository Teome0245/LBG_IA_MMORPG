from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS sessions (
  session_id TEXT PRIMARY KEY,
  created_ts REAL NOT NULL,
  updated_ts REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  ts REAL NOT NULL,
  FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS engine_state (
  session_id TEXT PRIMARY KEY,
  state_json TEXT NOT NULL,
  updated_ts REAL NOT NULL,
  FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS session_meta (
  session_id TEXT PRIMARY KEY,
  last_tick_ts REAL NOT NULL,
  window_start_ts REAL NOT NULL,
  window_nudges INTEGER NOT NULL,
  last_nudge_ts REAL NOT NULL,
  FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);
"""


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str
    ts: float
    id: int | None = None


@dataclass(frozen=True)
class SessionMeta:
    last_tick_ts: float
    window_start_ts: float
    window_nudges: int
    last_nudge_ts: float


def connect(db_path: str) -> sqlite3.Connection:
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA_SQL)
    return con


def now_ts() -> float:
    return float(time.time())


def ensure_session(con: sqlite3.Connection, session_id: str) -> None:
    t = now_ts()
    con.execute(
        "INSERT INTO sessions(session_id, created_ts, updated_ts) VALUES (?, ?, ?) "
        "ON CONFLICT(session_id) DO UPDATE SET updated_ts=excluded.updated_ts",
        (session_id, t, t),
    )
    con.commit()


def add_message(con: sqlite3.Connection, *, session_id: str, role: str, content: str) -> None:
    t = now_ts()
    con.execute(
        "INSERT INTO messages(session_id, role, content, ts) VALUES (?, ?, ?, ?)",
        (session_id, role, content, t),
    )
    con.execute("UPDATE sessions SET updated_ts=? WHERE session_id=?", (t, session_id))
    con.commit()


def get_history(con: sqlite3.Connection, *, session_id: str, limit: int) -> list[ChatMessage]:
    rows = con.execute(
        "SELECT id, role, content, ts FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?",
        (session_id, int(limit)),
    ).fetchall()
    out = [
        ChatMessage(id=int(r["id"]), role=str(r["role"]), content=str(r["content"]), ts=float(r["ts"]))
        for r in rows
    ]
    out.reverse()
    return out


def get_messages_after_id(con: sqlite3.Connection, *, session_id: str, after_id: int, limit: int) -> list[ChatMessage]:
    rows = con.execute(
        "SELECT id, role, content, ts FROM messages WHERE session_id=? AND id>? ORDER BY id ASC LIMIT ?",
        (session_id, int(after_id), int(limit)),
    ).fetchall()
    return [
        ChatMessage(id=int(r["id"]), role=str(r["role"]), content=str(r["content"]), ts=float(r["ts"]))
        for r in rows
    ]


def get_last_message_id(con: sqlite3.Connection, *, session_id: str) -> int:
    row = con.execute("SELECT MAX(id) AS mid FROM messages WHERE session_id=?", (session_id,)).fetchone()
    if not row:
        return 0
    mid = row["mid"]
    return int(mid) if mid is not None else 0


def get_session_meta(con: sqlite3.Connection, *, session_id: str) -> SessionMeta:
    row = con.execute(
        "SELECT last_tick_ts, window_start_ts, window_nudges, last_nudge_ts FROM session_meta WHERE session_id=?",
        (session_id,),
    ).fetchone()
    if row:
        return SessionMeta(
            last_tick_ts=float(row["last_tick_ts"]),
            window_start_ts=float(row["window_start_ts"]),
            window_nudges=int(row["window_nudges"]),
            last_nudge_ts=float(row["last_nudge_ts"]),
        )
    t = now_ts()
    meta = SessionMeta(last_tick_ts=t, window_start_ts=t, window_nudges=0, last_nudge_ts=0.0)
    con.execute(
        "INSERT INTO session_meta(session_id, last_tick_ts, window_start_ts, window_nudges, last_nudge_ts) VALUES (?, ?, ?, ?, ?)",
        (session_id, meta.last_tick_ts, meta.window_start_ts, meta.window_nudges, meta.last_nudge_ts),
    )
    con.commit()
    return meta


def save_session_meta(con: sqlite3.Connection, *, session_id: str, meta: SessionMeta) -> None:
    con.execute(
        "INSERT INTO session_meta(session_id, last_tick_ts, window_start_ts, window_nudges, last_nudge_ts) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(session_id) DO UPDATE SET "
        "last_tick_ts=excluded.last_tick_ts, window_start_ts=excluded.window_start_ts, "
        "window_nudges=excluded.window_nudges, last_nudge_ts=excluded.last_nudge_ts",
        (session_id, meta.last_tick_ts, meta.window_start_ts, int(meta.window_nudges), meta.last_nudge_ts),
    )
    con.commit()


def session_exists(con: sqlite3.Connection, *, session_id: str) -> bool:
    row = con.execute("SELECT 1 FROM sessions WHERE session_id=? LIMIT 1", (session_id,)).fetchone()
    return bool(row)


def load_engine_state(con: sqlite3.Connection, *, session_id: str) -> dict[str, Any] | None:
    row = con.execute("SELECT state_json FROM engine_state WHERE session_id=?", (session_id,)).fetchone()
    if not row:
        return None
    raw = row["state_json"]
    try:
        obj = json.loads(raw)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def save_engine_state(con: sqlite3.Connection, *, session_id: str, state: dict[str, Any]) -> None:
    t = now_ts()
    payload = json.dumps(state, ensure_ascii=False)
    con.execute(
        "INSERT INTO engine_state(session_id, state_json, updated_ts) VALUES (?, ?, ?) "
        "ON CONFLICT(session_id) DO UPDATE SET state_json=excluded.state_json, updated_ts=excluded.updated_ts",
        (session_id, payload, t),
    )
    con.execute("UPDATE sessions SET updated_ts=? WHERE session_id=?", (t, session_id))
    con.commit()


def list_recent_sessions(con: sqlite3.Connection, *, limit: int) -> list[str]:
    rows = con.execute(
        "SELECT session_id FROM sessions ORDER BY updated_ts DESC LIMIT ?",
        (int(limit),),
    ).fetchall()
    return [str(r["session_id"]) for r in rows]

