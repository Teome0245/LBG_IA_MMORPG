#!/usr/bin/env python3
"""Patch login Aurora : STF FR (patch_fr) + ui_loginscreen.inc corrigé."""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "client_patch"))
sys.path.insert(0, str(ROOT.parent / "new_mmo" / "modding_tools"))

from merge_fr_tre import extract_file_from_tre, extract_all_from_tre  # noqa: E402
from tre_writer import build_tre  # noqa: E402
from translate_all import read_stf, write_stf  # noqa: E402


def _load_stf(raw: bytes) -> tuple[int, list[dict]]:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".stf") as f:
        f.write(raw)
        p = Path(f.name)
    try:
        return read_stf(str(p))
    finally:
        p.unlink(missing_ok=True)


def _stf_with_upper_aliases(raw: bytes) -> bytes:
    """Duplique cpt_login → CPT_LOGIN etc. pour LocalText='[@CPT_LOGIN]'."""
    flag, entries = _load_stf(raw)
    by_key = {e["key"]: e for e in entries}
    aliases = {
        "CPT_LOGIN": "cpt_login",
        "USERNAME": "username",
        "PASSWORD": "password",
        "NEXT": "next",
        "BACK": "back",
        "CPT_LOGIN_FAIL": "cpt_login_fail",
        "MSG_LOGIN_FAIL": "msg_login_fail",
    }
    max_id = max((e["id"] for e in entries), default=0)
    for upper, lower in aliases.items():
        if upper in by_key or lower not in by_key:
            continue
        max_id += 1
        src = by_key[lower]
        entries.append(
            {
                "id": max_id,
                "key": upper,
                "value": src["value"],
                "unknown": src.get("unknown", 0xFFFFFFFF),
            }
        )
        by_key[upper] = entries[-1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=".stf") as f:
        out = Path(f.name)
    try:
        write_stf(flag, entries, str(out))
        return out.read_bytes()
    finally:
        out.unlink(missing_ok=True)


def _fix_login_inc(raw: bytes) -> bytes:
    text = raw.decode("latin-1", errors="replace")
    repl = {
        "[@CPT_LOGIN]": "[@cpt_login]",
        "[@USERNAME]": "[@username]",
        "[@PASSWORD]": "[@password]",
        "[@NEXT]": "[@next]",
        "[@BACK]": "[@back]",
        "[@CPT_LOGIN_FAIL]": "[@cpt_login_fail]",
        "[@MSG_LOGIN_FAIL]": "[@msg_login_fail]",
    }
    for old, new in repl.items():
        text = text.replace(old, new)
    return text.encode("latin-1", errors="replace")


def build_patch(
    *,
    aurora_dir: Path,
    patch_fr: Path,
    aur_french: Path,
    out_tre: Path,
    include_login_inc: bool = False,
) -> None:
    """STF FR + alias majuscules (CPT_LOGIN). Ne pas écraser ui_loginscreen.inc par défaut."""
    stf_raw = extract_file_from_tre(patch_fr, "string/en/ui.stf")
    if not stf_raw:
        raise SystemExit(f"string/en/ui.stf introuvable dans {patch_fr}")

    files: dict[str, bytes] = {
        "string/en/ui.stf": _stf_with_upper_aliases(stf_raw),
    }

    fr_ui = extract_file_from_tre(aur_french, "string/fr/ui.stf")
    if fr_ui:
        files["string/fr/ui.stf"] = _stf_with_upper_aliases(fr_ui)
    elif (fr_patch := extract_file_from_tre(patch_fr, "string/fr/ui.stf")):
        files["string/fr/ui.stf"] = fr_patch

    if include_login_inc:
        inc_src = aurora_dir / "aur_patch_013_configurable_02.tre"
        inc_raw = extract_file_from_tre(inc_src, "ui/ui_loginscreen.inc")
        if not inc_raw:
            raise SystemExit(f"ui_loginscreen.inc introuvable dans {inc_src}")
        files["ui/ui_loginscreen.inc"] = _fix_login_inc(inc_raw)

    build_tre(out_tre, files, compress=True)
    print(f"OK: {out_tre} ({len(files)} entrées)")


def main() -> int:
    p = argparse.ArgumentParser(description="TRE correctif login Aurora (UI FR)")
    p.add_argument(
        "--aurora-dir",
        type=Path,
        default=Path("/mnt/j/swgemu/StarWarsGalaxies - AURORA"),
    )
    p.add_argument(
        "--patch-fr",
        type=Path,
        default=Path("/mnt/j/swgemu/clients/prime-lbg/patch_fr_00.tre"),
    )
    p.add_argument(
        "--aur-french",
        type=Path,
        default=Path("/mnt/j/swgemu/StarWarsGalaxies - AURORA/Aur_French.tre"),
    )
    p.add_argument(
        "--include-login-inc",
        action="store_true",
        help="Inclure ui_loginscreen.inc modifié (déconseillé : libellés vides)",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Défaut: <aurora-dir>/patch_aurora_ui_fr_00.tre",
    )
    args = p.parse_args()
    out = args.out or (args.aurora_dir / "patch_aurora_ui_fr_00.tre")
    build_patch(
        aurora_dir=args.aurora_dir,
        patch_fr=args.patch_fr,
        aur_french=args.aur_french,
        out_tre=out,
        include_login_inc=args.include_login_inc,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
