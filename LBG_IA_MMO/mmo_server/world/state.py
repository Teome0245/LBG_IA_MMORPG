from __future__ import annotations

from dataclasses import dataclass, field

from entities.location import Location
from entities.npc import Npc


@dataclass(slots=True)
class WorldState:
    now_s: float = 0.0
    npcs: dict[str, Npc] = field(default_factory=dict)
    locations: dict[str, Location] = field(default_factory=dict)
    active_events: dict = field(default_factory=dict)

    def get_location_by_tag(self, tag: str) -> Location | None:
        for loc in self.locations.values():
            try:
                if tag in (loc.tags or []):
                    return loc
            except Exception:
                continue
        return None

    @classmethod
    def bootstrap_default(cls) -> "WorldState":
        """État initial : fichier seed versionné (`world/seed_data/`) ou repli minimal."""
        from world.seed import load_initial_world_state

        return load_initial_world_state()

