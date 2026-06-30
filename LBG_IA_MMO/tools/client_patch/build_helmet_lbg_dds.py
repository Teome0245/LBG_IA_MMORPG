#!/usr/bin/env python3
"""
Produit texture/helmet_rebel_ace_sm.dds (128×64 DXT5 + mipmaps) pour l'écran login.

Le CSHD ui_spacestation pointe vers helmet_rebel_ace_sm.dds : on remplace uniquement
le mip 0 (visuel) et on conserve les mips inférieurs du vanilla (taille exacte requise).

Usage :
  python3 tools/client_patch/build_helmet_lbg_dds.py
  python3 tools/client_patch/build_helmet_lbg_dds.py --vanilla /chemin/helmet.dds -o out.dds
"""
from __future__ import annotations

import argparse
import io
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "client_patch"))

from build_lbg_dds import (  # noqa: E402
    build_helmet_lbg_dds,
    extract_texture_from_tre,
)

DEFAULT_TRE = Path("/mnt/j/swgemu/clients/prime-lbg/patch_11_03.tre")
HELMET_PATH = "texture/helmet_rebel_ace_sm.dds"
WIDTH, HEIGHT = 128, 64


def extract_helmet_from_tre(tre_path: Path) -> bytes:
    return extract_texture_from_tre(tre_path, HELMET_PATH)


def main() -> int:
    parser = argparse.ArgumentParser(description="Génère helmet_rebel_ace_sm.dds branding LBG")
    parser.add_argument("--vanilla", type=Path, help="DDS vanilla (sinon extrait du TRE)")
    parser.add_argument("--tre", type=Path, default=DEFAULT_TRE)
    parser.add_argument("-o", "--output", type=Path, help="Fichier DDS de sortie")
    args = parser.parse_args()

    if args.vanilla:
        vanilla = args.vanilla.read_bytes()
    else:
        if not args.tre.is_file():
            raise SystemExit(f"TRE introuvable: {args.tre}")
        vanilla = extract_helmet_from_tre(args.tre)

    out_bytes = build_helmet_lbg_dds(vanilla)
    if len(out_bytes) != len(vanilla):
        raise SystemExit(f"taille sortie {len(out_bytes)} != vanilla {len(vanilla)}")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(out_bytes)
        print(f"OK {args.output} ({len(out_bytes)} o)")
    else:
        sys.stdout.buffer.write(out_bytes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
