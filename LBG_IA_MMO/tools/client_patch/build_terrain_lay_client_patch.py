#!/usr/bin/env python3
"""TRE client Prime : terrain/poi_*.lay pour le rendu flatten/cuvette (même IFF que le serveur)."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "client_patch"))

from tre_writer import build_tre  # noqa: E402

DEFAULT_LAY_DIR = ROOT / "content/core3/terrain"
DEFAULT_OUT = Path("/mnt/j/swgemu/clients/prime-lbg/patch_terrain_00.tre")
LAY_NAMES = ("poi_small.lay", "poi_medium.lay", "poi_large.lay", "poi_bowl.lay")


def collect_lay_files(lay_dir: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for name in LAY_NAMES:
        path = lay_dir / name
        if not path.is_file():
            raise SystemExit(f"Fichier manquant: {path} — lancer generate_poi_lay.py")
        tre_path = f"terrain/{name}".lower()
        files[tre_path] = path.read_bytes()
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="Build patch_terrain_00.tre (poi lay client)")
    parser.add_argument("--lay-dir", type=Path, default=DEFAULT_LAY_DIR)
    parser.add_argument("--output-tre", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--metadata-json", type=Path, default=None)
    args = parser.parse_args()

    files = collect_lay_files(args.lay_dir.resolve())
    args.output_tre.parent.mkdir(parents=True, exist_ok=True)
    build_tre(args.output_tre, files)

    md5 = hashlib.md5(args.output_tre.read_bytes()).hexdigest()
    meta = {
        "tre": args.output_tre.name,
        "files_count": len(files),
        "md5": md5,
        "paths": sorted(files.keys()),
    }
    print(json.dumps(meta, indent=2))

    if args.metadata_json:
        args.metadata_json.parent.mkdir(parents=True, exist_ok=True)
        args.metadata_json.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    print(f"\nAjouter dans swgemu_live.cfg (priorité haute, ex. 26) :")
    print(f"  searchTree_00_26={args.output_tre.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
