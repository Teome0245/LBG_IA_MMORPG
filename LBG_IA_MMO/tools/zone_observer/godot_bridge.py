"""Pont UDP JSON vers NetworkBridge Godot (port 12345)."""
from __future__ import annotations

import json
import os
import socket
import zlib
from pathlib import Path
from typing import Any


def entity_oid(entity_id: str) -> int:
    """ID stable partagé avec snapshot_bridge.gd (crc32, pas hash Python)."""
    return zlib.crc32(entity_id.encode("utf-8")) & 0x7FFF_FFFF


def detect_godot_host() -> str:
    """WSL → Godot Windows : IP hôte depuis resolv.conf (pas 127.0.0.1 WSL)."""
    explicit = os.environ.get("GODOT_HOST", "").strip()
    if explicit:
        return explicit
    proc = Path("/proc/version")
    try:
        if proc.is_file() and "microsoft" in proc.read_text(encoding="utf-8", errors="ignore").lower():
            for line in Path("/etc/resolv.conf").read_text(encoding="utf-8", errors="ignore").splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[0] == "nameserver":
                    return parts[1]
    except OSError:
        pass
    return "127.0.0.1"


class GodotBridge:
    def __init__(self, port: int = 12345, host: str | None = None) -> None:
        self.port = port
        self.host = (host or detect_godot_host()).strip() or "127.0.0.1"
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._active = port > 0
        self._known: dict[str, tuple[float, float, float]] = {}

    def _send(self, obj: dict[str, Any]) -> None:
        if not self._active:
            return
        try:
            data = json.dumps(obj, separators=(",", ":")).encode("utf-8")
            self._sock.sendto(data, (self.host, self.port))
        except OSError:
            pass

    def sync_entity(
        self,
        entity_id: str,
        kind: str,
        name: str,
        x: float,
        y: float,
        z: float,
    ) -> bool:
        """Spawn ou move. Retourne True si changement envoyé."""
        pos = (round(x, 3), round(y, 3), round(z, 3))
        oid = entity_oid(entity_id)
        color = "green" if kind == "player" and name.lower() in ("bot_ia", "lia", "nix", "mira") else (
            "blue" if kind == "player" else "orange"
        )
        if entity_id not in self._known:
            self._known[entity_id] = pos
            self._send(
                {
                    "t": "sp",
                    "sid": entity_id,
                    "id": oid,
                    "x": pos[0],
                    "y": pos[1],
                    "z": pos[2],
                    "c": color,
                    "l": name[:20],
                }
            )
            return True
        if self._known[entity_id] != pos:
            self._known[entity_id] = pos
            self._send({"t": "mv", "sid": entity_id, "id": oid, "x": pos[0], "y": pos[1], "z": pos[2]})
            return True
        return False

    def sync_all(self, entities: list[Any]) -> int:
        """Synchronise la liste ; despawn les entités absentes. Retourne nb paquets."""
        seen: set[str] = set()
        sent = 0
        for e in entities:
            seen.add(e.id)
            if self.sync_entity(e.id, e.kind, e.name, e.x, e.y, e.z):
                sent += 1
        for eid in list(self._known.keys()):
            if eid not in seen:
                oid = entity_oid(eid)
                self._send({"t": "dp", "sid": eid, "id": oid})
                del self._known[eid]
                sent += 1
        return sent

    def close(self) -> None:
        self._sock.close()
