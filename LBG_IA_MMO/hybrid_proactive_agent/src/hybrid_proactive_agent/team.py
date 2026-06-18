from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from hybrid_proactive_agent.engine import (
    HybridProactiveEngine,
    ProactiveAction,
    ProactifMode,
    integration_hints,
)
from hybrid_proactive_agent.memory import LongTermMemoryStore


class SpecialistRole:
    ARCHITECTE = "architecte"
    ORCHESTRATEUR = "orchestrateur"
    GAME_DESIGNER = "game_designer"


class RoleWeights(BaseModel):
    curiosite_boost: float = 0.0
    tension_boost: float = 0.0


ROLE_WEIGHTS: dict[str, RoleWeights] = {
    SpecialistRole.ARCHITECTE: RoleWeights(curiosite_boost=0.08, tension_boost=0.02),
    SpecialistRole.ORCHESTRATEUR: RoleWeights(curiosite_boost=0.04, tension_boost=0.06),
    SpecialistRole.GAME_DESIGNER: RoleWeights(curiosite_boost=0.1, tension_boost=0.03),
}

_MODE_RANK: dict[ProactifMode, int] = {
    "autonome": 3,
    "proactif_avance": 2,
    "proactif_leger": 1,
}


class MultiAgentProactiveCoordinator:
    """
    Trois moteurs (Architecte / Orchestrateur / Game designer) partagent la même observation ;
    décision retenue = mode le plus « fort » (autonome > avancé > léger), avec tie-break sur
    le rôle actif.
    """

    def __init__(
        self,
        memory: LongTermMemoryStore | None = None,
    ) -> None:
        self.memory = memory
        self.engines: dict[str, HybridProactiveEngine] = {
            SpecialistRole.ARCHITECTE: HybridProactiveEngine(),
            SpecialistRole.ORCHESTRATEUR: HybridProactiveEngine(),
            SpecialistRole.GAME_DESIGNER: HybridProactiveEngine(),
        }
        self.active_role: str = SpecialistRole.ORCHESTRATEUR

    def set_active_role(self, role: str) -> None:
        if role in self.engines:
            self.active_role = role

    def observe_all(
        self,
        user_message: str | None,
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = dict(context or {})
        for role, eng in self.engines.items():
            w = ROLE_WEIGHTS.get(role, RoleWeights())
            eng.observe_user_turn(user_message, ctx)
            eng.state.curiosite = min(1.0, eng.state.curiosite + w.curiosite_boost)
            eng.state.tension = min(1.0, eng.state.tension + w.tension_boost)

    def tick_silence_all(self, dt_seconds: float) -> None:
        for eng in self.engines.values():
            eng.tick_silence(dt_seconds)

    def decide_with_memory(self, context: dict[str, Any] | None = None) -> tuple[str, ProactiveAction]:
        ctx = dict(context or {})
        if self.memory:
            hint = self.memory.context_hints(str(ctx.get("intent", "")))
            if hint:
                ctx["long_term_recall"] = hint

        best_role: str | None = None
        best_action: ProactiveAction | None = None
        best_rank = -1

        for role, eng in self.engines.items():
            action = eng.decide(ctx)
            rank = _MODE_RANK[action.mode]
            if rank > best_rank:
                best_rank = rank
                best_role = role
                best_action = action
            elif rank == best_rank and best_role is not None and role == self.active_role:
                best_role = role
                best_action = action

        assert best_role is not None and best_action is not None
        return best_role, best_action


def team_integration_hints(
    coordinator: MultiAgentProactiveCoordinator,
    world_context: dict[str, Any] | None,
) -> dict[str, Any]:
    """Indices issus de l'état du moteur du rôle actif."""
    eng = coordinator.engines.get(coordinator.active_role)
    if not eng:
        return {}
    base = integration_hints(eng.state, world_context)
    base["active_specialist"] = coordinator.active_role
    return base
