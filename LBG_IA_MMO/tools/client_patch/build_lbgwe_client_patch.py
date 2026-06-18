#!/usr/bin/env python3
"""
Patch client Prime : ajoute /lbgwe dans client_command_table.iff
et produit patch_lbg_00.tre pour le canal launchpad Prime.

Usage :
  python3 tools/client_patch/build_lbgwe_client_patch.py
  SWG_SOURCE_IFF=/chemin/client_command_table.iff python3 ...
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "client_patch"))

from datatable_iff import read_dtii, write_dtii  # noqa: E402
from tre_writer import build_tre  # noqa: E402

DEFAULT_SOURCE = (
    ROOT.parent.parent / "new_mmo/modding_tools/patch_fr_workspace/orig_extracted/datatables/command/client_command_table.iff"
)
PATCH_BUILD = ROOT / "client-prime-lbg/patch_build"
PATCH_TRE = ROOT / "infra/client-patch-server/patches/prime/patch_lbg_00.tre"
IFF_TRE_PATH = "datatables/command/client_command_table.iff"
COMMAND_NAME = "lbgwe"
TEMPLATE_COMMAND = "dumpPausedCommands"


def _validate_tre(tre_path: Path, command_name: str) -> None:
    """Vérifie que le TRE généré est lisible (offset absolu + IFF)."""
    import struct
    import zlib
    import tempfile

    data = tre_path.read_bytes()
    magic = struct.unpack("<II", data[:8])
    if magic != (0x54524545, 0x30303035):
        raise SystemExit(f"TRE magic invalide: {magic}")
    _m0, _m1, _records, record_start, rc, rcomp, _nc, _ncomp, _nuncomp = struct.unpack(
        "<IIIIIIIII", data[:36]
    )
    rb = data[record_start : record_start + rcomp]
    rd = zlib.decompress(rb) if rc == 2 else rb
    _cs, uncomp, file_off, comp_type, comp_size, _no = struct.unpack("<IIIIII", rd[:24])
    if file_off < 36:
        raise SystemExit(f"TRE invalide (file_offset={file_off}, attendu >= 36)")
    raw = data[file_off : file_off + comp_size]
    payload = zlib.decompress(raw) if comp_type == 2 else raw
    if len(payload) != uncomp:
        raise SystemExit(f"TRE invalide (taille décompressée {len(payload)} != {uncomp})")
    with tempfile.NamedTemporaryFile(suffix=".iff", delete=False) as tmp:
        tmp.write(payload)
        tmp_path = tmp.name
    cols, _types, rows = read_dtii(tmp_path)
    names = [str(r[cols.index("commandName")]) for r in rows]
    Path(tmp_path).unlink(missing_ok=True)
    if command_name not in names:
        raise SystemExit(f"TRE invalide : {command_name} absent de client_command_table")


def patch_command_table(source_iff: Path, dest_iff: Path) -> dict:
    cols, types, rows = read_dtii(str(source_iff))
    name_idx = cols.index("commandName")
    names = [str(r[name_idx]) for r in rows]
    if COMMAND_NAME in names:
        return {"added": False, "rows": len(rows), "source": str(source_iff)}

    template_idx = names.index(TEMPLATE_COMMAND)
    new_row = list(rows[template_idx])
    new_row[name_idx] = COMMAND_NAME
    if "cppHook" in cols:
        new_row[cols.index("cppHook")] = COMMAND_NAME
    if "scriptHook" in cols:
        new_row[cols.index("scriptHook")] = ""
    if "stringId" in cols:
        new_row[cols.index("stringId")] = ""
    if "visible" in cols:
        new_row[cols.index("visible")] = 2
    if "godLevel" in cols:
        new_row[cols.index("godLevel")] = 0

    rows.append(new_row)
    dest_iff.parent.mkdir(parents=True, exist_ok=True)
    write_dtii(str(dest_iff), cols, types, rows)
    return {"added": True, "rows": len(rows), "source": str(source_iff), "template": TEMPLATE_COMMAND}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build patch_lbg_00.tre (/lbgwe client)")
    parser.add_argument("--source-iff", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--patch-build", type=Path, default=PATCH_BUILD)
    parser.add_argument("--output-tre", type=Path, default=PATCH_TRE)
    args = parser.parse_args()

    source_iff = Path(
        __import__("os").environ.get("SWG_SOURCE_IFF", str(args.source_iff))
    )
    if not source_iff.is_file():
        print(f"ERROR: IFF source introuvable: {source_iff}", file=sys.stderr)
        return 1

    dest_iff = args.patch_build / "datatables/command/client_command_table.iff"
    meta = patch_command_table(source_iff, dest_iff)

    with dest_iff.open("rb") as f:
        iff_bytes = f.read()

    build_tre(args.output_tre, {IFF_TRE_PATH: iff_bytes})
    _validate_tre(args.output_tre, COMMAND_NAME)

    manifest = {
        "command": COMMAND_NAME,
        "tre_path": IFF_TRE_PATH,
        "tre_file": args.output_tre.name,
        "rows": meta["rows"],
        "added": meta["added"],
        "template": meta.get("template"),
        "source_iff": meta["source"],
    }
    meta_path = args.output_tre.with_suffix(".json")
    meta_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"OK patch {COMMAND_NAME} -> {args.output_tre}")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
