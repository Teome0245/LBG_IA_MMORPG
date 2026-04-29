import math
import json
import os
from typing import Any

from mmmorpg_server.entities.entity import Entity
from mmmorpg_server.world_core.planet import PlanetConfig
from mmmorpg_server.world_core.time_manager import TimeManager


MAX_SPEED_UNITS_PER_S = 15.0
BOUNDS_HALF = 60000.0


class GameState:
    def __init__(self) -> None:
        self.planet = PlanetConfig(id="terre1", label="Terre1")
        self.time = TimeManager()
        self.entities: dict[str, Entity] = {}
        self.locations: list[dict[str, Any]] = []
        self._load_world_data()

    def _load_world_data(self) -> None:
        # Tente de charger les données réelles depuis le seed du mmo_server
        seed_path = "../../mmo_server/world/seed_data/world_initial.json"
        if not os.path.exists(seed_path):
            # Fallback local si lancé hors monorepo ou structure différente
            seed_path = "world_initial.json"

        try:
            with open(seed_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            # Charger les Lieux (Locations) pour le rendu "Contenu Réel"
            for loc in data.get("locations", []):
                geom = loc.get("geometry", {})
                # On ne garde que les lieux qui ont des coordonnées exploitables
                if "x" in geom and "y" in geom:
                    self.locations.append({
                        "id": loc["id"],
                        "name": loc["name"],
                        "type": loc["type"],
                        "x": float(geom["x"]),
                        "y": float(geom["y"]),
                        "z": float(geom.get("z", 0.0)),
                        "w": float(geom.get("width", 2.0)),
                        "h": float(geom.get("height", 2.0)),
                    })

            # Charger les NPCs
            for npc_data in data.get("npcs", []):
                sit = npc_data.get("situation", {})
                x = float(sit.get("x", 0.0))
                z = float(sit.get("y", 0.0)) # Mapping Y -> Z pour l'isométrique
                npc = Entity.new_npc(npc_data["name"], x, z)
                npc.role = npc_data.get("role", "civil")
                # On pourrait aussi mapper les stats ici
                self.entities[npc.id] = npc
        except Exception as e:
            print(f"Erreur chargement seed: {e}. Utilisation NPCs par défaut.")
            self._seed_fallback_npcs()

    def _seed_fallback_npcs(self) -> None:
        for name, xz in (
            ("Marchand civile", (12.0, -5.0)),
            ("Garde poste", (-20.0, 8.0)),
            ("Chef Magicien", (5.0, 15.0)),
            ("Guerrier Celadon", (-10.0, -10.0)),
        ):
            npc = Entity.new_npc(name, xz[0], xz[1])
            self.entities[npc.id] = npc

    def add_player(self, name: str) -> Entity:
        p = Entity.new_player(name)
        p.x, p.y, p.z = 0.0, 0.0, 0.0
        # Stats initiales pour la fiche de perso
        p.stats = {
            "hp": 100, "hp_max": 100,
            "mp": 50, "mp_max": 50,
            "stamina": 100, "stamina_max": 100,
            "level": 1,
            "exp": 0, "exp_next": 1000
        }
        self.entities[p.id] = p
        return p

    def remove_player(self, player_id: str) -> None:
        if player_id in self.entities:
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
        
        # Correction de la vitesse : on veut atteindre la cible en ~1 tick (0.05s)
        # On multiplie par 20 (1/dt) pour convertir le déplacement souhaité en vitesse
        target_vx = dx * 20.0
        target_vy = dy * 20.0
        target_vz = dz * 20.0
        
        # Cap à MAX_SPEED
        speed = math.sqrt(target_vx**2 + target_vy**2 + target_vz**2)
        if speed > MAX_SPEED_UNITS_PER_S:
            scale = MAX_SPEED_UNITS_PER_S / speed
            ent.vx, ent.vy, ent.vz = target_vx * scale, target_vy * scale, target_vz * scale
        else:
            ent.vx, ent.vy, ent.vz = target_vx, target_vy, target_vz

    def tick(self, dt: float) -> None:
        self.time.advance(dt)
        for ent in self.entities.values():
            if ent.kind == "npc":
                self._npc_step(ent, dt)
            
            ent.x += ent.vx * dt
            ent.y += ent.vy * dt
            ent.z += ent.vz * dt
            
            # Limites
            ent.x = max(-BOUNDS_HALF, min(BOUNDS_HALF, ent.x))
            ent.z = max(-BOUNDS_HALF, min(BOUNDS_HALF, ent.z))
            
            # Friction (uniquement si pas de commande move active, mais ici on simplifie)
            ent.vx *= 0.8
            ent.vy *= 0.8
            ent.vz *= 0.8

    def _npc_step(self, npc: Entity, dt: float) -> None:
        seed = sum(ord(c) for c in npc.id) % 314
        noise = math.sin(self.time.world_time_s * 0.3 + seed) * 1.5
        npc.vx += noise * dt
        npc.vz += math.cos(self.time.world_time_s * 0.25) * 1.2 * dt
        sp = math.sqrt(npc.vx**2 + npc.vz**2)
        cap = 2.5
        if sp > cap:
            npc.vx, npc.vz = npc.vx / sp * cap, npc.vz / sp * cap

    def entity_snapshots(self) -> list[dict]:
        return [e.to_snapshot() for e in self.entities.values()]
