from __future__ import annotations

import sys
from pathlib import Path


def _prepend(path: Path) -> None:
    p = str(path)
    if p not in sys.path:
        sys.path.insert(0, p)


# Prioriser le package "src layout" : évite que le dossier `mmmorpg_server/` (namespace)
# ne masque `mmmorpg_server/src/mmmorpg_server` quand on lance plusieurs suites ensemble.
ROOT = Path(__file__).resolve().parents[1]
_prepend(ROOT / "src")

