#!/usr/bin/env python3
"""Création minimale de fichiers TRE (TREE 0005) pour patches client SWG."""
from __future__ import annotations

import hashlib
import struct
import zlib
from pathlib import Path


def crc32_bzip2(data: bytes) -> int:
    crc = 0xFFFFFFFF
    for b in data:
        crc ^= b << 24
        for _ in range(8):
            if crc & 0x80000000:
                crc = ((crc << 1) ^ 0x04C11DB7) & 0xFFFFFFFF
            else:
                crc = (crc << 1) & 0xFFFFFFFF
    return crc ^ 0xFFFFFFFF


def build_tre(output_path: str | Path, files: dict[str, bytes], compress: bool = True) -> None:
    """files: chemin TRE (posix, minuscules) -> contenu binaire."""
    entries = []
    data_blob = bytearray()
    names_blob = bytearray()

    for tre_path in sorted(files.keys(), key=lambda p: crc32_bzip2(p.encode("ascii"))):
        payload = files[tre_path]
        if compress:
            compressed = zlib.compress(payload)
            compression_type = 2
            compressed_size = len(compressed)
            uncompressed_size = len(payload)
            stored = compressed
        else:
            compression_type = 0
            compressed_size = len(payload)
            uncompressed_size = len(payload)
            stored = payload

        # Offset absolu dans le fichier TRE (données après l'en-tête 36 octets)
        file_offset = 36 + len(data_blob)
        data_blob.extend(stored)
        name_offset = len(names_blob)
        names_blob.extend(tre_path.encode("ascii") + b"\x00")

        entries.append(
            {
                "path": tre_path,
                "checksum": crc32_bzip2(tre_path.encode("ascii")),
                "uncompressed_size": uncompressed_size,
                "file_offset": file_offset,
                "compression_type": compression_type,
                "compressed_size": compressed_size,
                "name_offset": name_offset,
                "md5": hashlib.md5(stored).digest(),
            }
        )

    record_data = bytearray()
    for entry in entries:
        record_data.extend(
            struct.pack(
                "<IIIIII",
                entry["checksum"],
                entry["uncompressed_size"],
                entry["file_offset"],
                entry["compression_type"],
                entry["compressed_size"],
                entry["name_offset"],
            )
        )

    record_block = zlib.compress(bytes(record_data))
    name_block = zlib.compress(bytes(names_blob))
    hash_block = b"".join(entry["md5"] for entry in entries)

    record_start = 36 + len(data_blob)
    # En-tête identique aux .tre SWG (fourcc LE) : 'TREE' + '0005', pas l'ASCII "TREE0005"
    header = struct.pack(
        "<IIIIIIIII",
        0x54524545,  # 'TREE'
        0x30303035,  # '0005' (même convention que patch_fr_00.tre)
        len(entries),
        record_start,
        2,
        len(record_block),
        2,
        len(name_block),
        len(names_blob),
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as f:
        f.write(header)
        f.write(data_blob)
        f.write(record_block)
        f.write(name_block)
        f.write(hash_block)
