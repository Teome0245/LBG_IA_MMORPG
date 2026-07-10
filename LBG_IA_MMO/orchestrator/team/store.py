"""Persistance SQLite des tâches équipe virtuelle."""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from typing import Any

from team.models import VALID_PRIORITIES, VALID_ROLES, VALID_STATUSES, TeamTask

_SCHEMA = """
CREATE TABLE IF NOT EXISTS team_tasks (
    id TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    objective TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    priority TEXT NOT NULL DEFAULT 'normal',
    approval_required INTEGER NOT NULL DEFAULT 0,
    actor_id TEXT NOT NULL DEFAULT 'system:team',
    context_json TEXT NOT NULL DEFAULT '{}',
    result_json TEXT NOT NULL DEFAULT '{}',
    trace_id TEXT NOT NULL DEFAULT '',
    created_ts REAL NOT NULL,
    updated_ts REAL NOT NULL,
    stored_approval_token TEXT
);
CREATE INDEX IF NOT EXISTS idx_team_tasks_status ON team_tasks(status);
CREATE INDEX IF NOT EXISTS idx_team_tasks_role ON team_tasks(role);
"""


def db_path() -> str:
    return os.environ.get("LBG_TEAM_DB_PATH", "/var/lib/lbg-ia-mmo/team_tasks.db").strip()


def team_enabled() -> bool:
    return os.environ.get("LBG_TEAM_ENABLED", "1").strip().lower() in ("1", "true", "yes", "on")


def reset_for_tests() -> None:
    """Vide la base en mémoire / fichier de test."""
    path = db_path()
    if path and path != ":memory:" and os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass


def _connect() -> sqlite3.Connection:
    path = db_path()
    if path == ":memory:":
        conn = sqlite3.connect(":memory:", check_same_thread=False)
    else:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = _connect()
        _conn.executescript(_SCHEMA)
        _conn.commit()
    return _conn


def _row_to_task(row: sqlite3.Row) -> TeamTask:
    ctx_raw = row["context_json"] or "{}"
    res_raw = row["result_json"] or "{}"
    try:
        context = json.loads(ctx_raw)
    except json.JSONDecodeError:
        context = {}
    try:
        result = json.loads(res_raw)
    except json.JSONDecodeError:
        result = {}
    if not isinstance(context, dict):
        context = {}
    if not isinstance(result, dict):
        result = {}
    return TeamTask(
        id=row["id"],
        role=row["role"],  # type: ignore[arg-type]
        objective=row["objective"],
        status=row["status"],  # type: ignore[arg-type]
        priority=row["priority"],  # type: ignore[arg-type]
        approval_required=bool(row["approval_required"]),
        actor_id=row["actor_id"],
        context=context,
        result=result,
        trace_id=row["trace_id"] or "",
        created_ts=float(row["created_ts"]),
        updated_ts=float(row["updated_ts"]),
        stored_approval_token=row["stored_approval_token"],
    )


def create_task(
    *,
    role: str,
    objective: str,
    actor_id: str = "system:team",
    priority: str = "normal",
    approval_required: bool | None = None,
    context: dict[str, object] | None = None,
    approval_token: str | None = None,
    trace_id: str | None = None,
) -> TeamTask:
    if role not in VALID_ROLES:
        raise ValueError(f"role invalide: {role}")
    if priority not in VALID_PRIORITIES:
        raise ValueError(f"priority invalide: {priority}")
    now = time.time()
    task_id = str(uuid.uuid4())
    ctx = dict(context or {})
    if trace_id:
        ctx.setdefault("trace_id", trace_id)
    need_approval = approval_required if approval_required is not None else False
    conn = _get_conn()
    conn.execute(
        """
        INSERT INTO team_tasks (
            id, role, objective, status, priority, approval_required,
            actor_id, context_json, result_json, trace_id,
            created_ts, updated_ts, stored_approval_token
        ) VALUES (?, ?, ?, 'queued', ?, ?, ?, ?, '{}', ?, ?, ?, ?)
        """,
        (
            task_id,
            role,
            objective,
            priority,
            1 if need_approval else 0,
            actor_id,
            json.dumps(ctx, ensure_ascii=False),
            trace_id or str(ctx.get("trace_id") or ""),
            now,
            now,
            approval_token,
        ),
    )
    conn.commit()
    return get_task(task_id)  # type: ignore[return-value]


def get_task(task_id: str) -> TeamTask | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM team_tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        return None
    return _row_to_task(row)


def list_tasks(
    *,
    role: str | None = None,
    status: str | None = None,
    actor_id: str | None = None,
    limit: int = 100,
) -> list[TeamTask]:
    clauses: list[str] = []
    params: list[Any] = []
    if role:
        clauses.append("role = ?")
        params.append(role)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if actor_id:
        clauses.append("actor_id = ?")
        params.append(actor_id)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(max(1, min(limit, 500)))
    conn = _get_conn()
    rows = conn.execute(
        f"SELECT * FROM team_tasks{where} ORDER BY updated_ts DESC LIMIT ?",
        params,
    ).fetchall()
    return [_row_to_task(r) for r in rows]


def update_task(
    task_id: str,
    *,
    status: str | None = None,
    result: dict[str, object] | None = None,
    context_patch: dict[str, object] | None = None,
    stored_approval_token: str | None = None,
    clear_approval_token: bool = False,
) -> TeamTask | None:
    task = get_task(task_id)
    if task is None:
        return None
    if status is not None:
        if status not in VALID_STATUSES:
            raise ValueError(f"status invalide: {status}")
        task.status = status  # type: ignore[assignment]
    if result is not None:
        task.result = dict(result)
    if context_patch:
        merged = dict(task.context)
        merged.update(context_patch)
        task.context = merged
    if clear_approval_token:
        task.stored_approval_token = None
    elif stored_approval_token is not None:
        task.stored_approval_token = stored_approval_token
    task.updated_ts = time.time()
    conn = _get_conn()
    conn.execute(
        """
        UPDATE team_tasks SET
            status = ?, result_json = ?, context_json = ?,
            updated_ts = ?, stored_approval_token = ?
        WHERE id = ?
        """,
        (
            task.status,
            json.dumps(task.result, ensure_ascii=False),
            json.dumps(task.context, ensure_ascii=False),
            task.updated_ts,
            task.stored_approval_token,
            task_id,
        ),
    )
    conn.commit()
    return task
