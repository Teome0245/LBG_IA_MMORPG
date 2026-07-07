#!/usr/bin/env python3
"""M4.4 — World Snapshot .ws → JSON pour prime-client (Godot)."""
from __future__ import annotations

import argparse
import json
import os
import socket
import struct
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = (
    Path(os.environ.get("PRIME_CLIENT", Path.home() / "projects/new_mmo/prime-client"))
    / "assets/maps"
)

# Réutilise le parseur éprouvé de client-prime-lbg
_CLIENT_ROOT = Path(os.environ.get("NEW_MMO_ROOT", Path.home() / "projects/new_mmo"))
_CLIENT_LBG = _CLIENT_ROOT / "client-prime-lbg"
if _CLIENT_LBG.is_dir():
    sys.path.insert(0, str(_CLIENT_LBG))

try:
    from ws_parser import parse_ws, send_to_godot  # type: ignore
except ImportError:
    parse_ws = None  # type: ignore
    send_to_godot = None  # type: ignore


def filter_mos_eisley(objects: list[dict[str, Any]], radius: float = 900.0) -> list[dict[str, Any]]:
    """Garde les objets autour de Mos Eisley (3520, -4800)."""
    cx, cz = 3520.0, -4800.0
    out: list[dict[str, Any]] = []
    for o in objects:
        dx = float(o.get("x", 0)) - cx
        dz = float(o.get("z", 0)) - cz
        if dx * dx + dz * dz <= radius * radius:
            out.append(o)
    return out


def export_ws(
    ws_path: Path,
    out_path: Path,
    *,
    mos_only: bool = True,
    max_objects: int = 0,
    godot_port: int = 0,
    godot_host: str = "127.0.0.1",
) -> int:
    if parse_ws is None:
        print("ERREUR: ws_parser introuvable (client-prime-lbg/ws_parser.py)", file=sys.stderr)
        return 1
    objects = parse_ws(str(ws_path))
    if mos_only:
        objects = filter_mos_eisley(objects)
    if max_objects > 0:
        objects = objects[:max_objects]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(objects, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK {len(objects)} objet(s) → {out_path}")
    if godot_port > 0:
        pkt = json.dumps({"t": "ws", "path": str(out_path.resolve())}).encode("utf-8")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(pkt, (godot_host, godot_port))
        sock.close()
        print(f"  → Godot {godot_host}:{godot_port}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Export .ws SWG → JSON Godot")
    parser.add_argument("ws_file", type=Path, nargs="?", help="Fichier snapshot (ex. tatooine.ws)")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUT / "mos_eisley_ws.json")
    parser.add_argument("--all-planet", action="store_true", help="Toute la planète (pas filtre Mos Eisley)")
    parser.add_argument("--max", type=int, default=0)
    parser.add_argument("--godot-port", type=int, default=0)
    parser.add_argument("--godot-host", default=os.environ.get("GODOT_HOST", "127.0.0.1"))
    args = parser.parse_args()
    if not args.ws_file:
        print("Usage: ws_to_json.py /chemin/tatooine.ws")
        print("  Extrait depuis TRE serveur: snapshot/tatooine.ws")
        return 2
    if not args.ws_file.is_file():
        print(f"Fichier absent: {args.ws_file}", file=sys.stderr)
        return 1
    return export_ws(
        args.ws_file,
        args.output,
        mos_only=not args.all_planet,
        max_objects=args.max,
        godot_port=args.godot_port,
        godot_host=args.godot_host,
    )


if __name__ == "__main__":
    raise SystemExit(main())
