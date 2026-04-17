"""
Shim package pour le monorepo.

Dans ce dépôt, le vrai package Python vit dans `mmmorpg_server/src/mmmorpg_server/` (layout "src").
Quand `LBG_IA_MMO/` est sur le PYTHONPATH, le dossier `mmmorpg_server/` peut être résolu avant le
package "src". Ce fichier force la résolution des sous-modules (`mmmorpg_server.config`, etc.)
vers le bon emplacement.
"""

from __future__ import annotations

from pathlib import Path
from pkgutil import extend_path

# Namespace/package path extensible.
__path__ = extend_path(__path__, __name__)  # type: ignore[name-defined]

_SRC_PKG = Path(__file__).resolve().parent / "src" / "mmmorpg_server"
if _SRC_PKG.is_dir():
    __path__.append(str(_SRC_PKG))  # type: ignore[attr-defined]

