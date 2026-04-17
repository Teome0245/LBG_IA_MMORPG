"""État autoritatif du monde — Phase 1."""

from __future__ import annotations

import math
from typing import Any

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
        # Phase 2 (réconciliation) : commits idempotents (trace_id) enregistrés en mémoire.
        self._seen_commit_trace_ids: set[str] = set()
        self._npc_commit_flags: dict[str, dict[str, Any]] = {}
        self._npc_reputation: dict[str, int] = {}
        # Gameplay (v1+) : jauges PNJ modifiables via commits (bornées 0–1), persistées.
        self._npc_gauges: dict[str, dict[str, float]] = {}
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
        for npc_id, name, xz in (
            ("npc:merchant", "Marchand civile", (12.0, -5.0)),
            ("npc:guard", "Garde poste", (-20.0, 8.0)),
            ("npc:mayor", "Maire", (4.0, 14.0)),
            ("npc:healer", "Guérisseuse", (-6.0, 10.0)),
            ("npc:alchemist", "Alchimiste", (18.0, 9.0)),
        ):
            npc = Entity.new_npc(name, xz[0], xz[1], npc_id=npc_id)
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
