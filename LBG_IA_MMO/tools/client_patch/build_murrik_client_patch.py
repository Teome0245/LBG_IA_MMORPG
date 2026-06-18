#!/usr/bin/env python3
"""Construit patch_murrik_00.tre (textures bth_*.dds + SAT aux chemins vanilla).

Ne pas inclure les IFF bothan : le serveur et le client vanilla utilisent
``appearance/bth_f.sat`` / ``appearance/bth_m.sat``. Des IFF pointant vers
``appearance/player/murrik_*.sat`` provoquent un crash au lancement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "client_patch"))

from tre_writer import build_tre  # noqa: E402

# Chemins internes TRE (minuscules, posix)
TEXTURE_GLOB = "bth_*.dds"
INCLUDE_PATHS = (
    "appearance/bth_f.sat",
    "appearance/bth_m.sat",
)


def collect_files(source_root: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    tex_dir = source_root / "texture"
    if not tex_dir.is_dir():
        raise SystemExit(f"Dossier texture introuvable: {tex_dir}")

    for dds in sorted(tex_dir.glob(TEXTURE_GLOB)):
        tre_path = f"texture/{dds.name}".lower()
        files[tre_path] = dds.read_bytes()

    for rel in INCLUDE_PATHS:
        p = source_root / Path(rel)
        if not p.is_file():
            raise SystemExit(f"Fichier requis manquant: {p}")
        files[rel.lower()] = p.read_bytes()

    return files


def main() -> None:
    parser = argparse.ArgumentParser(description="Build patch_murrik_00.tre")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("/mnt/j/swgemu/MOD_LBG"),
        help="Racine MOD_LBG (texture/ + appearance/ + object/)",
    )
    parser.add_argument(
        "--output-tre",
        type=Path,
        default=Path("/mnt/j/swgemu/clients/prime-lbg/patch_murrik_00.tre"),
    )
    parser.add_argument(
        "--metadata-json",
        type=Path,
        default=None,
        help="Optionnel: JSON manifeste (hash, liste fichiers)",
    )
    args = parser.parse_args()

    source = args.source.resolve()
    files = collect_files(source)
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


if __name__ == "__main__":
    main()
