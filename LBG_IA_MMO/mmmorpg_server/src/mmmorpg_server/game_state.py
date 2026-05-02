"""État autoritatif du monde — Phase 1."""

from __future__ import annotations

import math
import json
import os
from typing import Any

from mmmorpg_server.entities.entity import Entity
from mmmorpg_server.world_core.planet import PlanetConfig
from mmmorpg_server.world_core.time_manager import TimeManager


class StaticObstacle:
    def __init__(self, x: float, z: float, radius: float = 1.0, width: float = 0.0, depth: float = 0.0, kind: str = "circle", hollow: bool = False):
        self.x = x
        self.z = z
        self.radius = radius
        self.width = width
        self.depth = depth
        self.kind = kind # "circle" or "box"
        self.hollow = hollow

    def is_inside(self, px: float, pz: float, margin: float = 0.5) -> bool:
        if self.kind == "circle":
            dist = math.sqrt((px - self.x)**2 + (pz - self.z)**2)
            return dist < (self.radius + margin)
        elif self.kind == "box":
            half_w = (self.width / 2.0)
            half_d = (self.depth / 2.0)
            
            # Si on est à l'extérieur (avec une marge de sécurité), on ne bloque pas
            # Sauf si c'est une boîte pleine (non creuse)
            is_outside = (px < self.x - half_w - margin) or (px > self.x + half_w + margin) or \
                         (pz < self.z - half_d - margin) or (pz > self.z + half_d + margin)
            
            if is_outside:
                return False
                
            if not self.hollow:
                # Boîte pleine : on bloque tout ce qui n'est pas "dehors"
                return True
            
            # Pour une boîte creuse (bâtiment) : on bloque si on touche les bords de l'intérieur
            wall_margin = 1.0
            at_edge = (
                px < self.x - half_w + wall_margin or 
                px > self.x + half_w - wall_margin or 
                pz < self.z - half_d + wall_margin or 
                pz > self.z + half_d - wall_margin
            )
            
            if at_edge:
                # Porte : Bord Sud (z max), au centre (largeur 5m)
                is_door = (pz > self.z + half_d - wall_margin) and (abs(px - self.x) < 2.5)
                if not is_door:
                    return True
            
        return False


MAX_SPEED_UNITS_PER_S = 15.0
BOUNDS_HALF = 60000.0 # Augmenté pour le continent (102km)
NPC_CONVERSATION_RESUME_DELAY_S = 120.0


