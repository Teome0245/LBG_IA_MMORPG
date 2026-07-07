#!/usr/bin/env python3
"""TRE léger : alias STF majuscules (USERNAME…) pour login FR, sans toucher ui_loginscreen.inc."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "client_patch"))

from build_aurora_login_ui_fix import _stf_with_upper_aliases  # noqa: E402
from merge_fr_tre import extract_file_from_tre  # noqa: E402
from tre_writer import build_tre  # noqa: E402

DEFAULT_CLIENT = Path("/mnt/j/swgemu/clients/prime-lbg")
OUT_NAME = "patch_prime_fr_stf_00.tre"


def build_fr_stf_patch(*, client_dir: Path, out_tre: Path) -> None:
    files: dict[str, bytes] = {}

    en_raw = extract_file_from_tre(client_dir / "patch_fr_00.tre", "string/en/ui.stf")
    if not en_raw:
        raise SystemExit("patch_fr_00.tre : string/en/ui.stf introuvable")
    files["string/en/ui.stf"] = _stf_with_upper_aliases(en_raw)

    fr_raw = extract_file_from_tre(client_dir / "LBG_French.tre", "string/fr/ui.stf")
    if not fr_raw:
        raise SystemExit("LBG_French.tre : string/fr/ui.stf introuvable")
    files["string/fr/ui.stf"] = _stf_with_upper_aliases(fr_raw)

    build_tre(out_tre, files, compress=True)
    print(f"OK: {out_tre} ({len(files)} entrées)")
    for path in sorted(files):
        print(f"  · {path}")


def main() -> int:
    p = argparse.ArgumentParser(description="Alias STF login FR/EN (prio > LBG_French)")
    p.add_argument("--client-dir", type=Path, default=DEFAULT_CLIENT)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()
    out = args.out or (args.client_dir / OUT_NAME)
    build_fr_stf_patch(client_dir=args.client_dir, out_tre=out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
