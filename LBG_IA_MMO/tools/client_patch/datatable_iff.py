#!/usr/bin/env python3
"""Lecture / écriture des datatables SWG (FORM DTII / 0001)."""
from __future__ import annotations

import struct
from typing import Any


def _read_cstr(data: bytes, off: int) -> tuple[str, int]:
    end = data.index(b"\x00", off)
    return data[off:end].decode("ascii"), end + 1


def _write_cstr(value: str) -> bytes:
    return value.encode("ascii") + b"\x00"


def _read_cell(data: bytes, off: int, col_type: str) -> tuple[Any, int]:
    if col_type == "s":
        return _read_cstr(data, off)
    if col_type == "f":
        return struct.unpack_from("<f", data, off)[0], off + 4
    if col_type == "h":
        return struct.unpack_from("<I", data, off)[0], off + 4
    if col_type == "b":
        return bool(struct.unpack_from("<I", data, off)[0]), off + 4
    return struct.unpack_from("<i", data, off)[0], off + 4


def _write_cell(value: Any, col_type: str) -> bytes:
    if col_type == "s":
        return _write_cstr(str(value or ""))
    if col_type == "f":
        return struct.pack("<f", float(value))
    if col_type == "h":
        return struct.pack("<I", int(value) & 0xFFFFFFFF)
    if col_type == "b":
        return struct.pack("<I", 1 if value else 0)
    return struct.pack("<i", int(value))


def read_dtii(path: str) -> tuple[list[str], list[str], list[list[Any]]]:
    with open(path, "rb") as f:
        data = f.read()

    off = 0
    assert data[off : off + 4] == b"FORM"
    off += 8
    assert data[off : off + 4] == b"DTII"
    off += 4
    assert data[off : off + 4] == b"FORM"
    off += 8
    assert data[off : off + 4] == b"0001"
    off += 4

    assert data[off : off + 4] == b"COLS"
    off += 8
    ncols = struct.unpack_from("<I", data, off)[0]
    off += 4
    cols: list[str] = []
    for _ in range(ncols):
        s, off = _read_cstr(data, off)
        cols.append(s)

    assert data[off : off + 4] == b"TYPE"
    off += 8
    types: list[str] = []
    for _ in range(ncols):
        s, off = _read_cstr(data, off)
        types.append(s[0] if s else "i")

    assert data[off : off + 4] == b"ROWS"
    off += 8
    nrows = struct.unpack_from("<I", data, off)[0]
    off += 4
    rows: list[list[Any]] = []
    for _ in range(nrows):
        row: list[Any] = []
        for col_type in types:
            val, off = _read_cell(data, off, col_type)
            row.append(val)
        rows.append(row)

    return cols, types, rows


def write_dtii(path: str, cols: list[str], types: list[str], rows: list[list[Any]]) -> None:
    cols_chunk = struct.pack("<I", len(cols))
    for name in cols:
        cols_chunk += _write_cstr(name)

    type_chunk = b""
    for col_type in types:
        type_chunk += _write_cstr(col_type)

    rows_chunk = struct.pack("<I", len(rows))
    for row in rows:
        for value, col_type in zip(row, types):
            rows_chunk += _write_cell(value, col_type)

    def _chunk(tag: bytes, payload: bytes) -> bytes:
        return tag + struct.pack(">I", len(payload)) + payload

    inner = _chunk(b"COLS", cols_chunk) + _chunk(b"TYPE", type_chunk) + _chunk(b"ROWS", rows_chunk)
    version_payload = b"0001" + inner
    version_form = b"FORM" + struct.pack(">I", len(version_payload)) + version_payload
    dtii_payload = b"DTII" + version_form
    outer = b"FORM" + struct.pack(">I", len(dtii_payload)) + dtii_payload

    with open(path, "wb") as f:
        f.write(outer)
