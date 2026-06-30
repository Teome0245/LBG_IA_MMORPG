#!/usr/bin/env python3
"""Patch login/chargement Prime depuis custom_branding_sources/."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "client_patch"))

from generate_lbg_login_station_dds import (  # noqa: E402
    _write_dds_rgba,
    generate_lbg_station_rgba,
)
from merge_fr_tre import extract_file_from_tre  # noqa: E402
from tre_writer import build_tre  # noqa: E402

DEFAULT_PRIME = Path("/mnt/j/swgemu/clients/prime-lbg")
DEFAULT_SOURCES = Path("/mnt/j/swgemu/custom_branding_sources")
LOGIN_INC_SOURCE = "LBG_patch_029.tre"

# Aligné sur custom_branding_sources/compile_branding_patch.py
BRANDING_FILE_MAP: dict[str, str] = {
    "ui_splash_screen.inc": "ui/ui_splash_screen.inc",
    "ui_loginscreen.inc": "ui/ui_loginscreen.inc",
    "ui_loading2.inc": "ui/ui_loading2.inc",
    "ui_load_planet_flag.dds": "texture/loading/lbg/ui_load_planet_flag.dds",
    "ui_load_planet.dds": "texture/loading/lbg/ui_load_planet.dds",
    "ui_background_arrow.dds": "texture/ui_background_arrow.dds",
    "ui_logo_lucas.dds": "texture/ui_logo_lucas.dds",
    "ui_logo_soe.dds": "texture/ui_logo_soe.dds",
    "starwarslogo_optimized_12_000.dds": "texture/font/starwarslogo_optimized_12_000.dds",
    "theme.mp3": "music/mus_title_lp.mp3",
    "mus_title_lp.mp3": "music/mus_title_lp.mp3",
}


def _pack_custom_sources(sources_dir: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    if not sources_dir.is_dir():
        return files
    for local_name, tre_path in BRANDING_FILE_MAP.items():
        src = sources_dir / local_name
        if src.is_file():
            files[tre_path] = src.read_bytes()
    return files


def _fallback_login_inc(prime_dir: Path, inc_source: str) -> bytes:
    inc_tre = prime_dir / inc_source
    inc_raw = extract_file_from_tre(inc_tre, "ui/ui_loginscreen.inc")
    if not inc_raw:
        raise SystemExit(f"ui/ui_loginscreen.inc introuvable dans {inc_tre}")
    inc_text = inc_raw.decode("latin-1", errors="replace")
    if "new_login_screen" in inc_text:
        raise SystemExit(f"{inc_source} référence encore new_login_screen")
    return inc_raw


def _procedural_login_dds(tex_size: int = 512) -> bytes:
    import tempfile

    rgba = generate_lbg_station_rgba(tex_size, tex_size)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dds") as tmp:
        dds_path = Path(tmp.name)
    try:
        _write_dds_rgba(dds_path, tex_size, tex_size, rgba)
        return dds_path.read_bytes()
    finally:
        dds_path.unlink(missing_ok=True)


def build_prime_login_patch(
    *,
    prime_dir: Path,
    sources_dir: Path,
    out_tre: Path,
    inc_source: str = LOGIN_INC_SOURCE,
    tex_size: int = 512,
) -> None:
    files = _pack_custom_sources(sources_dir)

    if "ui/ui_loginscreen.inc" not in files:
        files["ui/ui_loginscreen.inc"] = _fallback_login_inc(prime_dir, inc_source)
        print(f"  login inc : repli {inc_source} (pas de ui_loginscreen.inc custom)")
    else:
        inc_text = files["ui/ui_loginscreen.inc"].decode("latin-1", errors="replace")
        if "new_login_screen" in inc_text:
            raise SystemExit(
                "ui_loginscreen.inc custom référence new_login_screen — retirer les images Aurora"
            )
        print("  login inc : custom_branding_sources/ui_loginscreen.inc")

    # Remplace toute référence résiduelle à l'atlas Aurora du patch 026
    if "texture/new_login_screen.dds" not in files:
        flag = sources_dir / "ui_load_planet_flag.dds"
        if flag.is_file():
            files["texture/new_login_screen.dds"] = flag.read_bytes()
            print("  new_login_screen.dds ← ui_load_planet_flag.dds")
        else:
            files["texture/new_login_screen.dds"] = _procedural_login_dds(tex_size)
            print("  new_login_screen.dds : procédural LBG")

    build_tre(out_tre, files, compress=True)
    print(f"OK: {out_tre} ({len(files)} entrées)")
    for tre_path in sorted(files):
        print(f"  · {tre_path}")


def main() -> int:
    p = argparse.ArgumentParser(
        description="TRE branding Prime (custom_branding_sources + login hors Aurora)"
    )
    p.add_argument("--prime-dir", type=Path, default=DEFAULT_PRIME)
    p.add_argument("--sources-dir", type=Path, default=DEFAULT_SOURCES)
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Défaut: <prime-dir>/patch_prime_login_00.tre",
    )
    p.add_argument(
        "--inc-source",
        default=LOGIN_INC_SOURCE,
        help="TRE repli si pas de ui_loginscreen.inc custom",
    )
    args = p.parse_args()
    out = args.out or (args.prime_dir / "patch_prime_login_00.tre")
    if not args.sources_dir.is_dir():
        print(f"AVERT: sources absentes {args.sources_dir} — repli inc vanilla")
    build_prime_login_patch(
        prime_dir=args.prime_dir,
        sources_dir=args.sources_dir,
        out_tre=out,
        inc_source=args.inc_source,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
