#!/usr/bin/env python3
"""TRE de test incremental pour isoler crash client (patch_murrik)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "client_patch"))
from tre_writer import build_tre  # noqa: E402

MOD = Path("/mnt/j/swgemu/MOD_LBG")
BACKUP = MOD / "texture_backup_vanilla"
OUT = Path("/mnt/j/swgemu/clients/prime-lbg")

PRESETS = {
    "bth_sat_tex": [
        "appearance/bth_f.sat",
        "appearance/bth_m.sat",
        "texture/bth_f_face.dds",
        "texture/bth_m_face.dds",
    ],
    "iff_sat": [
        "appearance/bth_f.sat",
        "appearance/bth_m.sat",
        "object/creature/player/shared_bothan_female.iff",
        "object/creature/player/shared_bothan_male.iff",
    ],
    "sat_only": [
        "appearance/bth_f.sat",
        "appearance/bth_m.sat",
    ],
    "iff_only": [
        "object/creature/player/shared_bothan_female.iff",
        "object/creature/player/shared_bothan_male.iff",
    ],
    "tex_vanilla": [f"texture/{p.name}" for p in sorted((BACKUP).glob("bth_*.dds"))],
    "tex_face_f": ["texture/bth_f_face.dds"],
}


def collect(paths: list[str], use_vanilla_tex: bool) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for rel in paths:
        rel = rel.lower()
        if rel.startswith("texture/") and use_vanilla_tex:
            src = BACKUP / Path(rel).name
        else:
            src = MOD / rel
        if not src.is_file():
            raise SystemExit(f"manquant: {src}")
        files[rel] = src.read_bytes()
    return files


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("preset", choices=sorted(PRESETS.keys()))
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--vanilla-tex", action="store_true", help="textures depuis backup")
    args = p.parse_args()
    out = args.out or OUT / f"patch_murrik_test_{args.preset}.tre"
    files = collect(PRESETS[args.preset], args.vanilla_tex)
    build_tre(out, files)
    print(f"OK {out} ({len(files)} fichiers)")


if __name__ == "__main__":
    main()
