"""Tests feed ZB-1 zone_bridge_live.json."""

from __future__ import annotations

import json
import time
from pathlib import Path

from services.lbg_gateway.zone_bridge_feed import (
    merge_snapshot_entities,
    probe_zone_bridge_feed,
    read_live_zone_state,
)


def test_read_live_zone_state_fresh(tmp_path: Path, monkeypatch) -> None:
    p = tmp_path / "zone_bridge_live.json"
    payload = {
        "type": "zone_state",
        "proto": "lbg-ws/2",
        "zone": "tatooine",
        "tick": 42,
        "entities": [],
    }
    p.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("LBG_GATEWAY_ZONE_BRIDGE_JSON", str(p))
    monkeypatch.setenv("LBG_GATEWAY_ZONE_BRIDGE_LIVE", "1")
    live = read_live_zone_state()
    assert live is not None
    assert live["tick"] == 42
    assert live["zone"] == "tatooine"


def test_read_live_zone_state_stale(tmp_path: Path, monkeypatch) -> None:
    p = tmp_path / "zone_bridge_live.json"
    p.write_text('{"type":"zone_state","proto":"lbg-ws/2","zone":"x","tick":1,"entities":[]}', encoding="utf-8")
    old = time.time() - 60
    import os

    os.utime(p, (old, old))
    monkeypatch.setenv("LBG_GATEWAY_ZONE_BRIDGE_JSON", str(p))
    monkeypatch.setenv("LBG_GATEWAY_ZONE_BRIDGE_MAX_AGE_S", "2")
    assert read_live_zone_state() is None


def test_merge_snapshot_entities_fallback() -> None:
    live = {"entities": []}
    snap = [{"id": "npc:Lia", "kind": "npc", "pos": [0, 0, 0]}]
    merged = merge_snapshot_entities(live, snap)
    assert merged == snap


def test_probe_zone_bridge_feed_missing(tmp_path: Path, monkeypatch) -> None:
    missing = tmp_path / "missing.json"
    monkeypatch.setenv("LBG_GATEWAY_ZONE_BRIDGE_JSON", str(missing))
    out = probe_zone_bridge_feed(path=missing)
    assert out["track"] == "zb1_live_feed"
    assert out["ok"] is False
