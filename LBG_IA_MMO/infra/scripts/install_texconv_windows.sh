#!/usr/bin/env bash
# Installe texconv.exe dans C:\Agent_IA\tools (conversion DDS batch).
set -euo pipefail
DEST="/mnt/c/Agent_IA/tools"
mkdir -p "$DEST"
URL="https://github.com/microsoft/DirectXTex/releases/download/jun2024/texconv.exe"
echo "Download: $URL"
curl -fsSL -o "${DEST}/texconv.exe" "$URL"
ls -la "${DEST}/texconv.exe"
echo "OK: ${DEST}/texconv.exe"
