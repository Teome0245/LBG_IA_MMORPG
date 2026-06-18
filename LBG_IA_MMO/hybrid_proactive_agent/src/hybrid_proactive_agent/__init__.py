"""Agent hybride proactif : modes léger / avancé / autonome, mémoire longue, équipe multi-rôles."""

from hybrid_proactive_agent.engine import (
    DEFAULT_GOALS,
    ActionKind,
    AgentInternalState,
    HybridProactiveEngine,
    InternalGoal,
    InternalGoalStatus,
    ProactiveAction,
    ProactifMode,
    QuestionCategory,
    integration_hints,
)
from hybrid_proactive_agent.memory import LongTermMemoryStore, MemoryEntry
from hybrid_proactive_agent.team import (
    ROLE_WEIGHTS,
    MultiAgentProactiveCoordinator,
    RoleWeights,
    SpecialistRole,
    team_integration_hints,
)

__all__ = [
    "DEFAULT_GOALS",
    "ActionKind",
    "AgentInternalState",
    "HybridProactiveEngine",
    "InternalGoal",
    "InternalGoalStatus",
    "LongTermMemoryStore",
    "MemoryEntry",
    "MultiAgentProactiveCoordinator",
    "ProactiveAction",
    "ProactifMode",
    "QuestionCategory",
    "ROLE_WEIGHTS",
    "RoleWeights",
    "SpecialistRole",
    "integration_hints",
    "team_integration_hints",
]
