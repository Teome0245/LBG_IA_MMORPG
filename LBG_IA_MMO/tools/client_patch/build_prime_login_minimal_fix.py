#!/usr/bin/env python3
"""Patch minimal login Prime : saisie cliquable + libellés STF (vanilla patch_00)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "client_patch"))

from build_aurora_login_ui_fix import _stf_with_upper_aliases  # noqa: E402
from build_prime_login_branding import _fix_login_inc_input  # noqa: E402
from merge_fr_tre import extract_file_from_tre  # noqa: E402
from tre_writer import build_tre  # noqa: E402

DEFAULT_CLIENT = Path("/mnt/j/swgemu/clients/prime-lbg")
OUT_NAME = "patch_prime_login_fix_00.tre"


def build_minimal_login_fix(
    *,
    client_dir: Path,
    out_tre: Path,
    vanilla_ref: Path | None = None,
) -> None:
    ref = vanilla_ref or client_dir
    login_raw = extract_file_from_tre(ref / "patch_00.tre", "ui/ui_loginscreen.inc")
    if not login_raw:
        raise SystemExit(f"ui_loginscreen.inc introuvable dans {ref}/patch_00.tre")

    stf_raw = extract_file_from_tre(client_dir / "patch_fr_00.tre", "string/en/ui.stf")
    if not stf_raw:
        stf_raw = extract_file_from_tre(ref / "patch_00.tre", "string/en/ui.stf")
    if not stf_raw:
        raise SystemExit("string/en/ui.stf introuvable")

    files: dict[str, bytes] = {
        "ui/ui_loginscreen.inc": _fix_login_inc_input(login_raw),
        "string/en/ui.stf": _stf_with_upper_aliases(stf_raw),
    }

    fr_stf = extract_file_from_tre(client_dir / "LBG_French.tre", "string/fr/ui.stf")
    if not fr_stf:
        fr_stf = extract_file_from_tre(client_dir / "patch_fr_00.tre", "string/fr/ui.stf")
    if fr_stf:
        files["string/fr/ui.stf"] = _stf_with_upper_aliases(fr_stf)

    build_tre(out_tre, files, compress=True)
    print(f"OK: {out_tre} ({len(files)} entrées)")
    for path in sorted(files):
        print(f"  · {path}")


def main() -> int:
    p = argparse.ArgumentParser(description="TRE correctif login minimal (vanilla)")
    p.add_argument("--client-dir", type=Path, default=DEFAULT_CLIENT)
    p.add_argument("--vanilla-ref", type=Path, default=None)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()
    out = args.out or (args.client_dir / OUT_NAME)
    build_minimal_login_fix(
        client_dir=args.client_dir,
        out_tre=out,
        vanilla_ref=args.vanilla_ref,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
