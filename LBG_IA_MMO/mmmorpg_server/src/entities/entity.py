from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
import uuid


@dataclass
class Entity:
    id: str
    kind: Literal["player", "npc"]
    name: str
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0

    @staticmethod
    def new_player(name: str) -> Entity:
        return Entity(
            id=str(uuid.uuid4()),
            kind="player",
            name=name[:64],
        )

    @staticmethod
    def new_npc(name: str, x: float, z: float) -> Entity:
        return Entity(
            id=str(uuid.uuid4()),
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
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "vx": self.vx,
            "vy": self.vy,
            "vz": self.vz,
        }
