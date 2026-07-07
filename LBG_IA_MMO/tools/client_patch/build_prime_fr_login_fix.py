#!/usr/bin/env python3
"""Patch login FR : inc minuscules (STF LBG_French) + saisie cliquable."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "client_patch"))

from build_aurora_login_ui_fix import _fix_login_inc  # noqa: E402
from build_prime_login_branding import _fix_login_inc_input  # noqa: E402
from merge_fr_tre import extract_file_from_tre  # noqa: E402
from tre_writer import build_tre  # noqa: E402

DEFAULT_CLIENT = Path("/mnt/j/swgemu/clients/prime-lbg")
OUT_NAME = "patch_prime_fr_login_00.tre"


def build_fr_login_patch(*, client_dir: Path, vanilla_ref: Path | None = None) -> bytes:
    ref = vanilla_ref or client_dir
    login_raw = extract_file_from_tre(ref / "patch_00.tre", "ui/ui_loginscreen.inc")
    if not login_raw:
        raise SystemExit(f"ui_loginscreen.inc introuvable dans {ref}/patch_00.tre")
    return _fix_login_inc_input(_fix_login_inc(login_raw))


def build_fr_login_tre(*, client_dir: Path, out_tre: Path, vanilla_ref: Path | None = None) -> None:
    ref = vanilla_ref or client_dir
    files: dict[str, bytes] = {
        "ui/ui_loginscreen.inc": build_fr_login_patch(
            client_dir=client_dir, vanilla_ref=vanilla_ref
        ),
    }
    # Carte planétaire vanilla (évite la mosaïque LBG_client / LBG_planets).
    map_dds = extract_file_from_tre(
        client_dir / "LBG_patch_008_texture_04.tre", "texture/ui_map_tatooine.dds"
    )
    if not map_dds:
        map_dds = extract_file_from_tre(ref / "patch_00.tre", "texture/ui_map_tatooine.dds")
    if map_dds:
        files["texture/ui_map_tatooine.dds"] = map_dds

    build_tre(out_tre, files, compress=True)
    print(f"OK: {out_tre} ({len(files)} entrées)")
    for path in sorted(files):
        print(f"  · {path}")


def main() -> int:
    p = argparse.ArgumentParser(description="Login FR : inc + saisie")
    p.add_argument("--client-dir", type=Path, default=DEFAULT_CLIENT)
    p.add_argument("--vanilla-ref", type=Path, default=None)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()
    out = args.out or (args.client_dir / OUT_NAME)
    build_fr_login_tre(client_dir=args.client_dir, out_tre=out, vanilla_ref=args.vanilla_ref)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
