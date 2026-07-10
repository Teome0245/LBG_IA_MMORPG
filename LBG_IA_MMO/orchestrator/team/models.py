from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

TeamRole = Literal["ops", "qa", "pm"]
TaskStatus = Literal["queued", "running", "review", "done", "failed", "cancelled"]
TaskPriority = Literal["low", "normal", "high", "critical"]

VALID_ROLES: frozenset[str] = frozenset({"ops", "qa", "pm"})
VALID_STATUSES: frozenset[str] = frozenset({"queued", "running", "review", "done", "failed", "cancelled"})
VALID_PRIORITIES: frozenset[str] = frozenset({"low", "normal", "high", "critical"})


@dataclass
class TeamTask:
    id: str
    role: TeamRole
    objective: str
    status: TaskStatus = "queued"
    priority: TaskPriority = "normal"
    approval_required: bool = False
    actor_id: str = "system:team"
    context: dict[str, object] = field(default_factory=dict)
    result: dict[str, object] = field(default_factory=dict)
    trace_id: str = ""
    created_ts: float = 0.0
    updated_ts: float = 0.0
    stored_approval_token: str | None = None
