"""Tests registre PNJ pilotes (Phase C)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import core3_ia_sidecar as sidecar  # noqa: E402


def test_resolve_pilot_by_lbg_id(tmp_path, monkeypatch):
    reg = tmp_path / "pilots.json"
    reg.write_text(
        json.dumps(
            {
                "pilots": [
                    {
                        "pilot_id": "npc:core3_scribe",
                        "lbg_npc_id": "npc:scribe",
                        "display_name": "Archiviste",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CORE3_IA_NPC_PILOTS_JSON", str(reg))
    sidecar._PILOT_REGISTRY_CACHE = None
    row = sidecar.resolve_pilot_row("npc:scribe")
    assert row is not None
    assert sidecar.pilot_id_from_row(row) == "npc:core3_scribe"
