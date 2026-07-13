#!/usr/bin/env python3
"""Génère un GLB placeholder minimal (cube ~1.8m) pour la sonde infographiste."""
from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "avatars" / "base" / "human_male_base.glb"


def _pack_glb(gltf: dict, bin_blob: bytes) -> bytes:
    json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_pad = (4 - (len(json_bytes) % 4)) % 4
    json_bytes += b" " * json_pad
    bin_pad = (4 - (len(bin_blob) % 4)) % 4
    bin_blob = bin_blob + (b"\x00" * bin_pad)

    json_chunk_len = 8 + len(json_bytes)
    bin_chunk_len = 8 + len(bin_blob)
    total = 12 + json_chunk_len + bin_chunk_len

    out = bytearray()
    out += struct.pack("<III", 0x46546C67, 2, total)
    out += struct.pack("<I", json_chunk_len)
    out += struct.pack("<I", 0x4E4F534A)
    out += json_bytes
    out += struct.pack("<I", bin_chunk_len)
    out += struct.pack("<I", 0x004E4942)
    out += bin_blob
    return bytes(out)


def build_cube_glb() -> bytes:
    # Cube centré, ~1.8m haut (Y-up glTF)
    vertices = [
        -0.3, 0.0, -0.3,
        0.3, 0.0, -0.3,
        0.3, 1.8, -0.3,
        -0.3, 1.8, -0.3,
        -0.3, 0.0, 0.3,
        0.3, 0.0, 0.3,
        0.3, 1.8, 0.3,
        -0.3, 1.8, 0.3,
    ]
    indices = [
        0, 1, 2, 2, 3, 0,
        4, 5, 6, 6, 7, 4,
        0, 4, 5, 5, 1, 0,
        2, 6, 7, 7, 3, 2,
        1, 5, 6, 6, 2, 1,
        0, 3, 7, 7, 4, 0,
    ]
    bin_blob = struct.pack(f"<{len(vertices)}f", *vertices)
    bin_blob += struct.pack(f"<{len(indices)}H", *indices)
    gltf = {
        "asset": {"version": "2.0", "generator": "lbg-placeholder"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "human_male_placeholder"}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": 8,
                "type": "VEC3",
                "min": [-0.3, 0.0, -0.3],
                "max": [0.3, 1.8, 0.3],
            },
            {
                "bufferView": 1,
                "componentType": 5123,
                "count": 36,
                "type": "SCALAR",
            },
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(vertices) * 4},
            {
                "buffer": 0,
                "byteOffset": len(vertices) * 4,
                "byteLength": len(indices) * 2,
            },
        ],
        "buffers": [{"byteLength": len(vertices) * 4 + len(indices) * 2}],
    }
    return _pack_glb(gltf, bin_blob)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(build_cube_glb())
    print(f"OK — {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
