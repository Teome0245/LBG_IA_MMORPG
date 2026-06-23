"""Heure locale LBG (défaut Europe/Paris) — timestamps et fenêtres ops."""

from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

_DEFAULT_TZ = "Europe/Paris"


def local_timezone_name() -> str:
    raw = os.environ.get("LBG_LOCAL_TIMEZONE", _DEFAULT_TZ).strip()
    return raw or _DEFAULT_TZ


def local_tz() -> ZoneInfo:
    return ZoneInfo(local_timezone_name())


def local_now() -> datetime:
    return datetime.now(local_tz())


def local_now_iso() -> str:
    return local_now().isoformat(timespec="seconds")


def local_now_compact() -> str:
    return local_now().strftime("%Y%m%dT%H%M%S")
