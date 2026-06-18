#!/usr/bin/env python3
"""Extrait un asset binaire d'une archive TRE SWG (format EERT5000 / Prime / Aurora)."""
from __future__ import annotations

import argparse
import struct
import sys
import zlib
from pathlib import Path


def _read_eert_index(path: Path) -> tuple[list[dict], bytes]:
    data = path.read_bytes()
    if len(data) < 36 or data[:8] != b"EERT5000":
        raise ValueError(f"format TRE non supporté (attendu EERT5000): {path}")

    count = struct.unpack_from("<I", data, 8)[0]
    rec_start, rec_comp, rec_size, name_comp, name_size = struct.unpack_from("<IIIII", data, 12)

    rec_block = data[rec_start : rec_start + rec_size]
    if rec_comp == 2:
        rec_block = zlib.decompress(rec_block)

    name_block = data[rec_start + rec_size : rec_start + rec_size + name_size]
    if name_comp == 2:
        name_block = zlib.decompress(name_block)

    names = name_block.split(b"\x00")
    entries: list[dict] = []
    for i in range(count):
        checksum, usize, foff, ctype, csize, name_off = struct.unpack_from("<IIIIII", rec_block, i * 24)
        name = names[name_off].decode("ascii", "replace") if name_off < len(names) else ""
        entries.append(
            {
                "name": name,
                "checksum": checksum,
                "usize": usize,
                "foff": foff,
                "ctype": ctype,
                "csize": csize,
            }
        )
    return entries, data


def extract_from_tre(tre_path: Path, logical_path: str) -> bytes | None:
    target = logical_path.replace("\\", "/").lower()
    entries, data = _read_eert_index(tre_path)
    for entry in entries:
        if entry["name"].lower() != target:
            continue
        payload = data[entry["foff"] : entry["foff"] + entry["csize"]]
        if entry["ctype"] == 2:
            payload = zlib.decompress(payload)
        return payload
    return None


def find_in_directory(tre_dir: Path, logical_path: str) -> tuple[Path, bytes] | None:
    for tre in sorted(tre_dir.glob("*.tre")):
        try:
            payload = extract_from_tre(tre, logical_path)
        except (OSError, ValueError, zlib.error):
            continue
        if payload is not None:
            return tre, payload
    return None


def list_lay_files(tre_dir: Path, filter_sub: str = "") -> list[tuple[str, str]]:
    found: dict[str, str] = {}
    filt = filter_sub.lower()
    for tre in sorted(tre_dir.glob("*.tre")):
        try:
            entries, _ = _read_eert_index(tre)
        except (OSError, ValueError, zlib.error):
            continue
        for entry in entries:
            name = entry["name"]
            low = name.lower()
            if not low.endswith(".lay"):
                continue
            if filt and filt not in low:
                continue
            found.setdefault(low, tre.name)
    return sorted((path, tre) for path, tre in found.items())


def main() -> int:
    parser = argparse.ArgumentParser(description="Extraire un fichier logique d'un TRE SWG (EERT5000)")
    parser.add_argument("tre_or_dir", type=Path, help="Fichier .tre ou dossier contenant des .tre")
    parser.add_argument("logical_path", nargs="?", help="Chemin logique, ex. terrain/poi_small.lay")
    parser.add_argument("-o", "--output", type=Path, help="Fichier de sortie")
    parser.add_argument("--list-lay", action="store_true", help="Lister les .lay du dossier TRE")
    parser.add_argument("--filter", default="", help="Filtre sous-chaîne pour --list-lay")
    args = parser.parse_args()

    src = args.tre_or_dir
    if args.list_lay:
        if not src.is_dir():
            print("ERROR: --list-lay requiert un dossier TRE", file=sys.stderr)
            return 1
        rows = list_lay_files(src, args.filter)
        print(f"# {src} — {len(rows)} fichiers .lay")
        for path, tre in rows:
            print(f"{path}\t{tre}")
        return 0

    if args.logical_path is None:
        parser.error("logical_path requis sauf avec --list-lay")

    if src.is_dir():
        hit = find_in_directory(src, args.logical_path)
        if hit is None:
            print(f"ERROR: {args.logical_path} introuvable dans {src}", file=sys.stderr)
            return 1
        tre_path, payload = hit
    else:
        payload = extract_from_tre(src, args.logical_path)
        tre_path = src
        if payload is None:
            print(f"ERROR: {args.logical_path} introuvable dans {tre_path}", file=sys.stderr)
            return 1

    out = args.output
    if out is None:
        out = Path(args.logical_path.replace("\\", "/"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(payload)
    print(f"OK {args.logical_path} ({len(payload)} o) depuis {tre_path.name} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
