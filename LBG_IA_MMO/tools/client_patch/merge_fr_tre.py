#!/usr/bin/env python3
"""Fusionne patch_fr_00.tre + Aur_French.tre → patch_fr_merged_00.tre (meilleure FR par entrée STF)."""
from __future__ import annotations

import argparse
import re
import struct
import sys
import tempfile
import zlib
from pathlib import Path

# translate_all (new_mmo modding_tools)
_MOD_TOOLS = Path(__file__).resolve().parents[3].parent / "new_mmo" / "modding_tools"
if _MOD_TOOLS.is_dir():
    sys.path.insert(0, str(_MOD_TOOLS))
from translate_all import read_stf, write_stf  # noqa: E402

from tre_writer import build_tre  # noqa: E402

TOKEN_REGEX = re.compile(r"%[A-Z]{2}|\\#[a-zA-Z0-9_]+")

FRENCH_HINTS = re.compile(
    r"\b(le|la|les|un|une|des|du|de|vous|pour|avec|est|pas|dans|sur|que|qui|"
    r"cette|cet|vos|votre|aux|au|où|être|avoir|êtes|nous|ils|elles|mais|ou|"
    r"enchères|spatioport|crédits|compétence|personnage)\b",
    re.I,
)
ENGLISH_HINTS = re.compile(
    r"\b(the|you|your|have|this|with|are|not|from|that|will|been|their|"
    r"auction|starport|credits|skill|character|cannot|please|click)\b",
    re.I,
)


def read_tre_index(tre_path: Path) -> tuple[bytes, list[str], bytes]:
    """Retourne (record_data, names, raw_file_bytes header+data pour seek)."""
    data = tre_path.read_bytes()
    if len(data) < 36:
        raise ValueError(f"TRE trop petit: {tre_path}")
    magic = data[:8]
    if magic not in (b"TREE0005", b"EERT5000"):
        raise ValueError(f"Magic TRE inconnu {magic!r} dans {tre_path}")

    (
        _magic,
        records,
        record_start,
        record_compression,
        record_compressed,
        name_compression,
        name_compressed,
        _name_uncompressed,
    ) = struct.unpack("<8sIIIIIII", data[:36])

    record_block = data[record_start : record_start + record_compressed]
    record_data = zlib.decompress(record_block) if record_compression == 2 else record_block

    names_start = record_start + record_compressed
    name_block = data[names_start : names_start + name_compressed]
    names_raw = zlib.decompress(name_block) if name_compression == 2 else name_block
    names = [n.decode("utf-8", errors="replace") for n in names_raw.split(b"\x00") if n]
    if len(names) != records:
        raise ValueError(f"{tre_path}: {records} records vs {len(names)} noms")
    return record_data, names, data


def extract_file_from_tre(tre_path: Path, tre_name: str) -> bytes | None:
    record_data, names, raw = read_tre_index(tre_path)
    target = tre_name.lower()
    for i, name in enumerate(names):
        if name.lower() != target:
            continue
        checksum, data_size, data_offset, data_compression, _du, _no = struct.unpack(
            "<IIIIII", record_data[i * 24 : i * 24 + 24]
        )
        compressed = raw[data_offset : data_offset + data_size]
        return zlib.decompress(compressed) if data_compression == 2 else compressed
    return None


def extract_all_from_tre(tre_path: Path) -> dict[str, bytes]:
    record_data, names, raw = read_tre_index(tre_path)
    out: dict[str, bytes] = {}
    for i, name in enumerate(names):
        _cs, data_size, data_offset, data_compression, _du, _no = struct.unpack(
            "<IIIIII", record_data[i * 24 : i * 24 + 24]
        )
        compressed = raw[data_offset : data_offset + data_size]
        try:
            payload = zlib.decompress(compressed) if data_compression == 2 else compressed
        except zlib.error:
            continue
        out[name.lower()] = payload
    return out


def french_quality_score(text: str, key: str) -> float:
    """Score plus haut = meilleure traduction FR pour le client."""
    if not text or not text.strip():
        return 0.0
    t = text.strip()
    if t == key:
        return 0.5
    # Chemins / assets : garder tel quel
    if t.startswith(("loading\\", "sound\\")) or re.search(r"\.(tga|iff|dds|wav|mp3)$", t, re.I):
        return 50.0
    if not re.search(r"[a-zA-Z]", t):
        return 30.0

    score = 1.0
    if re.search(r"[éèêàçùôîëïüÉÈÊÀÇÙÔÎËÏÜ]", t):
        score += 4.0
    fr_hits = len(FRENCH_HINTS.findall(t))
    en_hits = len(ENGLISH_HINTS.findall(t))
    score += fr_hits * 1.2
    score -= en_hits * 1.5
    # Pénalité texte quasi identique à de l'anglais (pas d'accents + mots EN)
    if en_hits >= 2 and not re.search(r"[éèêàçùôî]", t):
        score -= 3.0
    # Légère préférence pour traductions plus complètes (souvent patch_fr)
    score += min(len(t) / 200.0, 1.0)
    return score


