"""Thread autonome : fait « jouer » Lia via agent.core3 (sidecar /v1/think)."""

from __future__ import annotations

import json
import threading
import time

from lbg_agents.lia_autonomy import lia_autonomy_enabled, lia_autonomy_interval_s, lia_autonomy_tick

_lock = threading.Lock()
_stop = threading.Event()
_thread: threading.Thread | None = None
_last: dict[str, object] = {}


def get_status() -> dict[str, object]:
    with _lock:
        return dict(_last)


def _loop() -> None:
    time.sleep(2.0)
    while not _stop.is_set():
        if lia_autonomy_enabled():
            try:
                out = lia_autonomy_tick()
            except Exception as exc:
                out = {"ok": False, "outcome": "tick_exception", "error": str(exc)}
            with _lock:
                _last.clear()
                _last.update(out)
                _last["ts"] = time.time()
            if out.get("outcome") not in ("skipped_offline", "connect_failed"):
                print(
                    json.dumps(
                        {"event": "orchestrator.lia_autonomy.tick", **{k: out.get(k) for k in (
                            "ok", "outcome", "mode", "action", "player", "prompt", "incarnation", "connect"
                        )}},
                        ensure_ascii=False,
                    )
                )
        _stop.wait(timeout=float(lia_autonomy_interval_s()))


def ensure_started() -> None:
    global _thread
    if _thread is not None:
        return
    with _lock:
        _last["enabled"] = lia_autonomy_enabled()
        _last["interval_s"] = lia_autonomy_interval_s()
    _thread = threading.Thread(target=_loop, name="lbg-lia-autonomy", daemon=True)
    _thread.start()


def stop() -> None:
    _stop.set()
