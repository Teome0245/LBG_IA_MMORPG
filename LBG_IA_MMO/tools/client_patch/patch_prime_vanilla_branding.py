#!/usr/bin/env python3
"""
Patch branding Prime directement dans les TRE vanilla (copie PreCu = backup).

Étapes (une à la fois, tester le client après chaque étape) :
  --step 1  texture/helmet_rebel_ace_sm.dds dans patch_11_03.tre (fond login via CSHD)
  --step 2  music/mus_title_lp.mp3 dans data_music_00.tre (inline)
  --step roundtrip  réécrit patch_11_03 sans changer l'image (test outil)

Usage :
  python3 tools/client_patch/patch_prime_vanilla_branding.py --step 1
  python3 tools/client_patch/patch_prime_vanilla_branding.py --step 2 --music theme.mp3
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


from build_helmet_lbg_dds import build_helmet_lbg_dds, extract_helmet_from_tre  # noqa: E402


DEFAULT_PRIME = Path("/mnt/j/swgemu/clients/prime-lbg")
PATCH_11 = "patch_11_03.tre"
MUSIC_TRE = "data_music_00.tre"
HELMET_TEX = "texture/helmet_rebel_ace_sm.dds"
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


def patch_login_helmet(prime_dir: Path) -> None:
    """Étape 1 : remplace helmet_rebel_ace_sm.dds (cible du CSHD login, pas ui_spacestation)."""
    tre = prime_dir / PATCH_11
    if not tre.is_file():
        raise SystemExit(f"introuvable: {tre}")
    _backup(tre)
    vanilla = extract_helmet_from_tre(tre)
    lbg_dds = build_helmet_lbg_dds(vanilla)
    work_tre = tre.with_suffix(".tre.work.lbg")
    stats = replace_and_write(tre, work_tre, {HELMET_TEX: lbg_dds})
    work_tre.replace(tre)
    print(
        f"{PATCH_11}: {HELMET_TEX} → branding LBG ({len(lbg_dds)} o, "
        f"{stats['replaced']} remplacé, {stats['total']} entrées TRE)"
    )


def patch_login_roundtrip(prime_dir: Path) -> None:
    """Test outil : réécrit patch_11_03 sans changer le visuel helmet."""
    tre = prime_dir / PATCH_11
    if not tre.is_file():
        raise SystemExit(f"introuvable: {tre}")
    _backup(tre)
    vanilla = extract_helmet_from_tre(tre)
    work_tre = tre.with_suffix(".tre.work.lbg")
    stats = replace_and_write(tre, work_tre, {HELMET_TEX: vanilla})
    work_tre.replace(tre)
    print(f"{PATCH_11}: roundtrip {HELMET_TEX} ({stats['total']} entrées)")


def patch_login_texture(prime_dir: Path, work: Path) -> None:
    patch_login_helmet(prime_dir)


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
    parser.add_argument(
        "--step",
        choices=("1", "2", "roundtrip"),
        help="1=texture login helmet, 2=musique titre, roundtrip=test TRE",
    )
    parser.add_argument("--login-only", action="store_true", help="= --step 1")
    parser.add_argument("--music-only", action="store_true", help="= --step 2")
    args = parser.parse_args()

    if args.login_only:
        args.step = "1"
    if args.music_only:
        args.step = "2"
    if args.step is None:
        raise SystemExit("Indiquer --step 1, --step 2 ou --step roundtrip (une étape à la fois).")

    prime = args.prime_dir.resolve()
    if not prime.is_dir():
        raise SystemExit(f"dossier Prime introuvable: {prime}")

    with tempfile.TemporaryDirectory(prefix="lbg-brand-") as tmp:
        work = Path(tmp)
        if args.step == "1":
            patch_login_texture(prime, work)
        elif args.step == "roundtrip":
            patch_login_roundtrip(prime)
        elif args.step == "2":
            patch_title_music(prime, _load_music(args))

    if args.step != "2":
        cleanup_overlay_tre(prime)

    print("OK — relancer le client Prime et vérifier l'écran login.")
    print("Rollback : cp patch_11_03.tre.bak.lbg patch_11_03.tre")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
