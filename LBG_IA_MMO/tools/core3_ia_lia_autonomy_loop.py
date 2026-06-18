#!/usr/bin/env python3
"""Boucle autonome Lia — appelle le sidecar ou l'orchestrateur (voir LBG_CORE3_LIA_AUTONOMY_MODE)."""

from __future__ import annotations

import os
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_AGENTS_SRC = os.path.join(_REPO, "agents", "src")
if _AGENTS_SRC not in sys.path:
    sys.path.insert(0, _AGENTS_SRC)

from lbg_agents.lia_autonomy import (  # noqa: E402
    lia_autonomy_enabled,
    lia_autonomy_interval_s,
    run_lia_autonomy_loop,
)


def main() -> int:
    if not lia_autonomy_enabled():
        print("LBG_CORE3_LIA_AUTONOMY_ENABLED=0 — rien à faire.", file=sys.stderr)
        return 0
    interval = lia_autonomy_interval_s()
    print(f"lia_autonomy: interval={interval}s mode={os.environ.get('LBG_CORE3_LIA_AUTONOMY_MODE', 'invoke')}")
    run_lia_autonomy_loop()


if __name__ == "__main__":
    raise SystemExit(main())
