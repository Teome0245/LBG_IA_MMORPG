#!/usr/bin/env python3
"""
Patch client Prime — branding LBG (musique login + futurs assets UI).

Produit patch_lbg_01.tre chargé en priorité via swgemu_live.cfg (searchTree_00_25).

Usage :
  python3 tools/client_patch/build_lbg_branding_patch.py
  python3 tools/client_patch/build_lbg_branding_patch.py --music /chemin/theme_lbg.mp3
  python3 tools/client_patch/build_lbg_branding_patch.py --silent-seconds 3
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "client_patch"))

from tre_writer import build_tre  # noqa: E402

PATCH_TRE = ROOT / "infra/client-patch-server/patches/prime/patch_lbg_01.tre"
TITLE_MUSIC_TRE_PATH = "music/mus_title_lp.mp3"


def _silent_mp3(seconds: float, out: Path) -> None:
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg requis pour générer un MP3 (--music ou installer ffmpeg)")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r=44100:cl=stereo",
            "-t",
            str(seconds),
            "-c:a",
            "libmp3lame",
            "-q:a",
            "9",
            str(out),
        ],
        check=True,
    )


def _load_music(args: argparse.Namespace) -> bytes:
    if args.music:
        src = Path(args.music)
        if not src.is_file():
            raise SystemExit(f"Fichier musique introuvable : {src}")
        return src.read_bytes()
    with tempfile.TemporaryDirectory() as tmp:
        mp3 = Path(tmp) / "silent.mp3"
        _silent_mp3(args.silent_seconds, mp3)
        return mp3.read_bytes()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build patch_lbg_01.tre (branding Prime)")
    parser.add_argument(
        "--music",
        type=Path,
        help="MP3 de remplacement pour l'écran titre/login (défaut : silence court)",
    )
    parser.add_argument(
        "--silent-seconds",
        type=float,
        default=2.0,
        help="Durée du silence si --music absent (défaut 2 s)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PATCH_TRE,
        help=f"Chemin TRE de sortie (défaut {PATCH_TRE})",
    )
    args = parser.parse_args()

    payload = _load_music(args)
    if len(payload) < 128:
        raise SystemExit("MP3 trop petit — fichier invalide")

    build_tre(args.output, {TITLE_MUSIC_TRE_PATH: payload})
    print(f"OK {args.output} ({len(payload)} o) — {TITLE_MUSIC_TRE_PATH}")
    print("Puis : bash infra/scripts/generate_client_patch_manifests.sh")
    print("       bash infra/scripts/install_client_patch_server_245.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
