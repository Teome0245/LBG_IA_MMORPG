"""
Chargement de l'état monde initial depuis un fichier seed versionné (JSON).

Même schéma que ``world.persistence`` (``schema_version``, ``now_s``, ``npcs``).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from entities.npc import Npc
from lyra_engine.gauges import GaugesState
from world.persistence import world_state_from_dict
from world.state import WorldState

logger = logging.getLogger(__name__)

_SEED_FILENAME = "world_initial.json"


def _default_seed_path() -> Path:
    return Path(__file__).resolve().parent / "seed_data" / _SEED_FILENAME


def resolve_seed_path() -> Path:
    raw = os.environ.get("LBG_MMO_SEED_PATH", "").strip()
    if raw:
        return Path(raw).expanduser()
    return _default_seed_path()


def load_initial_world_state() -> WorldState:
    """
    Charge le JSON seed ; en cas d'erreur, retombe sur un monde minimal (un PNJ).
    """
    path = resolve_seed_path()
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("seed root must be an object")
        return world_state_from_dict(data)
    except FileNotFoundError:
        logger.warning("fichier seed introuvable (%s), monde minimal", path)
    except (OSError, json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
        logger.warning("seed invalide (%s) : %s — monde minimal", path, e)
    return _fallback_minimal_world()


def _fallback_minimal_world() -> WorldState:
    return WorldState(
        now_s=0.0,
        npcs={
            "npc:smith": Npc(id="npc:smith", name="Forgeron", role="smith"),
        },
    )
