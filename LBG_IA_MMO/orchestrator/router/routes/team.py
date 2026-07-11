"""
API équipe virtuelle studio (phase A).

- ``POST /v1/team/plan`` : objectif NL → tâches proposées
- ``POST /v1/team/tasks`` : créer une tâche
- ``GET  /v1/team/tasks`` : lister (filtres role/status/actor_id)
- ``GET  /v1/team/tasks/{id}`` : détail
- ``POST /v1/team/tasks/{id}/approve`` : approuver (token)
- ``POST /v1/team/tasks/{id}/run`` : exécuter
- ``POST /v1/team/tasks/{id}/cancel`` : annuler
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from team import roles as team_roles
from team import store as team_store
from team.models import VALID_PRIORITIES, VALID_ROLES
from team.player_ia_think import infer_approval_on_create
from team.role_aliases import enrich_task_view, role_aliases, role_display
from team.subprojects import list_subprojects

router = APIRouter(tags=["team"])


class PlanRequest(BaseModel):
    objective: str = Field(..., min_length=1)
    actor_id: str = "pilot:team"


class PlanResponse(BaseModel):
    proposals: list[dict[str, object]] = Field(default_factory=list)


class CreateTaskRequest(BaseModel):
    role: str = Field(..., min_length=1)
    objective: str = Field(..., min_length=1)
    actor_id: str = "pilot:team"
    priority: str = "normal"
    approval_required: bool | None = None
    context: dict[str, object] = Field(default_factory=dict)
    approval_token: str | None = None


class ApproveTaskRequest(BaseModel):
    token: str = Field(..., min_length=1)


class RunTaskRequest(BaseModel):
    approval_token: str | None = None


class TaskView(BaseModel):
    id: str
    role: str
    objective: str
    status: str
    priority: str = "normal"
    approval_required: bool = False
    actor_id: str = "pilot:team"
    context: dict[str, object] = Field(default_factory=dict)
    result: dict[str, object] = Field(default_factory=dict)
    trace_id: str = ""
    created_ts: float = 0.0
    updated_ts: float = 0.0
    role_alias: str = ""
    role_title: str = ""
    role_label: str = ""


class TeamMetaResponse(BaseModel):
    roles: list[dict[str, object]] = Field(default_factory=list)
    subprojects: list[dict[str, object]] = Field(default_factory=list)


class TaskListResponse(BaseModel):
    tasks: list[TaskView] = Field(default_factory=list)


def _to_view(task: object) -> TaskView:
    data = asdict(task)  # type: ignore[arg-type]
    data.pop("stored_approval_token", None)
    enriched = enrich_task_view(data)
    return TaskView(**{k: enriched[k] for k in TaskView.model_fields if k in enriched})


@router.get("/team/meta", response_model=TeamMetaResponse)
def team_meta() -> TeamMetaResponse:
    specs = team_roles.ROLE_SPECS
    aliases = role_aliases()
    roles: list[dict[str, object]] = []
    for role in sorted(VALID_ROLES):
        disp = role_display(role)
        spec = specs.get(role, {})
        roles.append(
            {
                **disp,
                "capability": spec.get("capability"),
                "autonomy": spec.get("autonomy"),
                "default_objective": spec.get("default_objective"),
            }
        )
    return TeamMetaResponse(roles=roles, subprojects=list_subprojects())


@router.post("/team/plan", response_model=PlanResponse)
def team_plan(payload: PlanRequest) -> PlanResponse:
    if not team_store.team_enabled():
        raise HTTPException(status_code=503, detail="équipe virtuelle désactivée (LBG_TEAM_ENABLED=0)")
    proposals = team_roles.plan_from_objective(payload.objective, actor_id=payload.actor_id)
    return PlanResponse(proposals=proposals)


@router.post("/team/tasks", response_model=TaskView)
def team_create_task(payload: CreateTaskRequest) -> TaskView:
    if not team_store.team_enabled():
        raise HTTPException(status_code=503, detail="équipe virtuelle désactivée")
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"role invalide: {payload.role}")
    if payload.priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail=f"priority invalide: {payload.priority}")
    approval = payload.approval_required
    inferred = infer_approval_on_create(payload.role, payload.objective, payload.context)
    if inferred is not None and approval is None:
        approval = inferred
    try:
        task = team_store.create_task(
            role=payload.role,
            objective=payload.objective,
            actor_id=payload.actor_id,
            priority=payload.priority,
            approval_required=approval,
            context=payload.context,
            approval_token=payload.approval_token,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _to_view(task)


@router.get("/team/tasks", response_model=TaskListResponse)
def team_list_tasks(
    role: str | None = None,
    status: str | None = None,
    actor_id: str | None = None,
    limit: int = 100,
) -> TaskListResponse:
    tasks = team_store.list_tasks(role=role, status=status, actor_id=actor_id, limit=limit)
    return TaskListResponse(tasks=[_to_view(t) for t in tasks])


@router.get("/team/tasks/{task_id}", response_model=TaskView)
def team_get_task(task_id: str) -> TaskView:
    task = team_store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="tâche introuvable")
    return _to_view(task)


@router.post("/team/tasks/{task_id}/approve", response_model=TaskView)
def team_approve_task(task_id: str, payload: ApproveTaskRequest) -> TaskView:
    task = team_roles.approve_task(task_id, payload.token)
    if task is None:
        raise HTTPException(status_code=404, detail="tâche introuvable")
    return _to_view(task)


@router.post("/team/tasks/{task_id}/run", response_model=TaskView)
def team_run_task(task_id: str, payload: RunTaskRequest | None = None) -> TaskView:
    token = payload.approval_token if payload else None
    task = team_roles.run_task(task_id, approval_token=token)
    if task is None:
        raise HTTPException(status_code=404, detail="tâche introuvable")
    return _to_view(task)


@router.post("/team/tasks/{task_id}/cancel", response_model=TaskView)
def team_cancel_task(task_id: str) -> TaskView:
    task = team_roles.cancel_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="tâche introuvable")
    return _to_view(task)
