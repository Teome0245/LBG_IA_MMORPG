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
VANILLA_INC_SOURCE = "patch_00.tre"
LOGIN_INC_SOURCE = "LBG_patch_029.tre"

# Aligné sur custom_branding_sources/compile_branding_patch.py
BRANDING_FILE_MAP: dict[str, str] = {
    "ui_background_arrow.dds": "texture/ui_background_arrow.dds",
    "theme.mp3": "music/mus_title_lp.mp3",
    "mus_title_lp.mp3": "music/mus_title_lp.mp3",
}

BRANDING_LOADING: dict[str, str] = {
    "ui_loading2.inc": "ui/ui_loading2.inc",
    "ui_load_planet_flag.dds": "texture/loading/lbg/ui_load_planet_flag.dds",
    "ui_load_planet.dds": "texture/loading/lbg/ui_load_planet.dds",
}

# Splash / logos : optionnels (peuvent bloquer le login si mal configurés)
BRANDING_OPTIONAL: dict[str, str] = {
    "ui_splash_screen.inc": "ui/ui_splash_screen.inc",
    "ui_logo_lucas.dds": "texture/ui_logo_lucas.dds",
    "ui_logo_soe.dds": "texture/ui_logo_soe.dds",
    "starwarslogo_optimized_12_000.dds": "texture/font/starwarslogo_optimized_12_000.dds",
}


def _pack_custom_sources(
    sources_dir: Path, *, include_splash: bool, include_loading: bool
) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    if not sources_dir.is_dir():
        return files
    for local_name, tre_path in BRANDING_FILE_MAP.items():
        src = sources_dir / local_name
        if src.is_file():
            files[tre_path] = src.read_bytes()
    if include_loading:
        for local_name, tre_path in BRANDING_LOADING.items():
            src = sources_dir / local_name
            if src.is_file():
                files[tre_path] = src.read_bytes()
    if include_splash:
        for local_name, tre_path in BRANDING_OPTIONAL.items():
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


def _fix_login_inc_input(inc_raw: bytes) -> bytes:
    """Cadres décoratifs : ne pas intercepter les clics (conserve CRLF Windows)."""
    nl = b"\r\n" if b"\r\n" in inc_raw else b"\n"
    text = inc_raw.decode("latin-1", errors="replace")
    lines = text.splitlines()
    out: list[str] = []
    in_input = False
    depth = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("<Page") and "Name='InputPage'" in stripped:
            in_input = True
            depth = 0
        if in_input:
            if stripped.startswith("<"):
                if stripped.startswith("</"):
                    depth -= stripped.count("</")
                elif not stripped.endswith("/>") and "<Page" in stripped:
                    depth += 1
            if depth <= 1 and "Name='box'" in stripped and stripped.startswith("<Page"):
                if "GetsInput=" not in stripped:
                    line = line.replace("<Page", "<Page GetsInput='false'", 1)
            if stripped.startswith("</Page>") and depth <= 0:
                in_input = False
        if "Name='blur'" in stripped and stripped.startswith("<Page"):
            if "GetsInput=" not in stripped:
                line = line.replace("<Page", "<Page GetsInput='false'", 1)
            if "Selectable='true'" in line:
                line = line.replace("Selectable='true'", "Selectable='false'")
        if (
            "Name='frame'" in stripped
            and "fullFrame.rs_default" in stripped
            and stripped.startswith("<Page")
            and "GetsInput=" not in stripped
        ):
            line = line.replace("<Page", "<Page GetsInput='false'", 1)
        out.append(line)
    return nl.join(line.encode("latin-1", errors="replace") for line in out)


def build_prime_login_patch(
    *,
    prime_dir: Path,
    sources_dir: Path,
    out_tre: Path,
    inc_source: str = VANILLA_INC_SOURCE,
    tex_size: int = 512,
    include_splash: bool = False,
    include_loading: bool = False,
    force_vanilla: bool = True,
) -> None:
    files: dict[str, bytes] = {}
    if not force_vanilla:
        files = _pack_custom_sources(
            sources_dir, include_splash=include_splash, include_loading=include_loading
        )

    src_tre = inc_source if force_vanilla else LOGIN_INC_SOURCE
    login_raw = _fallback_login_inc(prime_dir, src_tre)
    files["ui/ui_loginscreen.inc"] = _fix_login_inc_input(login_raw)
    print(f"  login inc : {src_tre} + correctif saisie")

    if include_loading:
        for local_name, tre_path in BRANDING_LOADING.items():
            src = sources_dir / local_name
            if src.is_file():
                files[tre_path] = src.read_bytes()
    else:
        loading_src = src_tre if force_vanilla else LOGIN_INC_SOURCE
        loading_raw = extract_file_from_tre(prime_dir / loading_src, "ui/ui_loading2.inc")
        if not loading_raw and force_vanilla:
            loading_raw = extract_file_from_tre(
                prime_dir / "data_other_00.tre", "ui/ui_loading2.inc"
            )
        if loading_raw:
            if b"aurora" in loading_raw or b"lbg/ui_load_planet" in loading_raw:
                loading_raw = extract_file_from_tre(
                    prime_dir / VANILLA_INC_SOURCE, "ui/ui_loading2.inc"
                ) or loading_raw
            files["ui/ui_loading2.inc"] = loading_raw
            print(f"  loading inc : {loading_src} (sans Aurora)")

    splash_raw = extract_file_from_tre(prime_dir / VANILLA_INC_SOURCE, "ui/ui_splash_screen.inc")
    if include_splash and splash_raw:
        lbg_splash = extract_file_from_tre(
            prime_dir / LOGIN_INC_SOURCE, "ui/ui_splash_screen.inc"
        )
        files["ui/ui_splash_screen.inc"] = lbg_splash or splash_raw
        print("  splash inc  : LBG_patch_029 (compatible JTL)")

    files["texture/new_login_screen.dds"] = _procedural_login_dds(tex_size)
    print("  new_login_screen.dds : station procédurale (écrase LBG_client)")

    tatooine = None
    for tre_name, path in [
        ("LBG_patch_029.tre", "texture/loading/tatooine/ui_load_permanent.dds.dds"),
        ("LBG_patch_029.tre", "texture/loading/generic/generic_flag.dds"),
        ("patch_00.tre", "texture/loading/generic/generic_flag.dds"),
    ]:
        tatooine = extract_file_from_tre(prime_dir / tre_name, path)
        if tatooine:
            break
    if tatooine:
        files["texture/loading/aurora1/ui_load_planet.dds"] = tatooine
        print("  aurora1/ui_load_planet.dds : texture neutre (écrase Destroyer)")

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
        "--include-loading",
        action="store_true",
        help="Inclure ui_loading2.inc + fonds planète (défaut: non)",
    )
    p.add_argument(
        "--include-splash",
        action="store_true",
        help="Inclure ui_splash_screen.inc et logos (défaut: non, évite blocage splash)",
    )
    p.add_argument(
        "--inc-source",
        default=VANILLA_INC_SOURCE,
        help="TRE source pour ui_loginscreen.inc (défaut: patch_00)",
    )
    p.add_argument(
        "--lbg-login",
        action="store_true",
        help="Utiliser LBG_patch_029 + branding custom (défaut: patch_00 vanilla)",
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
        include_splash=args.include_splash,
        include_loading=args.include_loading,
        force_vanilla=not args.lbg_login,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
