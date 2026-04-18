from __future__ import annotations

import os
import threading
import time
from collections import defaultdict


_lock = threading.Lock()
_started_s = time.time()

_counters: dict[str, int] = defaultdict(int)


def enabled() -> bool:
    v = os.environ.get("LBG_METRICS_ENABLED", "0").strip().lower()
    return v in ("1", "true", "yes", "on")


def auth_token() -> str:
    return os.environ.get("LBG_METRICS_TOKEN", "").strip()


def inc(name: str, value: int = 1) -> None:
    if not enabled():
        return
    if value <= 0:
        return
    with _lock:
        _counters[name] += int(value)


def render_prometheus_text() -> str:
    with _lock:
        snap = dict(_counters)
    uptime = max(0.0, time.time() - _started_s)
    lines: list[str] = []
    lines.append("# HELP lbg_process_uptime_seconds Uptime du process (best-effort).")
    lines.append("# TYPE lbg_process_uptime_seconds gauge")
    lines.append(f"lbg_process_uptime_seconds {uptime:.3f}")
    for k in sorted(snap.keys()):
        lines.append(f"# HELP {k} Counter (auto-generated name).")
        lines.append(f"# TYPE {k} counter")
        lines.append(f"{k} {int(snap[k])}")
    lines.append("")
    return "\n".join(lines)
