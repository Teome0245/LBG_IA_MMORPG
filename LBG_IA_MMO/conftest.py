"""
Conftest racine (monorepo).

Objectif : permettre de lancer plusieurs suites de tests en une seule commande
(backend + mmo_server + mmmorpg_server + orchestrator + agents) sans collisions
de modules ni problèmes de PYTHONPATH.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _prepend(path: Path) -> None:
    p = str(path)
    if p not in sys.path:
        sys.path.insert(0, p)


ROOT = Path(__file__).resolve().parent

# Packages "src layout"
_prepend(ROOT / "mmmorpg_server" / "src")

# Packages "flat layout" (imports de tests historiques)
_prepend(ROOT / "backend")
_prepend(ROOT / "orchestrator")
_prepend(ROOT / "agents")
_prepend(ROOT / "mmo_server")