def merge_stf_bytes(
    patch_bytes: bytes | None,
    aur_bytes: bytes | None,
    prefer: str,
) -> tuple[bytes, dict]:
    """Fusionne deux STF ; prefer='patch' | 'aurora' en cas d'égalité."""
    entries_by_key: dict[str, dict] = {}
    sources: list[tuple[str, bytes]] = []
    if patch_bytes:
        sources.append(("patch", patch_bytes))
    if aur_bytes:
        sources.append(("aurora", aur_bytes))

    if not sources:
        raise ValueError("Aucun STF à fusionner")
    if len(sources) == 1:
        src = sources[0][0]
        st = {"only_patch": 0, "only_aurora": 0, "pick_patch": 0, "pick_aurora": 0, "tie": 0}
        if src == "patch":
            st["only_patch"] = 1
        else:
            st["only_aurora"] = 1
        return sources[0][1], st

    parsed: dict[str, list[tuple[str, dict]]] = {}
    for src, blob in sources:
        with tempfile.NamedTemporaryFile(suffix=".stf", delete=False) as tmp:
            tmp.write(blob)
            tmp_path = tmp.name
        try:
            _flag, entries = read_stf(tmp_path)
        except (ValueError, struct.error, OSError) as e:
            print(f"    WARN STF illisible ({src}): {e}")
            continue
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        for e in entries:
            parsed.setdefault(e["key"], []).append((src, e))

    if not parsed:
        return sources[0][1], {
            "only_patch": 1 if sources[0][0] == "patch" else 0,
            "only_aurora": 1 if sources[0][0] == "aurora" else 0,
            "pick_patch": 0,
            "pick_aurora": 0,
            "tie": 0,
        }

    merged = []
    stats = {"pick_patch": 0, "pick_aurora": 0, "only_patch": 0, "only_aurora": 0, "tie": 0}

    all_keys = sorted(parsed.keys())
    for key in all_keys:
        cands = parsed[key]
        if len(cands) == 1:
            src, e = cands[0]
            merged.append(e)
            if src == "patch":
                stats["only_patch"] += 1
            else:
                stats["only_aurora"] += 1
            continue

        best = None
        best_score = -1e9
        for src, e in cands:
            sc = french_quality_score(e["value"], key)
            if src == prefer:
                sc += 0.15
            if sc > best_score:
                best_score = sc
                best = (src, e)
        src, e = best
        merged.append(e)
        if len(cands) == 2:
            other_src = "aurora" if src == "patch" else "patch"
            if abs(
                french_quality_score(e["value"], key)
                - french_quality_score(
                    next(x[1]["value"] for x in cands if x[0] == other_src), key
                )
            ) < 0.01:
                stats["tie"] += 1
            elif src == "patch":
                stats["pick_patch"] += 1
            else:
                stats["pick_aurora"] += 1

    merged.sort(key=lambda x: x["id"])
    flag = 0
    with tempfile.NamedTemporaryFile(suffix=".stf", delete=False) as tmp:
        out_path = tmp.name
    write_stf(flag, merged, out_path)
    result = Path(out_path).read_bytes()
    Path(out_path).unlink(missing_ok=True)
    return result, stats  # type: ignore[return-value]


def merge_tre_archives(
    patch_tre: Path,
    aur_tre: Path,
    out_tre: Path,
    prefer: str = "patch",
) -> dict:
    print(f"Lecture {patch_tre.name}…")
    patch_files = extract_all_from_tre(patch_tre)
    print(f"  {len(patch_files)} fichiers")
    print(f"Lecture {aur_tre.name}…")
    aur_files = extract_all_from_tre(aur_tre)
    print(f"  {len(aur_files)} fichiers")

    all_paths = sorted(set(patch_files) | set(aur_files))
    merged_files: dict[str, bytes] = {}
    report = {
        "total": len(all_paths),
        "stf_merged": 0,
        "binary_copy": 0,
        "pick_patch": 0,
        "pick_aurora": 0,
        "only_patch": 0,
        "only_aurora": 0,
    }

    for i, path in enumerate(all_paths):
        pb = patch_files.get(path) or None
        ab = aur_files.get(path) or None
        if pb is not None and len(pb) == 0:
            pb = None
        if ab is not None and len(ab) == 0:
            ab = None
        if path.endswith(".stf"):
            try:
                blob, st = merge_stf_bytes(pb, ab, prefer)
            except (ValueError, OSError) as e:
                print(f"  WARN skip {path}: {e}")
                blob = pb or ab
                st = {}
            if blob is None:
                continue
            merged_files[path] = blob
            report["stf_merged"] += 1
            for k in ("pick_patch", "pick_aurora", "only_patch", "only_aurora"):
                report[k] += st.get(k, 0)
        else:
            payload = pb or ab
            if payload is None:
                continue
            merged_files[path] = payload
            report["binary_copy"] += 1
        if (i + 1) % 2000 == 0:
            print(f"  fusion {i + 1}/{len(all_paths)}…")

    print(f"Écriture {out_tre} ({len(merged_files)} fichiers)…")
    out_tre.parent.mkdir(parents=True, exist_ok=True)
    build_tre(out_tre, merged_files, compress=True)
    print("Terminé.")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Fusion patch_fr + Aur_French → TRE optimal")
    parser.add_argument(
        "--patch",
        type=Path,
        default=Path("/mnt/j/swgemu/clients/prime-lbg/patch_fr_00.tre"),
    )
    parser.add_argument(
        "--aurora",
        type=Path,
        default=Path("/mnt/j/swgemu/StarWarsGalaxies - AURORA/Aur_French.tre"),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("/mnt/j/swgemu/clients/prime-lbg/patch_fr_merged_00.tre"),
    )
    parser.add_argument(
        "--prefer",
        choices=("patch", "aurora"),
        default="patch",
        help="En cas d'égalité de score FR, favoriser cette source (défaut: patch LBG)",
    )
    args = parser.parse_args()

    if not args.patch.is_file():
        print(f"ERREUR: introuvable {args.patch}", file=sys.stderr)
        return 1
    if not args.aurora.is_file():
        print(f"ERREUR: introuvable {args.aurora}", file=sys.stderr)
        return 1

    report = merge_tre_archives(args.patch, args.aurora, args.out, args.prefer)
    print("\n--- Rapport ---")
    for k, v in sorted(report.items()):
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
