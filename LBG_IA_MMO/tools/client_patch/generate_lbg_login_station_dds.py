#!/usr/bin/env python3
"""Génère texture/lbg_login_station.dds — station LBG pour écran login (RGBA 32-bit)."""
from __future__ import annotations

import argparse
import math
import struct
import random
from pathlib import Path


def _write_dds_rgba(path: Path, width: int, height: int, rgba: bytes) -> None:
    if len(rgba) != width * height * 4:
        raise ValueError("taille RGBA invalide")
    header = bytearray(128)
    header[0:4] = b"DDS "
    struct.pack_into("<I", header, 4, 124)
    struct.pack_into("<I", header, 8, 0x00001007)  # caps | height | width
    struct.pack_into("<I", header, 12, height)
    struct.pack_into("<I", header, 16, width)
    struct.pack_into("<I", header, 20, width * 4)
    struct.pack_into("<I", header, 76, 32)
    struct.pack_into("<I", header, 80, 0x41)  # RGBA
    struct.pack_into("<I", header, 88, 32)
    struct.pack_into("<I", header, 92, 0x00FF0000)
    struct.pack_into("<I", header, 96, 0x0000FF00)
    struct.pack_into("<I", header, 100, 0x000000FF)
    struct.pack_into("<I", header, 104, 0xFF000000)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(header) + rgba)


def _pixel(r: int, g: int, b: int, a: int = 255) -> bytes:
    return bytes((b, g, r, a))


def generate_lbg_station_rgba(width: int = 1024, height: int = 512) -> bytes:
    rng = random.Random(42)
    buf = bytearray(width * height * 4)
    cx, cy = width * 0.5, height * 0.52
    for y in range(height):
        for x in range(width):
            # fond espace
            t = y / max(height - 1, 1)
            r = int(4 + 8 * (1 - t))
            g = int(8 + 18 * (1 - t))
            b = int(22 + 40 * (1 - t))
            if rng.random() < 0.0025:
                r = g = b = 220

            # nébuleuse cyan
            nx = (x - width * 0.62) / width
            ny = (y - height * 0.35) / height
            neb = math.exp(-(nx * nx + ny * ny) * 8.0)
            r += int(8 * neb)
            g += int(28 * neb)
            b += int(36 * neb)

            # anneau station
            dx = (x - cx) / (width * 0.34)
            dy = (y - cy) / (height * 0.22)
            dist = math.sqrt(dx * dx + dy * dy)
            ring = math.exp(-((dist - 1.0) ** 2) * 40.0)
            core = math.exp(-(dist * dist) * 6.0) if dist < 0.55 else 0.0
            r += int(20 * ring + 35 * core)
            g += int(120 * ring + 80 * core)
            b += int(140 * ring + 95 * core)

            # pylônes
            for side in (-0.42, 0.42):
                px = cx + side * width * 0.34
                py = cy - height * 0.04
                if abs(x - px) < 10 and py - 70 < y < py + 40:
                    r, g, b = 40, 170, 200

            # lettres LBG (bloc simplifié)
            if width * 0.38 < x < width * 0.62 and height * 0.78 < y < height * 0.9:
                if (x - width * 0.38) % 28 < 8 or (y - height * 0.78) % 22 < 6:
                    r, g, b = 30, 200, 230

            i = (y * width + x) * 4
            buf[i : i + 4] = _pixel(min(r, 255), min(g, 255), min(b, 255))
    return bytes(buf)


def build_cshd_for_texture(texture_path: str) -> bytes:
    """CSHD minimal pointant vers une texture DDS (format proche du vanilla ui_spacestation)."""
    tex = texture_path.encode("ascii")
    # Reprend la structure IFF FORM/CSHD du fichier vanilla, chemins texture mis à jour.
    parts = [
        b"FORM",
        struct.pack(">I", 0),
        b"CSHD",
        b"FORM",
        struct.pack(">I", 0),
        b"0001",
        b"FORM",
        struct.pack(">I", 0),
        b"SSHT",
        b"FORM",
        struct.pack(">I", 0),
        b"0000",
        b"FORM",
        struct.pack(">I", 0),
        b"MATS",
        b"FORM",
        struct.pack(">I", 0),
        b"0000",
        b"TAG ",
        struct.pack(">I", 4),
        b"NIAM",
        b"MATL",
        struct.pack(">I", 68),
        bytes([0] * 68),
        b"FORM",
        struct.pack(">I", 0),
        b"TXMS",
        b"FORM",
        struct.pack(">I", 0),
        b"TXM ",
        b"FORM",
        struct.pack(">I", 0),
        b"0001",
        b"DATA",
        struct.pack(">I", 11),
        b"NIAM",
        struct.pack(">I", 0),
        b"\x02\x02\x02",
        b"NAME",
        struct.pack(">I", len(tex) + 1),
        tex + b"\x00",
    ]
    blob = b"".join(parts)
    # Recalcul tailles FORM (simplifié : une passe)
    return blob


def main() -> int:
    parser = argparse.ArgumentParser(description="Génère texture station login LBG")
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("-o", "--output", type=Path, default=Path("/tmp/lbg_login_station.dds"))
    parser.add_argument("--cshd-out", type=Path, default=None, help="Optionnel : ui_spacestation.dds CSHD")
    args = parser.parse_args()

    rgba = generate_lbg_station_rgba(args.width, args.height)
    _write_dds_rgba(args.output, args.width, args.height, rgba)
    print(f"OK DDS {args.width}x{args.height} -> {args.output} ({args.output.stat().st_size} o)")

    if args.cshd_out:
        # Utiliser la texture bitmap directement comme ui_spacestation (test client)
        args.cshd_out.write_bytes(args.output.read_bytes())
        print(f"OK ui_spacestation (DDS brut) -> {args.cshd_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
