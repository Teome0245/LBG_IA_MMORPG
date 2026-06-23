"""Heure locale LBG (défaut Europe/Paris) — timestamps et fenêtres ops."""

from __future__ import annotations

import os
from datetime import datetime, timezone
try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore


_DEFAULT_TZ = "Europe/Paris"


def local_timezone_name() -> str:
    raw = os.environ.get("LBG_LOCAL_TIMEZONE", _DEFAULT_TZ).strip()
    return raw or _DEFAULT_TZ


def local_tz():  # type: ignore
    if ZoneInfo is not None:
        try:
            return ZoneInfo(local_timezone_name())
        except Exception:
            pass
    try:
        return datetime.now().astimezone().tzinfo or timezone.utc
    except Exception:
        return timezone.utc



def local_now() -> datetime:
    return datetime.now(local_tz())


def local_now_iso() -> str:
    return local_now().isoformat(timespec="seconds")


def local_now_compact() -> str:
    return local_now().strftime("%Y%m%dT%H%M%S")
