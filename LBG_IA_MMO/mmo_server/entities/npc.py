from dataclasses import dataclass, field

from lyra_engine.gauges import GaugesState


@dataclass(slots=True)
class Npc:
    id: str
    name: str
    role: str
    gauges: GaugesState = field(default_factory=GaugesState)
    situation: dict = field(default_factory=dict)
    goals: list[str] = field(default_factory=list)
    # Réputation locale simple (v1). Bornage appliqué au chargement/persistance.
    reputation_value: int = 0

