from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
import uuid


@dataclass
class Entity:
    id: str
    kind: Literal["player", "npc"]
    name: str
    role: str = "civil"
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    stats: dict[str, Any] = None

    def __post_init__(self):
        if self.stats is None:
            self.stats = {}

    @staticmethod
    def new_player(name: str) -> Entity:
        return Entity(
            id=f"player:{uuid.uuid4().hex[:8]}",
            kind="player",
            name=name[:64],
        )

    @staticmethod
    def new_npc(name: str, x: float, z: float) -> Entity:
        return Entity(
            id=f"npc:{uuid.uuid4().hex[:8]}",
            kind="npc",
            name=name,
            x=x,
            y=0.0,
            z=z,
        )

    def to_snapshot(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "role": self.role,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "vx": self.vx,
            "vy": self.vy,
            "vz": self.vz,
            "stats": self.stats,
        }
