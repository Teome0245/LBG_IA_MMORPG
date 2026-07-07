#!/usr/bin/env python3
"""Patch login/chargement Prime depuis custom_branding_sources/."""
from __future__ import annotations

import argparse
import os
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
# Comme le client Aurora : fond 026 (prio 55) + login fonctionnel 029 (écrasé en prio 99).
PRIME_LOGIN_INC_SOURCE = LOGIN_INC_SOURCE

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
    if "new_login_screen" in inc_text and inc_source not in (
        "LBG_patch_026.tre",
        "upg_cu.tre",
    ):
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


def _patch_page_blocks_input(line: str) -> str:
    """Page décorative : ne capte pas souris / clavier."""
    stripped = line.strip()
    if not stripped.startswith("<Page"):
        return line
    if "GetsInput=" not in stripped:
        line = line.replace("<Page", "<Page GetsInput='false'", 1)
    if "Selectable='true'" in line:
        line = line.replace("Selectable='true'", "Selectable='false'")
    elif "Selectable=" not in stripped:
        line = line.replace("<Page", "<Page Selectable='false'", 1)
    return line


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
        if stripped.startswith("<Page") and "Name='blur'" in stripped:
            line = _patch_page_blocks_input(line)
        if (
            stripped.startswith("<Page")
            and "Name='frame'" in stripped
            and "fullFrame.rs_default" in stripped
        ):
            line = _patch_page_blocks_input(line)
        if "SourceResource='new_login_screen'" in stripped:
            if stripped.startswith("<Image") and "GetsInput=" not in stripped:
                line = line.replace("<Image", "<Image GetsInput='false'", 1)
        if stripped.startswith("<Textbox") and (
            "Name='UsernameTextbox'" in stripped or "Name='PasswordTextbox'" in stripped
        ):
            if "GetsInput=" not in stripped:
                line = line.replace("<Textbox", "<Textbox GetsInput='true'", 1)
        out.append(line)

    return nl.join(line.encode("latin-1", errors="replace") for line in out)


def build_prime_login_patch(
    *,
    prime_dir: Path,
    sources_dir: Path,
    out_tre: Path,
    inc_source: str = LOGIN_INC_SOURCE,
    tex_size: int = 512,
    include_splash: bool = False,
    include_loading: bool = False,
    force_vanilla: bool = True,
) -> None:
    """force_vanilla=True : LBG_patch_029 sans branding custom (pas patch_00 Pre-CU)."""
    files: dict[str, bytes] = {}
    if not force_vanilla:
        files = _pack_custom_sources(
            sources_dir, include_splash=include_splash, include_loading=include_loading
        )

    ui_source = PRIME_LOGIN_INC_SOURCE if force_vanilla else inc_source
    login_raw = _fallback_login_inc(prime_dir, ui_source)
    if os.environ.get("PRIME_LOGIN_RAW", "0") == "1":
        files["ui/ui_loginscreen.inc"] = login_raw
        print(f"  login inc : {ui_source} (brut)")
    else:
        files["ui/ui_loginscreen.inc"] = _fix_login_inc_input(login_raw)
        print(f"  login inc : {ui_source} + correctif saisie (champs cliquables)")

    if include_loading:
        for local_name, tre_path in BRANDING_LOADING.items():
            src = sources_dir / local_name
            if src.is_file():
                files[tre_path] = src.read_bytes()
    elif (
        not force_vanilla
        and os.environ.get("PRIME_LOGIN_RAW", "0") != "1"
    ):
        loading_raw = extract_file_from_tre(prime_dir / ui_source, "ui/ui_loading2.inc")
        if not loading_raw:
            loading_raw = extract_file_from_tre(
                prime_dir / LOGIN_INC_SOURCE, "ui/ui_loading2.inc"
            )
        if loading_raw and (b"aurora1/ui_load_planet" in loading_raw or b"lbg/ui_load_planet" in loading_raw):
            loading_raw = extract_file_from_tre(
                prime_dir / LOGIN_INC_SOURCE, "ui/ui_loading2.inc"
            )
        if loading_raw:
            files["ui/ui_loading2.inc"] = loading_raw
            print(f"  loading inc : {ui_source} (LBG, sans Aurora custom)")

    if include_splash:
        lbg_splash = extract_file_from_tre(
            prime_dir / LOGIN_INC_SOURCE, "ui/ui_splash_screen.inc"
        )
        if lbg_splash:
            files["ui/ui_splash_screen.inc"] = lbg_splash
            print("  splash inc  : LBG_patch_029 (compatible JTL)")

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
        default=LOGIN_INC_SOURCE,
        help="TRE source ui_loginscreen (défaut: LBG_patch_029.tre)",
    )
    p.add_argument(
        "--precu-login",
        action="store_true",
        help="Utiliser patch_00 Pre-CU (déconseillé pour lbgemu.exe)",
    )
    p.add_argument(
        "--custom-branding",
        action="store_true",
        help="Inclure custom_branding_sources (ui_loading2 Aurora, etc.)",
    )
    args = p.parse_args()
    out = args.out or (args.prime_dir / "patch_prime_login_00.tre")
    if not args.sources_dir.is_dir():
        print(f"AVERT: sources absentes {args.sources_dir} — repli inc vanilla")
    inc = VANILLA_INC_SOURCE if args.precu_login else args.inc_source
    build_prime_login_patch(
        prime_dir=args.prime_dir,
        sources_dir=args.sources_dir,
        out_tre=out,
        inc_source=inc,
        include_splash=args.include_splash,
        include_loading=args.include_loading or args.custom_branding,
        force_vanilla=not args.custom_branding,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