class GameState:
    def __init__(self) -> None:
        self.planet = PlanetConfig(id="terre1", label="Terre1")
        self.time = TimeManager()
        self.entities: dict[str, Entity] = {}
        self.locations: list[dict[str, Any]] = []
        # Phase 2 (réconciliation) : commits idempotents (trace_id) enregistrés en mémoire.
        self._seen_commit_trace_ids: set[str] = set()
        self._npc_commit_flags: dict[str, dict[str, Any]] = {}
        self._npc_reputation: dict[str, int] = {}
        # Gameplay (v1+) : jauges PNJ modifiables via commits (bornées 0–1), persistées.
        self._npc_gauges: dict[str, dict[str, float]] = {}
        
        # Obstacles du décor
        self.obstacles: list[StaticObstacle] = []
        # Rampes verticales (Escaliers)
        self.vertical_ramps = [
            # Auberge: Zone d'escalier vers l'étage
            {"x": -25, "z": -45, "w": 6, "d": 6, "y_start": 0, "y_end": 4}
        ]
        
        self._load_world_data()

    def _load_world_data(self) -> None:
        # Tente de charger les données réelles depuis le seed du mmo_server
        paths = [
            "../mmo_server/world/seed_data/world_initial.json",
            "../../mmo_server/world/seed_data/world_initial.json",
            "/opt/LBG_IA_MMO/mmo_server/world/seed_data/world_initial.json",
            "world_initial.json"
        ]
        seed_path = None
        for p in paths:
            if os.path.exists(p):
                seed_path = p
                break

        if seed_path:
            try:
                import random
                with open(seed_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                loc_coords = {}
                # Charger les Lieux (Locations)
                for loc in data.get("locations", []):
                    geom = loc.get("geometry", {})
                    coords = geom.get("coordinates", {})
                    if "x" in coords and "y" in coords:
                        # Calcul des dimensions basées sur la surface si width/height manquent
                        surface = float(geom.get("surface_m2", 64.0))
                        side = math.sqrt(surface)
                        w = float(geom.get("width", side))
                        h = float(geom.get("height", side))
                        
                        l_data = {
                            "id": loc["id"],
                            "name": loc["name"],
                            "type": loc["type"],
                            "x": float(coords["x"]),
                            "y": float(coords.get("z", 0.0)),
                            "z": float(coords["y"]),
                            "w": w,
                            "h": h,
                        }
                        self.locations.append(l_data)
                        loc_coords[loc["id"]] = (l_data["x"], l_data["z"])
                        
                        # Obstacle physique pour les bâtiments (Plein pour éviter de traverser)
                        if loc["type"] in ("building", "house", "shop", "tower", "inn"):
                            self.obstacles.append(StaticObstacle(
                                l_data["x"], l_data["z"], 
                                width=l_data["w"], depth=l_data["h"], 
                                kind="box", hollow=False
                            ))

                # Charger les NPCs
                for npc_data in data.get("npcs", []):
                    sit = npc_data.get("situation", {})
                    x_val = sit.get("x")
                    z_val = sit.get("y")
                    
                    if x_val is None or z_val is None:
                        loc_id = sit.get("location")
                        if loc_id in loc_coords:
                            x_val, z_val = loc_coords[loc_id]
                            x_val += random.uniform(-3, 3)
                            z_val += random.uniform(-3, 3)
                        else:
                            x_val, z_val = random.uniform(-20, 20), random.uniform(-20, 20)
                            
                    npc = Entity.new_npc(npc_data["name"], float(x_val), float(z_val), npc_id=npc_data.get("id"))
                    npc.role = npc_data.get("role", "civil")
                    r0 = npc_data.get("race_id")
                    if isinstance(r0, str) and r0.strip():
                        npc.race_id = r0.strip()
                    self.entities[npc.id] = npc
            except Exception as e:
                print(f"Erreur chargement seed: {e}")
                self._seed_npcs()
        else:
            self._seed_npcs()

    def get_npc_commit_flags(self, npc_id: str) -> dict[str, Any]:
        npc_id = (npc_id or "").strip()
        cur = self._npc_commit_flags.get(npc_id)
        return dict(cur) if isinstance(cur, dict) else {}

    def get_npc_reputation(self, npc_id: str) -> int:
        npc_id = (npc_id or "").strip()
        try:
            v = int(self._npc_reputation.get(npc_id, 0))
        except Exception:
            v = 0
        return -100 if v < -100 else 100 if v > 100 else v

    def get_npc_gauges(self, npc_id: str, *, default: dict[str, float] | None = None) -> dict[str, float]:
        npc_id = (npc_id or "").strip()
        cur = self._npc_gauges.get(npc_id)
        if isinstance(cur, dict) and cur:
            out = {}
            for k in ("hunger", "thirst", "fatigue"):
                try:
                    out[k] = float(cur.get(k, 0.0))
                except Exception:
                    out[k] = 0.0
                if out[k] < 0.0:
                    out[k] = 0.0
                if out[k] > 1.0:
                    out[k] = 1.0
            return out
        if isinstance(default, dict):
            return {
                "hunger": float(default.get("hunger", 0.0)),
                "thirst": float(default.get("thirst", 0.0)),
                "fatigue": float(default.get("fatigue", 0.0)),
            }
        return {"hunger": 0.0, "thirst": 0.0, "fatigue": 0.0}

    def _apply_aid_deltas(self, *, npc_id: str, hunger_delta: float, thirst_delta: float, fatigue_delta: float) -> None:
        # Init jauges si absentes : base 0–1 (déjà clamp).
        cur = self.get_npc_gauges(npc_id)
        nxt = {
            "hunger": cur["hunger"] + float(hunger_delta),
            "thirst": cur["thirst"] + float(thirst_delta),
            "fatigue": cur["fatigue"] + float(fatigue_delta),
        }
        for k in ("hunger", "thirst", "fatigue"):
            v = nxt[k]
            if v < 0.0:
                v = 0.0
            if v > 1.0:
                v = 1.0
            nxt[k] = float(v)
        self._npc_gauges[npc_id] = nxt

    def _apply_reputation_delta(self, *, npc_id: str, delta: int) -> None:
        cur = self.get_npc_reputation(npc_id)
        nxt = cur + int(delta)
        if nxt < -100:
            nxt = -100
        if nxt > 100:
            nxt = 100
        self._npc_reputation[npc_id] = int(nxt)

    def _validate_commit_flags(self, flags: dict[str, Any] | None) -> tuple[dict[str, Any] | None, str | None]:
        """
        Validation "liste blanche" (phase 2).
        On reste volontairement minimal et stable : l'autorité jeu filtre ce qui est persisté.
        """
        if flags is None:
            return None, None
        if not isinstance(flags, dict):
            return None, "flags must be a dict"
        if not flags:
            return None, None

        # Anti-abus : bornes simples (LAN, mais on protège des payloads accidentels).
        if len(flags) > 12:
            return None, "too many flags"

        allowed: dict[str, tuple[type, ...]] = {
            # Quêtes / RP
            "quest_accepted": (bool,),
            "quest_completed": (bool,),
            "quest_id": (str,),
            "quest_step": (int,),
            # Dialogue / état RP
            "mood": (str,),
            "rp_tone": (str,),
            # Réputation locale (v2+) : variation bornée appliquée par le serveur.
            "reputation_delta": (int,),
            # Gameplay v1 (aid) : deltas bornés (appliqués sur les jauges stockées côté serveur WS).
            "aid_hunger_delta": (int, float),
            "aid_thirst_delta": (int, float),
            "aid_fatigue_delta": (int, float),
            "aid_reputation_delta": (int,),
        }

        cleaned: dict[str, Any] = {}
        for k, v in flags.items():
            if not isinstance(k, str) or not k.strip():
                return None, "invalid flag key"
            key = k.strip()
            if len(key) > 40:
                return None, "flag key too long"
            if key not in allowed:
                return None, f"unsupported flag: {key}"
            if not isinstance(v, allowed[key]):
                return None, f"invalid type for {key}"
            if isinstance(v, str) and not v.strip():
                return None, f"empty value for {key}"
            if isinstance(v, str):
                vv = v.strip()
                if len(vv) > 120:
                    return None, f"value too long for {key}"
                cleaned[key] = vv
            elif key == "quest_step":
                # bornes simples
                vi = int(v)
                if vi < 0 or vi > 10_000:
                    return None, f"invalid value for {key}"
                cleaned[key] = vi
            elif key == "reputation_delta":
                di = int(v)
                if di < -100 or di > 100:
                    return None, f"invalid value for {key}"
                cleaned[key] = di
            elif key.startswith("aid_") and key.endswith("_delta"):
                if key == "aid_reputation_delta":
                    di = int(v)
                    if di < -100 or di > 100:
                        return None, f"invalid value for {key}"
                    cleaned[key] = di
                else:
                    df = float(v)
                    if df < -1.0 or df > 1.0:
                        return None, f"invalid value for {key}"
                    cleaned[key] = float(df)
            else:
                cleaned[key] = v

        return cleaned, None

    def _seed_npcs(self) -> None:
        # Identifiants stables : alignement avec `fusion_spec_monde.md` (format `npc:...`)
        for npc_id, name, xz, scale, race_id in (
            ("npc:merchant", "Marchand civile", (12.0, -5.0), 1.0, "race:halfblood_khar"),
            ("npc:guard", "Garde poste", (-20.0, 8.0), 1.0, "race:sylven"),
            ("npc:mayor", "Maire", (4.0, 14.0), 1.1, "race:human"),
            ("npc:healer", "Guérisseuse", (-6.0, 10.0), 0.9, "race:fae_lume"),
            ("npc:alchemist", "Alchimiste", (18.0, 9.0), 1.0, "race:tinkling"),
            ("npc:wizard", "Chef Magicien", (-10.0, 20.0), 1.2, "race:human"),
            ("npc:celadon", "Guerrier Celadon", (25.0, -10.0), 1.3, "race:nocthrim"),
            ("npc:mushroom", "Champignon Magique", (0.0, -30.0), 2.5, "race:champi_sapient"),
        ):
            npc = Entity.new_npc(name, xz[0], xz[1], npc_id=npc_id, scale=scale)
            if race_id:
                npc.race_id = race_id
            self.entities[npc.id] = npc

    def get_npc(self, npc_id: str) -> Entity | None:
        ent = self.entities.get(npc_id)
        if ent and ent.kind == "npc":
            return ent
        return None

    def commit_dialogue(
        self,
        *,
        npc_id: str,
        trace_id: str,
        flags: dict[str, Any] | None,
    ) -> tuple[bool, str]:
        """
        Réconciliation minimaliste (phase 2) : accepte un commit "dialogue" pour un PNJ si :
        - npc_id existe
        - trace_id est non vide
        - idempotence : trace_id déjà vu => accepté (noop)
        """
        npc_id = npc_id.strip()
        trace_id = trace_id.strip()
        if not npc_id:
            return False, "npc_id vide"
        if not trace_id:
            return False, "trace_id requis"
        if not self.get_npc(npc_id):
            return False, "npc introuvable"
        if trace_id in self._seen_commit_trace_ids:
            return True, "duplicate (idempotent noop)"
        self._seen_commit_trace_ids.add(trace_id)
        cleaned, err = self._validate_commit_flags(flags)
        if err:
            return False, err
        if isinstance(cleaned, dict) and cleaned:
            # Effet de bord contrôlé : réputation locale.
            if "reputation_delta" in cleaned:
                try:
                    self._apply_reputation_delta(npc_id=npc_id, delta=int(cleaned["reputation_delta"]))
                except Exception:
                    pass
            # Gameplay v1 : jauges + réputation via keys aid_*
            if any(k.startswith("aid_") for k in cleaned.keys()):
                try:
                    self._apply_aid_deltas(
                        npc_id=npc_id,
                        hunger_delta=float(cleaned.get("aid_hunger_delta", 0.0) or 0.0),
                        thirst_delta=float(cleaned.get("aid_thirst_delta", 0.0) or 0.0),
                        fatigue_delta=float(cleaned.get("aid_fatigue_delta", 0.0) or 0.0),
                    )
                except Exception:
                    pass
                if "aid_reputation_delta" in cleaned:
                    try:
                        self._apply_reputation_delta(npc_id=npc_id, delta=int(cleaned["aid_reputation_delta"]))
                    except Exception:
                        pass
            cur = self._npc_commit_flags.get(npc_id) or {}
            # Merge léger : dernier write gagne (on n'expose pas les clés aid_* dans world_flags)
            for k, v in cleaned.items():
                if isinstance(k, str) and k.startswith("aid_"):
                    continue
                cur[k] = v
            self._npc_commit_flags[npc_id] = cur
        return True, "accepted"

    def freeze_npc_and_face(self, npc_id: str, player_id: str, duration: float = NPC_CONVERSATION_RESUME_DELAY_S) -> None:
        npc = self.get_npc(npc_id)
        player = self.entities.get(player_id)
        if not npc or not player:
            return
        
        # Calcul de l'angle vers le joueur
        dx = player.x - npc.x
        dz = player.z - npc.z
        
        # En Godot/Maths standards, atan2(dx, dz) donne l'angle sur le plan horizontal
        npc.ry = math.atan2(dx, dz)
        npc.busy_timer = duration
        
        # Stopper net la vitesse pour éviter que l'inertie ne continue
        npc.vx = npc.vy = npc.vz = 0.0

    def export_commit_state(self) -> tuple[set[str], dict[str, dict[str, Any]], dict[str, int], dict[str, dict[str, float]]]:
        return (
            set(self._seen_commit_trace_ids),
            dict(self._npc_commit_flags),
            dict(self._npc_reputation),
            dict(self._npc_gauges),
        )

    def import_commit_state(
        self,
        *,
        seen_trace_ids: set[str],
        npc_flags: dict[str, dict[str, Any]],
        npc_reputation: dict[str, int] | None = None,
        npc_gauges: dict[str, dict[str, float]] | None = None,
    ) -> None:
        self._seen_commit_trace_ids = {t for t in seen_trace_ids if isinstance(t, str) and t.strip()}
        out_flags: dict[str, dict[str, Any]] = {}
        for k, v in npc_flags.items():
            if isinstance(k, str) and k.strip() and isinstance(v, dict):
                out_flags[k.strip()] = v
        self._npc_commit_flags = out_flags
        rep_out: dict[str, int] = {}
        if isinstance(npc_reputation, dict):
            for k, v in npc_reputation.items():
                if isinstance(k, str) and k.strip():
                    try:
                        rep_out[k.strip()] = int(v)
                    except Exception:
                        continue
        self._npc_reputation = rep_out
        gauges_out: dict[str, dict[str, float]] = {}
        if isinstance(npc_gauges, dict):
            for k, v in npc_gauges.items():
                if not (isinstance(k, str) and k.strip() and isinstance(v, dict)):
                    continue
                out = {}
                for gk in ("hunger", "thirst", "fatigue"):
                    try:
                        gf = float(v.get(gk, 0.0))
                    except Exception:
                        gf = 0.0
                    if gf < 0.0:
                        gf = 0.0
                    if gf > 1.0:
                        gf = 1.0
                    out[gk] = float(gf)
                gauges_out[k.strip()] = out
        self._npc_gauges = gauges_out

    def add_player(self, name: str) -> Entity:
        p = Entity.new_player(name)
        # Spawn au centre de la place (au Sud de l'Hôtel de Ville déplacé)
        # Altitude 0.0 pour être au niveau du sol
        p.x, p.y, p.z = 0.0, 0.0, -20.0
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
            
        # Initialisation des stats par défaut pour le joueur
        if not getattr(ent, "stats", None):
            ent.stats = {
                "hp": 100, "hp_max": 100,
                "mp": 50, "mp_max": 50,
                "stamina": 100, "stamina_max": 100,
                "level": 1, "exp": 0
            }

        # Calcul du delta conscient du Wrap-Around (102400m)
        dx = x - ent.x
        if dx > 51200: dx -= 102400
        elif dx < -51200: dx += 102400
        
        dx, dy, dz = dx * 20.0, (y - ent.y) * 20.0, (z - ent.z) * 20.0
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        
        if dist < 0.01:
            ent.vx = ent.vy = ent.vz = 0.0
            return

        limit = MAX_SPEED_UNITS_PER_S
        if dist > limit:
            scale = limit / dist
            dx, dy, dz = dx * scale, dy * scale, dz * scale
            
        ent.vx, ent.vy, ent.vz = dx, dy, dz
        
        # Consommation d'endurance
        if dist > 5.0:
            ent.stats["stamina"] = max(0, ent.stats["stamina"] - 0.05)
        else:
            ent.stats["stamina"] = min(ent.stats["stamina_max"], ent.stats["stamina"] + 0.1)

    def tick(self, dt: float) -> None:
        self.time.advance(dt)
        for ent in self.entities.values():
            bt = float(getattr(ent, "busy_timer", 0.0) or 0.0)
            if bt > 0:
                ent.busy_timer = bt - float(dt)
                if ent.kind == "npc":
                    ent.vx = ent.vy = ent.vz = 0.0
            
            if ent.kind == "npc" and float(getattr(ent, "busy_timer", 0.0) or 0.0) <= 0.0:
                self._npc_step(ent, dt)
            
            # Gestion des escaliers (Rampes)
            for ramp in self.vertical_ramps:
                if (ramp["x"] - ramp["w"]/2 <= ent.x <= ramp["x"] + ramp["w"]/2 and
                    ramp["z"] - ramp["d"]/2 <= ent.z <= ramp["z"] + ramp["d"]/2):
                    
                    # On ajuste Y vers l'étage cible selon le mouvement horizontal
                    # Si on avance vers l'intérieur de la zone (z décroissant ou croissant selon le sens)
                    target_y = ramp["y_end"] if (ent.vz > 0.1 or ent.vx > 0.1) else ramp["y_start"]
                    dy = target_y - ent.y
                    if abs(dy) > 0.1:
                        ent.y += (dy / abs(dy)) * 2.0 * dt # Monte à 2m/s
            
            # Prédiction de la prochaine position
            nx = ent.x + ent.vx * dt
            nz = ent.z + ent.vz * dt
            
            # Vérification des obstacles (Joueurs et PNJ)
            blocked = False
            for obs in self.obstacles:
                if obs.is_inside(nx, nz, margin=0.5):
                    blocked = True
                    break
            
            if not blocked:
                ent.x = nx
                ent.z = nz
            else:
                # En cas de blocage, on annule la vitesse pour ne pas forcer
                ent.vx = 0.0
                ent.vz = 0.0

            ent.y += ent.vy * dt
            # World Wrap Horizontal (X) - 102.4km
            if ent.x > 51200:
                ent.x -= 102400
            elif ent.x < -51200:
                ent.x += 102400
            
            # Clamp Vertical (Z) - 51.2km
            ent.z = max(-25600, min(25600, ent.z))
            # Clamp Altitude (Y)
            ent.y = max(-50.0, min(50.0, ent.y))
            ent.vx *= 0.6
            ent.vy *= 0.6
            ent.vz *= 0.6

    def _npc_step(self, npc: Entity, dt: float) -> None:
        # Comportements spécialisés par rôle ou nom
        if "Garde" in npc.name or npc.role == "guard":
            self._guard_behavior(npc, dt)
        else:
            # PNJ basiques : lente dérive + rebond symbolique sur les bords
            seed = sum(ord(c) for c in npc.id) % 314
            noise = math.sin(self.time.world_time_s * 0.3 + seed) * 2.0
            npc.vx += noise * dt
            npc.vz += math.cos(self.time.world_time_s * 0.25) * 1.5 * dt
            sp = math.sqrt(npc.vx**2 + npc.vz**2)
            cap = 2.0
            if sp > cap:
                npc.vx, npc.vz = npc.vx / sp * cap, npc.vz / sp * cap

    def _get_location_coords(self, loc_id: str) -> tuple[float, float]:
        """Retourne les coordonnées (x, z) d'un lieu par son ID."""
        for loc in self.locations:
            if loc["id"] == loc_id:
                return loc["x"], loc["z"]
        
        # Fallbacks basés sur world_initial.json si non chargé
        defaults = {
            "porte_nord": (0.0, 180.0),
            "porte_sud": (0.0, -180.0),
            "muraille_est": (180.0, 0.0),
            "muraille_ouest": (-180.0, 0.0),
            "place_d_armes": (0.0, 0.0),
            "caserne": (-100.0, 100.0),
            "hotel_de_ville": (0.0, 50.0),
        }
        return defaults.get(loc_id, (0.0, 0.0))

    def _guard_behavior(self, npc: Entity, dt: float) -> None:
        # Configuration des patrouilles (dynamique via IDs de lieux)
        patrol_points = ["porte_nord", "place_d_armes", "muraille_est", "place_d_armes", "muraille_ouest", "place_d_armes", "porte_sud", "place_d_armes"]
        
        # Cas spécial pour le Capitaine (npc:guard_1) : il reste souvent près de l'Hôtel de Ville
        if npc.id == "npc:guard_1":
            patrol_points = ["hotel_de_ville", "place_d_armes"]

        if "patrol_idx" not in npc.stats:
            # Attribution d'un point de départ aléatoire dans la ronde pour éviter les "trains" de gardes
            npc.stats["patrol_idx"] = sum(ord(c) for c in npc.id) % len(patrol_points)
            npc.stats["wait_timer"] = (sum(ord(c) for c in npc.id) % 5) * 1.0 
            npc.stats["path_type"] = "standard"

        if npc.stats["wait_timer"] > 0:
            npc.stats["wait_timer"] -= dt
            npc.vx = npc.vz = 0
            return

        # Cible actuelle
        loc_id = patrol_points[npc.stats["patrol_idx"]]
        tx, tz = self._get_location_coords(loc_id)
        
        dx, dz = tx - npc.x, tz - npc.z
        dist = math.sqrt(dx*dx + dz*dz)
        
        if dist < 3.0:
            # Arrivé au point.
            # Temps d'attente au point
            wait = 5.0
            if "porte" in loc_id:
                wait = 20.0 # Temps de garde à la porte
            elif "hotel" in loc_id:
                wait = 60.0 # Le Capitaine reste longtemps à l'Hôtel de Ville
            
            npc.stats["wait_timer"] = wait
            npc.stats["patrol_idx"] = (npc.stats["patrol_idx"] + 1) % len(patrol_points)
        else:
            # On avance vers la cible
            # Vitesse de marche (un peu plus lent pour les gardes pour paraître discipliné)
            speed = 3.5 
            npc.vx = (dx / dist) * speed
            npc.vz = (dz / dist) * speed
            # Rotation vers la cible
            npc.ry = math.atan2(dx, dz)

    def entity_snapshots(self) -> list[dict]:
        out: list[dict] = []
        for ent in self.entities.values():
            snap = ent.to_snapshot()
            if ent.kind == "npc":
                flags = self.get_npc_commit_flags(ent.id)
                snap["world_state"] = {
                    "reputation": int(self.get_npc_reputation(ent.id)),
                    "gauges": self.get_npc_gauges(ent.id),
                    "flags": flags,
                }
            out.append(snap)
        return out
