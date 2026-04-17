from __future__ import annotations

from dataclasses import dataclass, field

from entities.npc import Npc


@dataclass(slots=True)
class WorldState:
    now_s: float = 0.0
    npcs: dict[str, Npc] = field(default_factory=dict)

    @classmethod
    def bootstrap_default(cls) -> "WorldState":
        """État initial : fichier seed versionné (`world/seed_data/`) ou repli minimal."""
        from world.seed import load_initial_world_state

        return load_initial_world_state()

