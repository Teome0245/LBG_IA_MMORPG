#!/usr/bin/env python3
"""Audit rapide des chemins logiques dans un TRE SWG (via strings — fiable sur EERT/TREE)."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Chemins SWG typiques dans les archives
PATH_RE = re.compile(
    r"(?:appearance|object|texture|shader|string|datatables|terrain|"
    r"clienteffect|effect|pixel_program|vertex_program)/[^\s\x00]{4,120}",
    re.IGNORECASE,
)


def extract_paths(tre_path: Path) -> list[str]:
    proc = subprocess.run(
        ["strings", "-n", "8", str(tre_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise OSError(proc.stderr or f"strings failed on {tre_path}")
    found: set[str] = set()
    for line in proc.stdout.splitlines():
        for m in PATH_RE.finditer(line):
            found.add(m.group(0).replace("\\", "/").lower())
    return sorted(found)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit chemins dans des TRE SWG (AURORA / Prime)")
    parser.add_argument("tre", nargs="+", type=Path)
    parser.add_argument("--filter", default="", help="Filtre sous-chaîne")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    for tre in args.tre:
        if not tre.is_file():
            print(f"# absent: {tre}", file=sys.stderr)
            continue
        try:
            paths = extract_paths(tre)
        except OSError as e:
            print(f"# ERREUR {tre}: {e}", file=sys.stderr)
            continue
        if args.filter:
            f = args.filter.lower()
            paths = [p for p in paths if f in p]
        if args.limit:
            paths = paths[: args.limit]
        print(f"\n# {tre.name} — {len(paths)} chemins")
        for p in paths:
            print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
