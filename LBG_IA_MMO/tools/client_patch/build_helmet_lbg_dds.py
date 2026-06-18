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

from generate_lbg_login_station_dds import generate_lbg_station_rgba  # noqa: E402

DEFAULT_TRE = Path("/mnt/j/swgemu/clients/prime-lbg/patch_11_03.tre")
HELMET_PATH = "texture/helmet_rebel_ace_sm.dds"
VENV_PY = ROOT / "mmo_server/world/tools/venv_gen/bin/python3"
WIDTH, HEIGHT = 128, 64


def _dxt5_mip_sizes(width: int, height: int) -> list[int]:
    sizes: list[int] = []
    w, h = width, height
    while w >= 1 and h >= 1:
        bw = max(1, (w + 3) // 4)
        bh = max(1, (h + 3) // 4)
        sizes.append(bw * bh * 16)
        if w == 1 and h == 1:
            break
        w = max(1, w // 2)
        h = max(1, h // 2)
    return sizes


def extract_helmet_from_tre(tre_path: Path) -> bytes:
    data = tre_path.read_bytes()
    if data[:8] != b"EERT5000":
        raise ValueError(f"format TRE non supporté: {tre_path}")
    count = struct.unpack_from("<I", data, 8)[0]
    rec_start, rc, rs, nc, ns = struct.unpack_from("<IIIII", data, 12)
    rb = data[rec_start : rec_start + rs]
    if rc == 2:
        rb = zlib.decompress(rb)
    nb = data[rec_start + rs : rec_start + rs + ns]
    if nc == 2:
        nb = zlib.decompress(nb)
    names = [n.decode("ascii") for n in nb.split(b"\x00") if n]
    try:
        idx = names.index(HELMET_PATH)
    except ValueError as exc:
        raise KeyError(f"{HELMET_PATH} absent de {tre_path.name}") from exc
    _cs, _usize, foff, ctype, csize, _no = struct.unpack_from("<IIIIII", rb, idx * 24)
    payload = data[foff : foff + csize]
    if ctype == 2:
        payload = zlib.decompress(payload)
    return payload


def encode_dxt5_mip0_rgba(rgba: bytes, width: int, height: int) -> bytes:
    """Encode le mip 0 en DXT5 via Pillow (venv projet)."""
    if not VENV_PY.is_file():
        raise SystemExit(f"Pillow requis: {VENV_PY} introuvable")
    script = f"""
import io, sys
from PIL import Image
rgba = sys.stdin.buffer.read()
img = Image.frombytes('RGBA', ({width}, {height}), rgba)
buf = io.BytesIO()
img.save(buf, format='DDS', pixel_format='DXT5')
sys.stdout.buffer.write(buf.getvalue()[128:])
"""
    import subprocess

    proc = subprocess.run(
        [str(VENV_PY), "-c", script],
        input=rgba,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", errors="replace") or "encodage DXT5 échoué")
    mip0 = proc.stdout
    expected = _dxt5_mip_sizes(width, height)[0]
    if len(mip0) != expected:
        raise ValueError(f"mip0 DXT5: {len(mip0)} o != {expected} o attendus")
    return mip0


def build_helmet_lbg_dds(vanilla: bytes, width: int = WIDTH, height: int = HEIGHT) -> bytes:
    if vanilla[:4] != b"DDS " or len(vanilla) < 128:
        raise ValueError("DDS vanilla invalide")
    fourcc = vanilla[84:88]
    if fourcc != b"DXT5":
        raise ValueError(f"format attendu DXT5, reçu {fourcc!r}")

    mip_sizes = _dxt5_mip_sizes(width, height)
    body = vanilla[128:]
    if len(body) < sum(mip_sizes):
        raise ValueError(f"corps DDS trop court ({len(body)} o)")

    rgba = generate_lbg_station_rgba(width, height)
    new_mip0 = encode_dxt5_mip0_rgba(rgba, width, height)
    tail = body[mip_sizes[0] :]
    return vanilla[:128] + new_mip0 + tail


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
