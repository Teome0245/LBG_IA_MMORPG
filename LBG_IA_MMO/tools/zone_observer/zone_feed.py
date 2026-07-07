#!/usr/bin/env python3
"""
Observateur zone Prime — lecture snapshots ia_bridge (M1).

Affiche joueurs + PNJ pilotes depuis player_snapshots.json et npc_snapshots.json.
Peut exporter un flux JSON pour prime-client (Godot).

Usage :
  python3 tools/zone_observer/zone_feed.py --once
  python3 tools/zone_observer/zone_feed.py --watch --interval 1
  python3 tools/zone_observer/zone_feed.py --watch --json-out /tmp/zone_feed.json
  IA_BRIDGE_DIR=/opt/lbg-new-mmo-clean/MMOCoreORB/bin/ia_bridge python3 ...
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.lbg_gateway.zone_players import build_zone_player_entities  # noqa: E402

from godot_bridge import GodotBridge  # noqa: E402

DEFAULT_BRIDGE = ROOT / "content/core3/ia_bridge"
DEFAULT_LOCATIONS = ROOT / "content/core3/locations"


@dataclass
class ZoneEntity:
    id: str
    kind: str
    name: str
    x: float
    y: float
    z: float
    online: bool = True
    stale: bool = False
    zone: str = ""

    def distance_to(self, ox: float, oz: float) -> float:
        return math.hypot(self.x - ox, self.z - oz)


def _bridge_dir() -> Path:
    raw = os.environ.get("IA_BRIDGE_DIR", "").strip()
    return Path(raw) if raw else DEFAULT_BRIDGE


def sync_bridge_from_vm(
    *,
    host: str,
    user: str = "lbg",
    remote_dir: str = "/opt/lbg-new-mmo-clean/MMOCoreORB/bin/ia_bridge",
    local_dir: Path | None = None,
) -> Path:
    """Copie player_snapshots.json (+ npc) depuis la VM Prime via scp."""
    dest = local_dir or Path(os.environ.get("LOCAL_BRIDGE_DIR", "/tmp/prime_ia_bridge"))
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("player_snapshots.json", "npc_snapshots.json"):
        remote = f"{user}@{host}:{remote_dir}/{name}"
        subprocess.run(
            ["scp", "-q", "-o", "ConnectTimeout=5", remote, str(dest / name)],
            check=False,
            timeout=15,
        )
    return dest


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _npc_entities(npc_path: Path, max_age_s: float) -> list[ZoneEntity]:
    doc = _load_json(npc_path)
    now = time.time()
    out: list[ZoneEntity] = []
    for key, snap in doc.items():
        if not isinstance(snap, dict):
            continue
        x, y, z = snap.get("x"), snap.get("y"), snap.get("z")
        if x is None or y is None or z is None:
            continue
        ts = snap.get("ts")
        stale = False
        if isinstance(ts, (int, float)):
            stale = (now - float(ts)) > max_age_s
        online = snap.get("online")
        if online is False:
            continue
        name = str(
            snap.get("display_name")
            or snap.get("name")
            or snap.get("pilot_id")
            or key
        ).strip()
        out.append(
            ZoneEntity(
                id=f"npc:{key}",
                kind="npc",
                name=name,
                x=float(x),
                y=float(y),
                z=float(z),
                online=True,
                stale=stale,
                zone=str(snap.get("zone", "")),
            )
        )
    return out


def _player_entities(player_path: Path, locations_dir: Path) -> list[ZoneEntity]:
    rows = build_zone_player_entities(
        snapshots_path=player_path,
        locations_dir=str(locations_dir),
    )
    out: list[ZoneEntity] = []
    for row in rows:
        pos = row.get("pos") or [0, 0, 0]
        if len(pos) < 3:
            continue
        out.append(
            ZoneEntity(
                id=str(row.get("id", row.get("name", "?"))),
                kind="player",
                name=str(row.get("name", "?")),
                x=float(pos[0]),
                y=float(pos[1]),
                z=float(pos[2]),
                online=row.get("online", True) is not False,
                zone=str(row.get("zone", "")),
            )
        )
    return out


def collect_entities(
    *,
    bridge_dir: Path | None = None,
    locations_dir: Path | None = None,
    max_age_s: float = 8.0,
    players_only: bool = False,
) -> list[ZoneEntity]:
    bridge = bridge_dir or _bridge_dir()
    loc = locations_dir or DEFAULT_LOCATIONS
    player_path = bridge / "player_snapshots.json"
    npc_path = bridge / "npc_snapshots.json"
    entities = _player_entities(player_path, loc)
    if not players_only:
        entities.extend(_npc_entities(npc_path, max_age_s))
    return entities


def pick_origin(entities: list[ZoneEntity], ox: float | None, oz: float | None) -> tuple[float, float]:
    if ox is not None and oz is not None:
        return ox, oz
    players = [e for e in entities if e.kind == "player"]
    if players:
        return players[0].x, players[0].z
    if entities:
        return entities[0].x, entities[0].z
    return 3520.0, -4800.0


def sort_entities(
    entities: list[ZoneEntity],
    origin_x: float,
    origin_z: float,
) -> list[ZoneEntity]:
    return sorted(entities, key=lambda e: e.distance_to(origin_x, origin_z))


def format_table(entities: list[ZoneEntity], origin_x: float, origin_z: float) -> str:
    if not entities:
        return "(aucune entité — snapshots vides ou absents)"
    lines = [
        f"{'kind':<7} {'name':<16} {'x':>9} {'y':>6} {'z':>9} {'dist':>8} {'zone':<10} flags",
        "-" * 72,
    ]
    for e in entities:
        flags = []
        if e.stale:
            flags.append("stale")
        if not e.online:
            flags.append("off")
        lines.append(
            f"{e.kind:<7} {e.name[:16]:<16} {e.x:9.1f} {e.y:6.1f} {e.z:9.1f} "
            f"{e.distance_to(origin_x, origin_z):8.1f} {e.zone[:10]:<10} {','.join(flags)}"
        )
    return "\n".join(lines)


def export_payload(
    entities: list[ZoneEntity],
    origin_x: float,
    origin_z: float,
) -> dict[str, Any]:
    return {
        "ts": time.time(),
        "origin": {"x": origin_x, "z": origin_z},
        "entities": [asdict(e) for e in entities],
    }


def run_once(
    args: argparse.Namespace,
    godot: GodotBridge | None = None,
) -> list[ZoneEntity]:
    bridge_dir = Path(args.bridge_dir) if args.bridge_dir else None
    if args.prime_host:
        bridge_dir = sync_bridge_from_vm(
            host=args.prime_host,
            user=args.prime_user,
            remote_dir=args.remote_bridge_dir,
            local_dir=Path(args.local_bridge_dir) if args.local_bridge_dir else None,
        )
    entities = collect_entities(
        bridge_dir=bridge_dir,
        locations_dir=Path(args.locations_dir) if args.locations_dir else None,
        max_age_s=args.max_age,
        players_only=args.players_only,
    )
    ox, oz = pick_origin(entities, args.origin_x, args.origin_z)
    entities = sort_entities(entities, ox, oz)
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(export_payload(entities, ox, oz), indent=2) + "\n",
            encoding="utf-8",
        )
    if godot is not None:
        pkt = godot.sync_all(entities)
        if pkt and not args.quiet:
            print(f"  → Godot UDP : {pkt} paquet(s)")
    if not args.quiet:
        print(format_table(entities, ox, oz))
        print(f"\n{len(entities)} entité(s)  origine=({ox:.1f}, {oz:.1f})")
    return entities


def main() -> int:
    parser = argparse.ArgumentParser(description="Observateur zone Prime (snapshots ia_bridge)")
    parser.add_argument("--bridge-dir", type=Path, help="Dossier ia_bridge (défaut: content/core3/ia_bridge)")
    parser.add_argument("--locations-dir", type=Path, help="Dossier content/core3/locations")
    parser.add_argument("--origin-x", type=float, default=None, help="Origine tri distance (X)")
    parser.add_argument("--origin-z", type=float, default=None, help="Origine tri distance (Z)")
    parser.add_argument("--max-age", type=float, default=8.0, help="Âge max snapshot PNJ (s)")
    parser.add_argument("--track-players", default="Lia,Nix,Mira,Gally,Bot_IA",
                        help="Joueurs suivis (LBG_GATEWAY_TRACK_PLAYERS)")
    parser.add_argument("--once", action="store_true", help="Un seul affichage puis sortie")
    parser.add_argument("--watch", action="store_true", help="Boucle d'affichage")
    parser.add_argument("--interval", type=float, default=1.0, help="Intervalle --watch (s)")
    parser.add_argument("--json-out", type=Path, help="Écrit le flux JSON (pour prime-client)")
    parser.add_argument("--godot-port", type=int, default=0,
                        help="Port UDP Godot NetworkBridge (ex. 12345)")
    parser.add_argument("--godot-host", default="",
                        help="Hôte Godot (défaut: auto WSL→Windows, sinon 127.0.0.1)")
    parser.add_argument("--mirror", action="store_true",
                        help="Raccourci M3 : --watch --godot-port 12345 --interval 0.5")
    parser.add_argument("--prime-host", default=os.environ.get("PRIME_HOST", "").strip(),
                        help="VM Prime : scp ia_bridge avant chaque tick (ex. 192.168.0.246)")
    parser.add_argument("--prime-user", default=os.environ.get("PRIME_USER", "lbg"),
                        help="Utilisateur SSH VM Prime")
    parser.add_argument("--remote-bridge-dir",
                        default="/opt/lbg-new-mmo-clean/MMOCoreORB/bin/ia_bridge",
                        help="Chemin ia_bridge sur la VM")
    parser.add_argument("--local-bridge-dir", type=Path,
                        default=Path(os.environ.get("LOCAL_BRIDGE_DIR", "/tmp/prime_ia_bridge")),
                        help="Copie locale des snapshots VM")
    parser.add_argument("--players-only", action="store_true",
                        help="Joueurs suivis uniquement (pas les PNJ ia_bridge)")
    parser.add_argument("--quiet", action="store_true", help="Pas de tableau terminal")
    args = parser.parse_args()

    if args.mirror:
        if not args.once:
            args.watch = True
        if args.godot_port == 0:
            args.godot_port = 12345
        if args.interval == 1.0:
            args.interval = 0.5
        if not args.prime_host:
            args.prime_host = os.environ.get("PRIME_HOST", "192.168.0.246")
        args.players_only = True
        default_bridge = Path(os.environ.get("LOCAL_BRIDGE_DIR", "/tmp/prime_ia_bridge"))
        cache_raw = os.environ.get("PRIME_CLIENT_CACHE", "").strip()
        if cache_raw:
            cache = Path(cache_raw).expanduser()
        else:
            pc = os.environ.get("PRIME_CLIENT", "").strip()
            cache = Path(pc) / "cache" if pc else default_bridge
        cache.mkdir(parents=True, exist_ok=True)
        if not args.json_out:
            args.json_out = cache / "zone_feed.json"
        if args.local_bridge_dir == default_bridge:
            args.local_bridge_dir = cache
        if os.environ.get("MIRROR_PLAYERS_ONLY", "").strip().lower() in ("0", "false", "no"):
            args.players_only = False

    if args.track_players:
        os.environ["LBG_GATEWAY_TRACK_PLAYERS"] = args.track_players

    if not args.once and not args.watch:
        args.once = True

    godot_host = args.godot_host.strip() or None
    godot = GodotBridge(args.godot_port, host=godot_host) if args.godot_port > 0 else None

    if args.watch:
        try:
            if godot and not args.quiet:
                print(f"# M3 mirror → Godot {godot.host}:{args.godot_port}  json={args.json_out or '-'}")
            while True:
                if not args.quiet:
                    print("\033[2J\033[H", end="")
                    print(f"# zone_feed  {time.strftime('%H:%M:%S')}  bridge={_bridge_dir()}\n")
                run_once(args, godot)
                time.sleep(max(0.2, args.interval))
        except KeyboardInterrupt:
            print("\n(arrêt)")
            if godot:
                godot.close()
            return 0

    run_once(args, godot)
    if godot:
        godot.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
