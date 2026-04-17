"""Paramètres serveur (env) — priorité backend, sans dépendre du client Godot."""

from __future__ import annotations

import os

HOST: str = os.environ.get("MMMORPG_HOST", "0.0.0.0")
PORT: int = int(os.environ.get("MMMORPG_PORT", "7733"))

TICK_RATE_HZ: float = float(os.environ.get("MMMORPG_TICK_RATE_HZ", "20"))

# Rejet des frames entrantes trop grosses (DoS léger).
MAX_WS_INBOUND_BYTES: int = int(os.environ.get("MMMORPG_MAX_WS_INBOUND_BYTES", str(64 * 1024)))

# Anti-spam sur `move` (secondes entre deux commandes appliquées).
MOVE_MIN_INTERVAL_S: float = float(os.environ.get("MMMORPG_MOVE_MIN_INTERVAL_S", "0.02"))
