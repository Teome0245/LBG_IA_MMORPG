"""Conversion postes cellule → coords monde (Tatooine Prime)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

# Cellules intérieur → location_id (fichiers content/core3/locations/*.json)
CELL_TO_LOCATION: dict[int, str] = {
    1082877: "mos_eisley_cantina_bar",
    1105851: "mos_eisley_cantina_bar",
    1105853: "mos_eisley_cantina_bar",
    1189634: "loc:mos_eisley_training_center",
    1189635: "loc:mos_eisley_training_center",
    1189636: "loc:mos_eisley_training_center",
    1189637: "loc:mos_eisley_training_center",
    1189638: "loc:mos_eisley_training_center",
    1189639: "loc:mos_eisley_training_center",
}


def infer_location_id(*, location_id: str = "", cell: int = 0) -> str:
    lid = str(location_id or "").strip()
    if lid:
        return lid
    return CELL_TO_LOCATION.get(int(cell or 0), "")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


@lru_cache(maxsize=2)
def load_location_anchors(locations_dir: str) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    root = Path(locations_dir)
    if not root.is_dir():
        return out
    for path in sorted(root.glob("*.json")):
        doc = _load_json(path)
        lid = str(doc.get("location_id", "")).strip()
        wa = doc.get("world_anchor")
        if lid and isinstance(wa, dict):
            anchor = {
                "x": float(wa.get("x", 0)),
                "y": float(wa.get("y", 0)),
                "z": float(wa.get("z", 0)),
            }
            out[lid] = anchor
            if lid.startswith("loc:"):
                out[lid[4:]] = anchor
            else:
                out[f"loc:{lid}"] = anchor
    return out


def is_cell_local_pos(x: float, y: float, z: float) -> bool:
    """Poste intérieur cantina / cellule (pas coords planétaires SWG)."""
    return max(abs(x), abs(y), abs(z)) < 400.0


def cell_to_world(
    local: dict[str, Any],
    anchor: dict[str, float] | None,
) -> list[float]:
    """
    Repère catalogue : post x,z plan horizontal, post y = hauteur.
    world_anchor : x, y = plan horizontal SWG, z = hauteur (cf. mos_eisley_cantina_bar).
    Sortie alignée gateway player_pos : [x, hauteur, z_horizontal].
    """
    lx = float(local.get("x", 0))
    ly = float(local.get("y", 0))
    lz = float(local.get("z", 0))
    if not anchor:
        return [lx, ly, lz]
    return [
        anchor["x"] + lx,
        anchor["z"] + ly,
        anchor["y"] + lz,
    ]


def resolve_world_pos(
    raw: dict[str, Any],
    *,
    location_id: str = "",
    anchors: dict[str, dict[str, float]],
    cell: int = 0,
) -> list[float]:
    x = float(raw.get("x", 0))
    y = float(raw.get("y", 0))
    z = float(raw.get("z", 0))
    if is_cell_local_pos(x, y, z):
        loc = infer_location_id(location_id=location_id, cell=cell)
        anc = anchors.get(loc) if loc else None
        return cell_to_world({"x": x, "y": y, "z": z}, anc)
    return [x, y, z]


def local_pos_for_interior(
    x: float,
    y: float,
    z: float,
    *,
    cell: int,
) -> list[float] | None:
    if int(cell or 0) not in CELL_TO_LOCATION:
        return None
    if not is_cell_local_pos(x, y, z):
        return None
    return [x, y, z]
