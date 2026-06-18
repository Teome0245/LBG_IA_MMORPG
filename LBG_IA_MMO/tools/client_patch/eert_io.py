#!/usr/bin/env python3
"""Lecture / réécriture archives TRE SWG (EERT5000)."""
from __future__ import annotations

import shutil
from pathlib import Path

from merge_fr_tre import extract_all_from_tre
from tre_writer import build_tre


def replace_and_write(
    source_tre: Path,
    output_tre: Path,
    replacements: dict[str, bytes],
    *,
    add: dict[str, bytes] | None = None,
) -> dict[str, int]:
    files = extract_all_from_tre(source_tre)
    stats = {"replaced": 0, "added": 0, "total": 0}
    for logical, payload in replacements.items():
        key = logical.lower()
        if key not in files:
            raise KeyError(f"asset absent de {source_tre.name}: {logical}")
        files[key] = payload
        stats["replaced"] += 1
    for logical, payload in (add or {}).items():
        key = logical.lower()
        if key in files:
            stats["replaced"] += 1
        else:
            stats["added"] += 1
        files[key] = payload
    stats["total"] = len(files)
    output_tre.parent.mkdir(parents=True, exist_ok=True)
    build_tre(output_tre, files, compress=True)
    return stats


def patch_binary_slot(tre_path: Path, logical_path: str, new_payload: bytes) -> None:
    """Remplace un asset inline (slot fixe dans le blob data du TRE)."""
    import struct
    import zlib

    backup = Path(str(tre_path) + ".bak.lbg")
    if not backup.exists():
        shutil.copy2(tre_path, backup)

    data = bytearray(tre_path.read_bytes())
    count = struct.unpack_from("<I", data, 8)[0]
    rec_start, rc, rs, nc, ns = struct.unpack_from("<IIIII", data, 12)
    rb = data[rec_start : rec_start + rs]
    if rc == 2:
        rb = zlib.decompress(rb)
    nb = data[rec_start + rs : rec_start + rs + ns]
    if nc == 2:
        nb = zlib.decompress(nb)
    names = nb.split(b"\x00")

    target = logical_path.lower()
    for i in range(count):
        _cs, usize, foff, ctype, csize, name_off = struct.unpack_from("<IIIIII", rb, i * 24)
        name = names[name_off].decode("ascii", "replace") if name_off < len(names) else ""
        if name.lower() != target:
            continue
        slot = csize if csize else usize
        if len(new_payload) > slot:
            raise ValueError(f"{logical_path}: {len(new_payload)} o > slot {slot} o")
        if ctype != 0:
            raise ValueError(f"{logical_path}: compression {ctype} non supportée inline")
        end = foff + slot
        data[foff:end] = new_payload + bytes(end - foff - len(new_payload))
        tre_path.write_bytes(data)
        return
    raise KeyError(f"{logical_path} introuvable dans {tre_path}")
