#!/usr/bin/env bash
set -euo pipefail

# Convertit les scripts shell du repo en fins de ligne Unix (LF).
# Utile si un fichier a été édité sous Windows et provoque : `set: pipefail\r: invalid option name`.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

targets=(
  "${ROOT_DIR}/infra/scripts"
  "${ROOT_DIR}/infra/systemd"
)

files="$(
  python3 - <<'PY' "${ROOT_DIR}"
import sys
from pathlib import Path

root = Path(sys.argv[1])
targets = [root / "infra" / "scripts", root / "infra" / "systemd"]
exts = {".sh", ".service"}

out = []
for t in targets:
    if not t.exists():
        continue
    for p in t.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix not in exts:
            continue
        try:
            b = p.read_bytes()
        except OSError:
            continue
        if b"\r\n" in b:
            out.append(str(p))

print("\n".join(out))
PY
)"

count=0
if [[ -n "${files}" ]]; then
  while IFS= read -r f; do
    [[ -n "${f}" ]] || continue
    sed -i 's/\r$//' "${f}"
    count=$((count + 1))
  done <<< "${files}"
fi

echo "OK: fix_crlf (files_converted=${count})"

