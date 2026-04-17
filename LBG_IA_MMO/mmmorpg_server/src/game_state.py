"""État autoritatif du monde — Phase 1."""

from __future__ import annotations

import math

from mmmorpg_server.entities.entity import Entity
from mmmorpg_server.world_core.planet import PlanetConfig
from mmmorpg_server.world_core.time_manager import TimeManager


MAX_SPEED_UNITS_PER_S = 12.0
BOUNDS_HALF = 500.0  # zone "platte" temporaire avant sphère


class GameState:
    def __init__(self) -> None:
        self.planet = PlanetConfig(id="terre1", label="Terre1")
        self.time = TimeManager()
        self.entities: dict[str, Entity] = {}
        self._seed_npcs()

    def _seed_npcs(self) -> None:
        for name, xz in (
            ("Marchand civile", (12.0, -5.0)),
            ("Garde poste", (-20.0, 8.0)),
        ):
            npc = Entity.new_npc(name, xz[0], xz[1])
            self.entities[npc.id] = npc

    def add_player(self, name: str) -> Entity:
        p = Entity.new_player(name)
        p.x, p.y, p.z = 0.0, 0.0, 0.0
        self.entities[p.id] = p
        return p

    def remove_player(self, player_id: str) -> None:
        ent = self.entities.get(player_id)
        if ent and ent.kind == "player":
            del self.entities[player_id]

    def apply_player_move(self, player_id: str, x: float, y: float, z: float) -> None:
        ent = self.entities.get(player_id)
        if not ent or ent.kind != "player":
            return
        dx, dy, dz = x - ent.x, y - ent.y, z - ent.z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        if dist < 1e-6:
            ent.vx = ent.vy = ent.vz = 0.0
            return
        scale = min(1.0, MAX_SPEED_UNITS_PER_S / dist)
        ent.vx, ent.vy, ent.vz = dx * scale, dy * scale, dz * scale

    def tick(self, dt: float) -> None:
        self.time.advance(dt)
        for ent in self.entities.values():
            if ent.kind == "npc":
                self._npc_step(ent, dt)
            ent.x += ent.vx * dt
            ent.y += ent.vy * dt
            ent.z += ent.vz * dt
            ent.x = max(-BOUNDS_HALF, min(BOUNDS_HALF, ent.x))
            ent.y = max(-50.0, min(50.0, ent.y))
            ent.z = max(-BOUNDS_HALF, min(BOUNDS_HALF, ent.z))
            ent.vx *= 0.92
            ent.vy *= 0.92
            ent.vz *= 0.92

    def _npc_step(self, npc: Entity, dt: float) -> None:
        # PNJ basiques : lente dérive + rebond symbolique sur les bords
        seed = sum(ord(c) for c in npc.id) % 314
        noise = math.sin(self.time.world_time_s * 0.3 + seed) * 2.0
        npc.vx += noise * dt
        npc.vz += math.cos(self.time.world_time_s * 0.25) * 1.5 * dt
        sp = math.sqrt(npc.vx**2 + npc.vz**2)
        cap = 3.0
        if sp > cap:
            npc.vx, npc.vz = npc.vx / sp * cap, npc.vz / sp * cap
        if abs(npc.x) >= BOUNDS_HALF - 2:
            npc.vx *= -0.5
        if abs(npc.z) >= BOUNDS_HALF - 2:
            npc.vz *= -0.5

    def entity_snapshots(self) -> list[dict]:
        return [e.to_snapshot() for e in self.entities.values()]
