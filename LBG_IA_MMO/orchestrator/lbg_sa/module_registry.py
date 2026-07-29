"""Registre des modules LBG Studios Agents (studios Cortex / Corps / Peau)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

LbgSaPartition = Literal["cortex", "corps", "peau"]
ModuleStatus = Literal["active", "planned", "frozen"]


@dataclass(frozen=True)
class LbgSaModule:
    id: str
    label: str
    partition: LbgSaPartition
    owner_role: str
    memory_namespace: str
    host_allowlist: tuple[str, ...]
    mmo_safe: bool
    status: ModuleStatus
    docs: tuple[str, ...] = ()
    paths: tuple[str, ...] = ()


LBG_SA_MODULES: tuple[LbgSaModule, ...] = (
    LbgSaModule(
        id="team_studio",
        label="Équipe virtuelle studio",
        partition="cortex",
        owner_role="pm",
        memory_namespace="team/pm",
        host_allowlist=("140",),
        mmo_safe=False,
        status="active",
        docs=("docs/vision_equipe_fable_autoconsultation.md",),
        paths=("orchestrator/team/",),
    ),
    LbgSaModule(
        id="atlas_llm",
        label="Atlas — plateforme LLM locale",
        partition="cortex",
        owner_role="admin_infra",
        memory_namespace="team/atlas",
        host_allowlist=("110", "111", "140", "200", "201", "245", "246"),
        mmo_safe=False,
        status="active",
        docs=("docs/plan_team_local_llm.md", "docs/plan_lbg_studios_agents_partitions.md"),
        paths=("orchestrator/team/admin_infra_workflow.py", "infra/scripts/atlas_bench_watchdog.py"),
    ),
    LbgSaModule(
        id="reason_router",
        label="Routage REASON multi-profils",
        partition="cortex",
        owner_role="dev_game",
        memory_namespace="cortex/router",
        host_allowlist=("110", "140"),
        mmo_safe=False,
        status="active",
        paths=("orchestrator/team/reason_llm.py",),
    ),
    LbgSaModule(
        id="player_ia_choeur",
        label="Chœur — joueurs IA Core3",
        partition="corps",
        owner_role="player_ia",
        memory_namespace="player/lia",
        host_allowlist=("246", "140"),
        mmo_safe=True,
        status="active",
        docs=("docs/core3_ia_prime_stability.md",),
        paths=("orchestrator/team/player_ia_exec.py", "agents/src/lbg_agents/core3_player_autonomy.py"),
    ),
    LbgSaModule(
        id="core3_prime",
        label="Core3 Prime monde",
        partition="corps",
        owner_role="player_ia",
        memory_namespace="corps/core3",
        host_allowlist=("246", "245"),
        mmo_safe=True,
        status="active",
    ),
    LbgSaModule(
        id="pilot_team_ui",
        label="Pilot — onglet Équipe",
        partition="peau",
        owner_role="pm",
        memory_namespace="",
        host_allowlist=("140", "10"),
        mmo_safe=False,
        status="active",
        paths=("pilot_web/index.html",),
    ),
    LbgSaModule(
        id="lbg_sa_memory",
        label="Mémoire LBG_SA namespacée (archives)",
        partition="cortex",
        owner_role="pm",
        memory_namespace="cortex/lbg_sa",
        host_allowlist=("140",),
        mmo_safe=False,
        status="active",
        paths=("orchestrator/lbg_sa/memory_store.py",),
    ),
    LbgSaModule(
        id="hybrid_proactive",
        label="Moteur proactif (greffon)",
        partition="cortex",
        owner_role="pm",
        memory_namespace="cortex/proactive",
        host_allowlist=("140",),
        mmo_safe=False,
        status="planned",
        docs=("hybrid_proactive_agent/docs/GREFFON.md",),
    ),
)


def list_modules(*, partition: LbgSaPartition | None = None, status: ModuleStatus | None = None) -> list[LbgSaModule]:
    out = list(LBG_SA_MODULES)
    if partition is not None:
        out = [m for m in out if m.partition == partition]
    if status is not None:
        out = [m for m in out if m.status == status]
    return out


def get_module(module_id: str) -> LbgSaModule | None:
    for m in LBG_SA_MODULES:
        if m.id == module_id:
            return m
    return None


def modules_as_dicts() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for m in LBG_SA_MODULES:
        d = asdict(m)
        d["host_allowlist"] = list(m.host_allowlist)
        d["docs"] = list(m.docs)
        d["paths"] = list(m.paths)
        rows.append(d)
    return rows
