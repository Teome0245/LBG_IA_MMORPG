"""Tests chargement catalogue v2 (C.2)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import core3_ia_sidecar as sidecar  # noqa: E402


def test_catalog_over_legacy(tmp_path, monkeypatch):
    cat = tmp_path / "catalog.json"
    cat.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "zone": "tatooine",
                "profiles": {
                    "profile:test": {
                        "lbg_npc_id": "npc:test",
                        "role": "test",
                        "actions_allowed": ["npc_say"],
                        "llm": {"system_hint": "hint test", "max_tokens": 80},
                    }
                },
                "entries": [
                    {
                        "pilot_id": "npc:core3_test",
                        "profile_id": "profile:test",
                        "display_name": "[IA] Test",
                        "status": "active",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CORE3_IA_NPC_CATALOG_JSON", str(cat))
    sidecar.invalidate_pilot_registry_cache()
    reg = sidecar.load_pilot_registry()
    assert reg["registry_source"] == "catalog"
    assert len(reg["pilots"]) == 1
    row = sidecar.resolve_pilot_row("npc:test")
    assert row is not None
    prof = sidecar.resolve_profile_for_row(row)
    assert prof.get("llm", {}).get("system_hint") == "hint test"


if __name__ == "__main__":
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        cat = Path(td) / "catalog.json"
        cat.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "zone": "tatooine",
                    "profiles": {
                        "profile:test": {
                            "lbg_npc_id": "npc:test",
                            "llm": {"system_hint": "hint test"},
                        }
                    },
                    "entries": [
                        {
                            "pilot_id": "npc:core3_test",
                            "profile_id": "profile:test",
                            "display_name": "[IA] Test",
                            "status": "active",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        os.environ["CORE3_IA_NPC_CATALOG_JSON"] = str(cat)
        sidecar.invalidate_pilot_registry_cache()
        reg = sidecar.load_pilot_registry()
        assert reg["registry_source"] == "catalog"
        print("OK catalog load", reg["registry_source"])
