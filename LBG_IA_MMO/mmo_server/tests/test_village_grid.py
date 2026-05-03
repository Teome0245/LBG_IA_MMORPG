from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from http_app import app
from world.village_grid import VillageCollisionGrid


def _grid_path() -> Path:
    return Path(__file__).resolve().parents[1] / "world" / "seed_data" / "pixie_seat.grid.json"


def test_load_pixie_seat_grid() -> None:
    p = _grid_path()
    assert p.exists()
    g = VillageCollisionGrid.load(p)
    assert g.w == 143 and g.h == 143
    assert g.tile_m == 2.0
    ch, gx, gz = g.terrain_at_world_m(0.0, 0.0)
    assert gx is not None and gz is not None
    assert ch is not None and len(ch) == 1


def test_world_collision_meta_endpoint() -> None:
    with TestClient(app) as client:
        r = client.get("/v1/world/collision")
        assert r.status_code == 200
        d = r.json()
        assert d.get("loaded") is True
        assert d["grid"]["w"] == 143


def test_world_collision_grid_endpoint() -> None:
    with TestClient(app) as client:
        r = client.get("/v1/world/collision-grid")
        assert r.status_code == 200
        d = r.json()
        assert d.get("loaded") is True
        assert d.get("kind") == "watabou_grid_v1"
        assert d["grid"]["w"] == 143
        assert isinstance(d["grid"].get("rows"), list)
        assert len(d["grid"]["rows"]) == 143


def test_collision_probe_without_internal_token() -> None:
    os.environ.pop("LBG_MMO_INTERNAL_TOKEN", None)
    with TestClient(app) as client:
        r = client.get("/internal/v1/world/collision-probe", params={"x": 0.0, "z": 0.0})
        assert r.status_code == 200
        body = r.json()
        assert body.get("loaded") is True
        assert "walkable" in body
        assert body["tile"]["gx"] is not None


def test_collision_probe_requires_token_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_MMO_INTERNAL_TOKEN", "tok")
    with TestClient(app) as client:
        r1 = client.get("/internal/v1/world/collision-probe", params={"x": 0.0, "z": 0.0})
        assert r1.status_code == 401
        r2 = client.get(
            "/internal/v1/world/collision-probe",
            params={"x": 0.0, "z": 0.0},
            headers={"X-LBG-Service-Token": "tok"},
        )
        assert r2.status_code == 200


def test_collision_meta_no_grid_when_path_missing(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("LBG_MMO_VILLAGE_GRID_JSON", str(tmp_path / "absent.grid.json"))
    with TestClient(app) as client:
        r = client.get("/v1/world/collision")
        assert r.status_code == 200
        assert r.json() == {"loaded": False}
