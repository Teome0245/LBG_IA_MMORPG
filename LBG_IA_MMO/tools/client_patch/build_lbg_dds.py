#!/usr/bin/env python3
"""Génère des DDS LBG (remplacement mip 0, conserve mips vanilla + taille exacte)."""
from __future__ import annotations

import io
import math
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "client_patch"))

from generate_lbg_login_station_dds import generate_lbg_station_rgba  # noqa: E402

VENV_PY = ROOT / "mmo_server/world/tools/venv_gen/bin/python3"
DXT_BLOCK_BYTES = {"DXT1": 8, "DXT5": 16}


def _dxt_mip_sizes(width: int, height: int, block_bytes: int) -> list[int]:
    sizes: list[int] = []
    w, h = width, height
    while w >= 1 and h >= 1:
        bw = max(1, (w + 3) // 4)
        bh = max(1, (h + 3) // 4)
        sizes.append(bw * bh * block_bytes)
        if w == 1 and h == 1:
            break
        w = max(1, w // 2)
        h = max(1, h // 2)
    return sizes


def extract_texture_from_tre(tre_path: Path, logical_path: str) -> bytes:
    data = tre_path.read_bytes()
    if data[:8] != b"EERT5000":
        raise ValueError(f"format TRE non supporté: {tre_path}")
    rec_start, rc, rs, nc, ns = struct.unpack_from("<IIIII", data, 12)
    rb = data[rec_start : rec_start + rs]
    if rc == 2:
        rb = zlib.decompress(rb)
    nb = data[rec_start + rs : rec_start + rs + ns]
    if nc == 2:
        nb = zlib.decompress(nb)
    names = [n.decode("ascii") for n in nb.split(b"\x00") if n]
    try:
        idx = names.index(logical_path)
    except ValueError as exc:
        raise KeyError(f"{logical_path} absent de {tre_path.name}") from exc
    _cs, _usize, foff, ctype, csize, _no = struct.unpack_from("<IIIIII", rb, idx * 24)
    payload = data[foff : foff + csize]
    if ctype == 2:
        payload = zlib.decompress(payload)
    return payload


def _fourcc_name(vanilla: bytes) -> str:
    fourcc = vanilla[84:88]
    if fourcc == b"DXT1":
        return "DXT1"
    if fourcc == b"DXT5":
        return "DXT5"
    raise ValueError(f"format DDS non supporté: {fourcc!r}")


def encode_dxt_mip0_rgba(rgba: bytes, width: int, height: int, pixel_format: str) -> bytes:
    if pixel_format not in DXT_BLOCK_BYTES:
        raise ValueError(pixel_format)
    if not VENV_PY.is_file():
        raise SystemExit(f"Pillow requis: {VENV_PY} introuvable")
    script = f"""
import io, sys
from PIL import Image
rgba = sys.stdin.buffer.read()
img = Image.frombytes('RGBA', ({width}, {height}), rgba)
buf = io.BytesIO()
img.save(buf, format='DDS', pixel_format='{pixel_format}')
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
        raise RuntimeError(proc.stderr.decode("utf-8", errors="replace") or "encodage DXT échoué")
    mip0 = proc.stdout
    expected = _dxt_mip_sizes(width, height, DXT_BLOCK_BYTES[pixel_format])[0]
    if len(mip0) != expected:
        raise ValueError(f"mip0 {pixel_format}: {len(mip0)} o != {expected} o attendus")
    return mip0


def build_dds_mip0_replace(
    vanilla: bytes,
    rgba: bytes,
    width: int,
    height: int,
    *,
    pixel_format: str | None = None,
) -> bytes:
    if vanilla[:4] != b"DDS " or len(vanilla) < 128:
        raise ValueError("DDS vanilla invalide")
    fmt = pixel_format or _fourcc_name(vanilla)
    if len(rgba) != width * height * 4:
        raise ValueError("taille RGBA invalide")

    mip_sizes = _dxt_mip_sizes(width, height, DXT_BLOCK_BYTES[fmt])
    body = vanilla[128:]
    new_mip0 = encode_dxt_mip0_rgba(rgba, width, height, fmt)
    if len(body) == mip_sizes[0]:
        # DDS sans chaîne mips (ex. ui_rebel_final_space 512×512)
        if len(new_mip0) != len(body):
            raise ValueError(f"mip0 {len(new_mip0)} o != corps {len(body)} o")
        return vanilla[:128] + new_mip0
    if len(body) < mip_sizes[0]:
        raise ValueError(f"corps DDS trop court ({len(body)} o)")
    return vanilla[:128] + new_mip0 + body[mip_sizes[0] :]


def generate_lbg_spec_rgba(width: int = 128, height: int = 64) -> bytes:
    """Carte spec : reflets sur l'anneau station, fond sombre."""
    color = generate_lbg_station_rgba(width, height)
    out = bytearray(width * height * 4)
    cx, cy = width * 0.5, height * 0.52
    for y in range(height):
        for x in range(width):
            i = (y * width + x) * 4
            b, g, r, a = color[i : i + 4]
            lum = int(0.2126 * r + 0.7152 * g + 0.0722 * b)
            dx = (x - cx) / (width * 0.34)
            dy = (y - cy) / (height * 0.22)
            dist = math.sqrt(dx * dx + dy * dy)
            ring = math.exp(-((dist - 1.0) ** 2) * 40.0)
            spec = min(255, int(lum * 0.25 + 180 * ring + 40 * ring * (g / 255.0)))
            out[i : i + 3] = bytes((spec, spec, spec))
            out[i + 3] = 255
    return bytes(out)


def generate_rebel_ui_neutral_rgba(vanilla: bytes, width: int = 512, height: int = 512) -> bytes:
    """UI atlas : remplace le logo Rebelle (coin haut-droit) par un panneau neutre LBG."""
    if not VENV_PY.is_file():
        raise SystemExit(f"Pillow requis: {VENV_PY} introuvable")
    script = f"""
import io, sys
from PIL import Image, ImageDraw
raw = sys.stdin.buffer.read()
img = Image.open(io.BytesIO(raw)).convert('RGBA')
w, h = img.size
x0, y0 = int(w * 0.55), int(h * 0.02)
x1, y1 = int(w * 0.98), int(h * 0.42)
draw = ImageDraw.Draw(img)
draw.rectangle((x0, y0, x1, y1), fill=(28, 48, 58, 255))
draw.rectangle((x0 + 12, y0 + 12, x1 - 12, y0 + 44), fill=(20, 130, 150, 255))
draw.rectangle((x0 + 20, y0 + 56, x1 - 20, y1 - 16), fill=(18, 36, 48, 230))
if img.size != ({width}, {height}):
    img = img.resize(({width}, {height}))
sys.stdout.buffer.write(img.tobytes())
"""
    import subprocess

    proc = subprocess.run(
        [str(VENV_PY), "-c", script],
        input=vanilla,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", errors="replace") or "édition UI échouée")
    rgba = proc.stdout
    if len(rgba) != width * height * 4:
        raise ValueError(f"RGBA UI: {len(rgba)} o != {width * height * 4} o")
    return rgba


def build_rebel_ui_lbg_dds(vanilla: bytes, width: int = 512, height: int = 512) -> bytes:
    rgba = generate_rebel_ui_neutral_rgba(vanilla, width, height)
    return build_dds_mip0_replace(vanilla, rgba, width, height, pixel_format="DXT5")


def build_helmet_lbg_dds(vanilla: bytes, width: int = 128, height: int = 64) -> bytes:
    return build_dds_mip0_replace(vanilla, generate_lbg_station_rgba(width, height), width, height)


def build_helmet_spec_lbg_dds(vanilla: bytes, width: int = 128, height: int = 64) -> bytes:
    return build_dds_mip0_replace(
        vanilla, generate_lbg_spec_rgba(width, height), width, height, pixel_format="DXT1"
    )
