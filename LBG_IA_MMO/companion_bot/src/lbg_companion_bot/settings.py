from __future__ import annotations

import os
from dataclasses import dataclass


def _truthy(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _csv(raw: str) -> list[str]:
    return [x.strip() for x in (raw or "").split(",") if x.strip()]


@dataclass(frozen=True)
class Settings:
    title: str = "LBG Companion Bot"
    version: str = "0.1.0"

    # Persistance
    db_path: str = "./data/companion.sqlite3"

    # Réseau
    cors_origins: list[str] = None  # type: ignore[assignment]

    # Debug
    debug_default: bool = False

    # LLM OpenAI-compatible (optionnel)
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout_s: float = 60.0
    llm_temperature: float = 0.4
    llm_max_tokens: int = 512
    llm_disabled: bool = False

    # Conversation
    max_history_messages: int = 18

    # Autonomie (tick)
    autonomous_tick_enabled: bool = True
    autonomous_loop_interval_s: float = 10.0
    autonomous_loop_max_sessions: int = 20
    autonomous_min_nudge_interval_s: float = 60.0
    autonomous_window_s: float = 3600.0
    autonomous_max_nudges_per_window: int = 5

    @classmethod
    def from_env(cls) -> "Settings":
        cors = _csv(os.environ.get("LBG_COMPANION_CORS_ORIGINS", "").strip())

        def _f(name: str, default: float) -> float:
            raw = os.environ.get(name, str(default)).strip()
            try:
                return float(raw)
            except ValueError:
                return float(default)

        def _i(name: str, default: int) -> int:
            raw = os.environ.get(name, str(default)).strip()
            try:
                return int(raw)
            except ValueError:
                return int(default)

        return cls(
            db_path=os.environ.get("LBG_COMPANION_DB_PATH", cls.db_path).strip() or cls.db_path,
            cors_origins=cors,
            debug_default=_truthy(os.environ.get("LBG_COMPANION_DEBUG_DEFAULT", "0")),
            llm_base_url=os.environ.get("LBG_COMPANION_LLM_BASE_URL", "").strip(),
            llm_api_key=os.environ.get("LBG_COMPANION_LLM_API_KEY", "").strip(),
            llm_model=os.environ.get("LBG_COMPANION_LLM_MODEL", "").strip(),
            llm_timeout_s=max(5.0, _f("LBG_COMPANION_LLM_TIMEOUT", 60.0)),
            llm_temperature=max(0.0, min(_f("LBG_COMPANION_LLM_TEMPERATURE", 0.4), 2.0)),
            llm_max_tokens=max(16, min(_i("LBG_COMPANION_LLM_MAX_TOKENS", 512), 4096)),
            llm_disabled=_truthy(os.environ.get("LBG_COMPANION_LLM_DISABLED", "0")),
            max_history_messages=max(2, min(_i("LBG_COMPANION_MAX_HISTORY", 18), 64)),
            autonomous_tick_enabled=_truthy(os.environ.get("LBG_COMPANION_AUTONOMOUS_TICK_ENABLED", "1")),
            autonomous_loop_interval_s=max(1.0, _f("LBG_COMPANION_AUTONOMOUS_LOOP_INTERVAL_S", 10.0)),
            autonomous_loop_max_sessions=max(1, min(_i("LBG_COMPANION_AUTONOMOUS_LOOP_MAX_SESSIONS", 20), 2000)),
            autonomous_min_nudge_interval_s=max(5.0, _f("LBG_COMPANION_AUTONOMOUS_MIN_NUDGE_INTERVAL_S", 60.0)),
            autonomous_window_s=max(60.0, _f("LBG_COMPANION_AUTONOMOUS_WINDOW_S", 3600.0)),
            autonomous_max_nudges_per_window=max(0, min(_i("LBG_COMPANION_AUTONOMOUS_MAX_NUDGES_PER_WINDOW", 5), 1000)),
        )

