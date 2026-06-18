#!/usr/bin/env python3
"""Remet appearanceFilename bothan sur les chemins vanilla (évite crash client)."""
from __future__ import annotations

import argparse
from pathlib import Path

# Même taille de champ que l’édition SIE « murrik » (30 octets avant le \0XXXX).
REPLACEMENTS = (
    (b"appearance/player/murrik_f.sat", b"appearance/bth_f.sat" + b"\x00" * 10),
    (b"appearance/player/murrik_m.sat", b"appearance/bth_m.sat" + b"\x00" * 10),
)

IFF_FILES = (
    "object/creature/player/shared_bothan_female.iff",
    "object/creature/player/shared_bothan_male.iff",
)


def patch_iff(data: bytes) -> bytes:
    out = data
    changed = False
    for old, new in REPLACEMENTS:
        if old not in out:
            continue
        if len(old) != len(new):
            raise ValueError(f"longueurs différentes ({len(old)} vs {len(new)}): {old!r} -> {new!r}")
        out = out.replace(old, new, 1)
        changed = True
    if not changed and not any(new in out for _, new in REPLACEMENTS):
        raise ValueError("aucun chemin murrik ni bth reconnu")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("/mnt/j/swgemu/MOD_LBG"),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = args.source.resolve()

    for rel in IFF_FILES:
        path = root / rel
        if not path.is_file():
            raise SystemExit(f"manquant: {path}")
        original = path.read_bytes()
        patched = patch_iff(original)
        if patched == original:
            print(f"OK (déjà vanilla): {rel}")
            continue
        if args.dry_run:
            print(f"PATCH {rel}")
            continue
        path.write_bytes(patched)
        print(f"écrit: {rel}")


if __name__ == "__main__":
    main()
