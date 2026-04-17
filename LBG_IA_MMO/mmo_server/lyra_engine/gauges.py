from dataclasses import dataclass


@dataclass(slots=True)
class GaugesState:
    hunger: float = 0.0
    thirst: float = 0.0
    fatigue: float = 0.0

    def step(self, dt_s: float) -> None:
        self.hunger = min(1.0, self.hunger + 0.0005 * dt_s)
        self.thirst = min(1.0, self.thirst + 0.0007 * dt_s)
        self.fatigue = min(1.0, self.fatigue + 0.0004 * dt_s)

