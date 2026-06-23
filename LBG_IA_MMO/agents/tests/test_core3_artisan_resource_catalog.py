"""Validation catalogue ressources hub artisan (Phase 2)."""

from __future__ import annotations

import json
from pathlib import Path


def _resource_catalog_path() -> Path:
    return Path(__file__).resolve().parents[2] / "content" / "core3" / "core3_resource_samples.json"


def _dispenser_path() -> Path:
    return Path(__file__).resolve().parents[2] / "content" / "core3" / "core3_artisan_dispenser.json"


def _load_resource_catalog() -> dict:
    return json.loads(_resource_catalog_path().read_text(encoding="utf-8"))


def _all_sample_ids(doc: dict) -> list[str]:
    ids: list[str] = []
    for fam in doc.get("families") or []:
        for row in fam.get("samples") or []:
            if isinstance(row, dict) and row.get("id"):
                ids.append(str(row["id"]))
    return ids


def test_resource_catalog_schema_and_kits():
    doc = _load_resource_catalog()
    assert doc.get("schema_version") == 1
    assert int(doc.get("default_units") or 0) >= 1000
    assert int(doc.get("max_units") or 0) >= int(doc.get("default_units") or 0)
    ids = _all_sample_ids(doc)
    assert len(ids) >= 20
    assert len(ids) == len(set(ids))
    kits = doc.get("kits") or []
    assert len(kits) >= 2
    for kit in kits:
        for sid in kit.get("sample_ids") or []:
            assert sid in ids, f"kit {kit.get('id')} references unknown sample {sid}"


def test_artisan_hub_has_bazaar_terminal():
    doc = json.loads(_dispenser_path().read_text(encoding="utf-8"))
    hub = doc.get("hub") or {}
    bz = hub.get("bazaar_terminal") or {}
    assert "bazaar" in str(bz.get("template", ""))
