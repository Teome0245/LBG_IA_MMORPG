#!/usr/bin/env python3
"""Déplace un joueur offline en patchant sceneobjects.db (Berkeley DB 5.3 + zlib).

Usage typique : sortir Gally de Mos Eisley (>1000 objets custom).
"""
from __future__ import annotations

import argparse
import shutil
import struct
import sys
import zlib
from datetime import datetime
from pathlib import Path


def pack_oid(oid: int) -> bytes:
    return struct.pack("<Q", oid)


def decompress_object(raw: bytes) -> bytes:
    return zlib.decompress(raw)


def compress_object(data: bytes) -> bytes:
    return zlib.compress(data, 6)


def patch_all_triplets(blob: bytes, old_xyz: tuple[float, float, float], new_xyz: tuple[float, float, float], tol: float = 2.0) -> tuple[bytes, int]:
    """Remplace les triplets (x,z,y) proches de old_xyz."""
    ox, oz, oy = old_xyz
    nx, nz, ny = new_xyz
    out = bytearray(blob)
    count = 0
    i = 0
    while i < len(out) - 11:
        x, z, y = struct.unpack("<fff", out[i : i + 12])
        if abs(x - ox) <= tol and abs(z - oz) <= tol and abs(y - oy) <= tol:
            out[i : i + 12] = struct.pack("<fff", nx, nz, ny)
            count += 1
            i += 12
            continue
        i += 1
    return bytes(out), count


def main() -> int:
    ap = argparse.ArgumentParser(description="Relocate offline player in sceneobjects.db")
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--oid", type=int, required=True)
    ap.add_argument("--old-x", type=float, required=True)
    ap.add_argument("--old-z", type=float, default=0.0)
    ap.add_argument("--old-y", type=float, required=True)
    ap.add_argument("--new-x", type=float, required=True)
    ap.add_argument("--new-z", type=float, required=True)
    ap.add_argument("--new-y", type=float, required=True)
    ap.add_argument("--tolerance", type=float, default=5.0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    try:
        from berkeleydb import db as bdb  # type: ignore
    except ImportError:
        print("ERROR: pip3 install --user berkeleydb", file=sys.stderr)
        return 2

    db_path = args.db.resolve()
    if not db_path.is_file():
        print(f"ERROR: {db_path} introuvable", file=sys.stderr)
        return 1

    key = pack_oid(args.oid)
    database = bdb.DB()
    database.open(str(db_path), None, bdb.DB_HASH, 0)

    try:
        raw = database.get(key)
        if raw is None:
            print(f"ERROR: OID {args.oid} absent", file=sys.stderr)
            return 1

        dec = decompress_object(bytes(raw))
        old_xyz = (args.old_x, args.old_z, args.old_y)
        new_xyz = (args.new_x, args.new_z, args.new_y)
        patched, n = patch_all_triplets(dec, old_xyz, new_xyz, tol=args.tolerance)
        if n == 0:
            print(f"ERROR: aucun triplet proche de {old_xyz} (tol={args.tolerance})", file=sys.stderr)
            return 1

        new_raw = compress_object(patched)

        if args.dry_run:
            print(f"DRY-RUN OK — OID {args.oid} : {n} triplet(s) {old_xyz} → {new_xyz}")
            return 0

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = db_path.with_suffix(f".db.bak_relocate_{ts}")
        shutil.copy2(db_path, backup)
        print(f"Backup : {backup}")

        database.put(key, new_raw)
        print(f"OK — OID {args.oid} : {n} triplet(s) {old_xyz} → {new_xyz}")
        return 0
    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
