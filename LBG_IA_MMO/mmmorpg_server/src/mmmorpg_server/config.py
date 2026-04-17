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

# Pont "jeu → IA" (optionnel) : si défini, le serveur WS peut appeler le backend monorepo
# pour obtenir une réplique PNJ (via POST /v1/pilot/internal/route par défaut) lorsqu'un client envoie `hello`
# avec des champs optionnels (ex. `world_npc_id`, `npc_name`, `text`).
IA_BACKEND_URL: str = os.environ.get("MMMORPG_IA_BACKEND_URL", "").strip().rstrip("/")
IA_BACKEND_PATH: str = os.environ.get("MMMORPG_IA_BACKEND_PATH", "/v1/pilot/internal/route").strip() or "/v1/pilot/internal/route"
IA_BACKEND_TOKEN: str = os.environ.get("MMMORPG_IA_BACKEND_TOKEN", "").strip()

# Timeout (secondes) pour l'appel backend du pont jeu → IA.
# En LAN, le connect est rapide, mais la génération LLM peut dépasser quelques secondes.
IA_TIMEOUT_S: float = float(os.environ.get("MMMORPG_IA_TIMEOUT_S", "30"))

# Fiabilisation : si activé, le serveur envoie une réplique placeholder immédiatement
# (sur le prochain world_tick) dès qu'un hello contient `world_npc_id` + `text`,
# puis renverra une seconde réplique quand l'IA répond (si elle répond).
IA_PLACEHOLDER_ENABLED: bool = os.environ.get("MMMORPG_IA_PLACEHOLDER_ENABLED", "1").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
IA_PLACEHOLDER_REPLY: str = os.environ.get(
    "MMMORPG_IA_PLACEHOLDER_REPLY",
    "… (Le PNJ vous regarde, comme s’il réfléchissait.)",
).strip()

# --- HTTP interne (lecture seule) : snapshot Lyra depuis le serveur WS ---
# Désactivé par défaut (port 0) : utile pour le pont "jeu → IA" en lecture seule
# (voir docs/fusion_pont_jeu_ia.md). Exposer uniquement en LAN / réseau privé.
INTERNAL_HTTP_HOST: str = os.environ.get("MMMORPG_INTERNAL_HTTP_HOST", "127.0.0.1").strip() or "127.0.0.1"
INTERNAL_HTTP_PORT: int = int(os.environ.get("MMMORPG_INTERNAL_HTTP_PORT", "0"))
INTERNAL_HTTP_TOKEN: str = os.environ.get("MMMORPG_INTERNAL_HTTP_TOKEN", "").strip()

# Rate-limit (LAN) sur l'HTTP interne : protège des boucles / spam accidentels.
# 0 => désactivé. S'applique par IP remote (best-effort).
INTERNAL_HTTP_RL_RPS: float = float(os.environ.get("MMMORPG_INTERNAL_HTTP_RL_RPS", "0").strip() or "0")
INTERNAL_HTTP_RL_BURST: int = int(os.environ.get("MMMORPG_INTERNAL_HTTP_RL_BURST", "0").strip() or "0")

# --- Persistance (phase 2) : commits / flags PNJ ---
# Désactivable (utile en CI ou tests).
PERSIST_DISABLE: bool = os.environ.get("MMMORPG_DISABLE_PERSIST", "0").strip().lower() in ("1", "true", "yes", "on")
STATE_PATH: str = os.environ.get("MMMORPG_STATE_PATH", "").strip()
