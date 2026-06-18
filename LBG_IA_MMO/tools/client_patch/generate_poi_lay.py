#!/usr/bin/env python3
"""Génère terrain/poi_*.lay (TGEN IFF) pour flatten / cuvette Core3."""
from __future__ import annotations

import argparse
import struct
from pathlib import Path

# Rayons alignés sur noBuildRadius des templates POI SOE (objects.lua base_poi_*)
POI_RADIUS_M = {
    "poi_small.lay": 16.0,
    "poi_medium.lay": 32.0,
    "poi_large.lay": 64.0,
}

# Cuvette Lost Heaven : ~900 m d'emprise (half=9, step=50)
DEFAULT_BOWL_RADIUS_M = 450.0
DEFAULT_BOWL_FEATHER = 0.35


def _chunk(tag: bytes, body: bytes) -> bytes:
    if len(tag) != 4:
        raise ValueError(f"tag IFF invalide: {tag!r}")
    return tag + struct.pack(">I", len(body)) + body


def _form(form_type: bytes, body: bytes) -> bytes:
    return _chunk(b"FORM", form_type + body)


def _data(*parts: bytes) -> bytes:
    return _chunk(b"DATA", b"".join(parts))


def _adta(payload: bytes) -> bytes:
    return _chunk(b"ADTA", payload)


def _ihdr(enabled: int = 1, description: str = "") -> bytes:
    payload = struct.pack(">i", enabled) + description.encode("ascii") + b"\x00"
    return _form(b"IHDR", _form(b"0001", _data(payload)))


def _empty_group(tag: bytes, version: bytes) -> bytes:
    return _form(tag, _form(version, b""))


def _bcir(radius: float, feather_amount: float = 0.25, feather_type: int = 1) -> bytes:
    payload = struct.pack(">fffif", 0.0, 0.0, radius, feather_type, feather_amount)
    return _form(b"BCIR", _form(b"0002", _ihdr() + _data(payload)))


def _ahcn(height: float = 0.0, operation_type: int = 0) -> bytes:
    payload = struct.pack(">if", operation_type, height)
    return _form(b"AHCN", _form(b"0000", _ihdr() + _data(payload)))


def _layer(
    radius: float,
    name: str,
    *,
    op_type: int = 0,
    height: float = 0.0,
    feather: float = 0.25,
) -> bytes:
    adta = struct.pack(">III", 1, 0, 1) + name.encode("ascii") + b"\x00"
    body = _ihdr() + _adta(adta) + _bcir(radius, feather) + _ahcn(height, op_type)
    return _form(b"LAYR", _form(b"0003", body))


def build_tgen_body(layer_bytes: bytes) -> bytes:
    # Ordre TerrainGenerator::parseFromIffStream(0000) : SGRP → FGRP → RGRP → EGRP → MGRP → LAYR
    return (
        _empty_group(b"SGRP", b"0006")
        + _empty_group(b"FGRP", b"0008")
        + _empty_group(b"RGRP", b"0003")
        + _empty_group(b"EGRP", b"0002")
        + _empty_group(b"MGRP", b"0000")
        + layer_bytes
    )


def wrap_tgen(body: bytes) -> bytes:
    """Core3 attend FORM TGEN / FORM 0000 (TerrainGenerator::readObject)."""
    return _form(b"TGEN", _form(b"0000", body))


def build_poi_lay(radius_m: float, layer_name: str = "poi_flatten") -> bytes:
    return wrap_tgen(build_tgen_body(_layer(radius_m, layer_name, op_type=0, height=0.0)))


def build_bowl_lay(
    radius_m: float = DEFAULT_BOWL_RADIUS_M,
    layer_name: str = "poi_bowl",
    *,
    target_z: float = 0.0,
    feather: float = DEFAULT_BOWL_FEATHER,
) -> bytes:
    if abs(target_z) < 0.001:
        return wrap_tgen(
            build_tgen_body(
                _layer(radius_m, layer_name, op_type=4, height=0.0, feather=feather)
            )
        )
    return wrap_tgen(
        build_tgen_body(
            _layer(radius_m, layer_name, op_type=0, height=target_z, feather=feather)
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Génère poi_*.lay et poi_bowl.lay pour Core3")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("content/core3/terrain"),
        help="Dossier de sortie (défaut: content/core3/terrain)",
    )
    parser.add_argument(
        "--bowl-radius",
        type=float,
        default=DEFAULT_BOWL_RADIUS_M,
        help=f"Rayon cuvette poi_bowl.lay (défaut: {DEFAULT_BOWL_RADIUS_M}m)",
    )
    parser.add_argument("--deploy-info", action="store_true", help="Affiche la commande deploy VM")
    args = parser.parse_args()

    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    for filename, radius in POI_RADIUS_M.items():
        payload = build_poi_lay(radius, filename.replace(".lay", ""))
        path = out_dir / filename
        path.write_bytes(payload)
        print(f"OK {path} ({len(payload)} o, radius={radius:.0f}m flatten)")

    bowl = build_bowl_lay(args.bowl_radius)
    bowl_path = out_dir / "poi_bowl.lay"
    bowl_path.write_bytes(bowl)
    print(
        f"OK {bowl_path} ({len(bowl)} o, radius={args.bowl_radius:.0f}m, "
        "cuvette Z=0 absolu, op=4)"
    )

    if args.deploy_info:
        print("\nDeploy VM:")
        print("  bash infra/scripts/deploy_terrain_lay_vm.sh")
        print("  bash infra/scripts/deploy_core3_ia_bridge_vm.sh --restart")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
