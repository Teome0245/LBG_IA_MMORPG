"""Pont optionnel gateway → ia_bridge/pending.jsonl (Phase 3 v0)."""

from __future__ import annotations

import os
from pathlib import Path

ZONE = "tatooine"


def pending_path() -> Path | None:
    raw = os.environ.get("LBG_GATEWAY_PENDING_FILE", "").strip()
    if not raw:
        return None
    return Path(raw)


def inject_enabled() -> bool:
    return os.environ.get("LBG_GATEWAY_INJECT_MOVE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def inject_player_name() -> str:
    return os.environ.get("LBG_GATEWAY_INJECT_PLAYER", "Gally").strip() or "Gally"


def append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line.rstrip("\n"))
        f.write("\n")


def inject_move_to(path: Path, player: str, x: float, y: float, z: float, note: str = "godot") -> None:
    """Format ia_bridge : action|player|zone|x|y|z|message (coords cellule / planète)."""
    line = f"move_to|{player}|{ZONE}|{x:.2f}|{y:.2f}|{z:.2f}|{note}"
    append_line(path, line)
