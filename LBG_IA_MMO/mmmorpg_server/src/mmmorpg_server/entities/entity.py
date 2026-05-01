from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Any
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
    # Champs gameplay (best-effort) — utilisés par GameState (patrouilles, freeze, etc.)
    ry: float = 0.0
    scale: float = 1.0
    busy_timer: float = 0.0
    stats: dict[str, Any] | None = None

    @staticmethod
    def new_player(name: str) -> Entity:
        return Entity(
            id=str(uuid.uuid4()),
            kind="player",
            name=name[:64],
            role="player",
            stats={},
        )

    @staticmethod
    def new_npc(
        name: str,
        x: float,
        z: float,
        *,
        npc_id: str | None = None,
        scale: float = 1.0,
        role: str = "civil",
    ) -> Entity:
        return Entity(
            id=(npc_id.strip() if isinstance(npc_id, str) and npc_id.strip() else str(uuid.uuid4())),
            kind="npc",
            name=name,
            role=(role.strip() if isinstance(role, str) and role.strip() else "civil"),
            x=x,
            y=0.0,
            z=z,
            scale=float(scale) if isinstance(scale, (int, float)) else 1.0,
            stats={},
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
            "ry": self.ry,
            "scale": self.scale,
            "stats": self.stats or {},
        }
