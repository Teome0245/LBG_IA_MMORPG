#!/usr/bin/env python3
"""
Patch branding Prime directement dans les TRE vanilla (copie PreCu = backup).

- patch_11_03.tre : texture/ui_spacestation.dds (fond login)
- data_music_00.tre : music/mus_title_lp.mp3 (inline, slot 696448 o)

Usage :
  python3 tools/client_patch/patch_prime_vanilla_branding.py
  python3 tools/client_patch/patch_prime_vanilla_branding.py --music theme.mp3
  python3 tools/client_patch/patch_prime_vanilla_branding.py --prime-dir /mnt/j/swgemu/clients/prime-lbg
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

from eert_io import patch_binary_slot, replace_and_write  # noqa: E402
from generate_lbg_login_station_dds import (  # noqa: E402
    _write_dds_rgba,
    generate_lbg_station_rgba,
)


DEFAULT_PRIME = Path("/mnt/j/swgemu/clients/prime-lbg")
PATCH_11 = "patch_11_03.tre"
MUSIC_TRE = "data_music_00.tre"
LOGIN_TEX = "texture/ui_spacestation.dds"
MUSIC_PATH = "music/mus_title_lp.mp3"
MUSIC_SLOT = 696448


def _backup(path: Path) -> Path:
    bak = path.with_suffix(path.suffix + ".bak.lbg")
    if not bak.exists():
        shutil.copy2(path, bak)
        print(f"backup → {bak}")
    return bak


def _load_music(args: argparse.Namespace) -> bytes:
    if args.music:
        p = Path(args.music)
        if not p.is_file():
            raise SystemExit(f"musique introuvable: {p}")
        data = p.read_bytes()
    else:
        if not shutil.which("ffmpeg"):
            raise SystemExit("ffmpeg requis sans --music")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "title.mp3"
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
                    "sine=frequency=220:duration=8",
                    "-c:a",
                    "libmp3lame",
                    "-q:a",
                    "6",
                    str(out),
                ],
                check=True,
            )
            data = out.read_bytes()
    if len(data) > MUSIC_SLOT:
        raise SystemExit(f"MP3 {len(data)} o > slot {MUSIC_SLOT} o dans {MUSIC_TRE}")
    if len(data) < 128:
        raise SystemExit("MP3 trop petit")
    return data


def patch_login_texture(prime_dir: Path, work: Path) -> None:
    """Login : conserver le CSHD vanilla (ui_spacestation.dds) — une DDS brute provoque crash GPU."""
    tre = prime_dir / PATCH_11
    if not tre.is_file():
        raise SystemExit(f"introuvable: {tre}")
    print(
        f"{PATCH_11}: ui_spacestation.dds inchangé (CSHD requis). "
        "Prochaine étape : remplacer texture/helmet_rebel_ace_sm.dds ou CSHD LBG."
    )


def patch_title_music(prime_dir: Path, mp3: bytes) -> None:
    tre = prime_dir / MUSIC_TRE
    if not tre.is_file():
        raise SystemExit(f"introuvable: {tre}")
    _backup(tre)
    patch_binary_slot(tre, MUSIC_PATH, mp3)
    print(f"{MUSIC_TRE}: {MUSIC_PATH} → {len(mp3)} o (slot {MUSIC_SLOT} o)")


def cleanup_overlay_tre(prime_dir: Path) -> None:
    """Retire patch_lbg_01 si présent — branding intégré au vanilla."""
    live = prime_dir / "swgemu_live.cfg"
    if not live.is_file():
        return
    text = live.read_text(encoding="utf-8")
    new = "\n".join(line for line in text.splitlines() if "patch_lbg_01.tre" not in line)
    if new != text:
        live.write_text(new + ("\n" if not new.endswith("\n") else ""), encoding="utf-8")
        print("swgemu_live.cfg : patch_lbg_01.tre retiré (branding vanilla)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Branding LBG dans TRE vanilla Prime")
    parser.add_argument("--prime-dir", type=Path, default=DEFAULT_PRIME)
    parser.add_argument("--music", type=Path, help="MP3 titre (sinon tonalité 8s via ffmpeg)")
    parser.add_argument("--login-only", action="store_true")
    parser.add_argument("--music-only", action="store_true")
    args = parser.parse_args()

    prime = args.prime_dir.resolve()
    if not prime.is_dir():
        raise SystemExit(f"dossier Prime introuvable: {prime}")

    with tempfile.TemporaryDirectory(prefix="lbg-brand-") as tmp:
        work = Path(tmp)
        if not args.music_only:
            patch_login_texture(prime, work)
        if not args.login_only:
            patch_title_music(prime, _load_music(args))

    if not args.music_only:
        cleanup_overlay_tre(prime)

    print("OK — relancer le client Prime (PreCu inchangé / backup .bak.lbg sur Prime)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
