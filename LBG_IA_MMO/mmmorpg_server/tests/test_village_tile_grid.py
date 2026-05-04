from __future__ import annotations

import logging
from pathlib import Path

import pytest

from mmmorpg_server.game_state import GameState
from mmmorpg_server.world_core import village_tile_grid as vtg_mod
from mmmorpg_server.world_core.village_tile_grid import VillageTileGrid, try_load_village_tile_grid


def _grid_file() -> Path:
    # LBG_IA_MMO/mmmorpg_server/tests/ -> parents[2] = LBG_IA_MMO
    return Path(__file__).resolve().parents[2] / "mmo_server" / "world" / "seed_data" / "pixie_seat.grid.json"


def test_add_player_spiral_when_grid_center_blocked() -> None:
    rows = (
        ".....",
        ".....",
        "..T..",
        ".....",
        ".....",
    )
    g = VillageTileGrid(
        tile_m=2.0,
        w=5,
        h=5,
        origin_x=-5.0,
        origin_z=-5.0,
        rows=rows,
        source_path=None,
    )
    gs = GameState()
    gs._village_tile_grid = g
    p = gs.add_player("Spirale")
    assert p.x == -2.0 and p.y == 0.0 and p.z == -2.0


def test_first_walkable_spawn_spiral_when_origin_tile_blocked() -> None:
    rows = (
        ".....",
        ".....",
        "..T..",
        ".....",
        ".....",
    )
    g = VillageTileGrid(
        tile_m=2.0,
        w=5,
        h=5,
        origin_x=-5.0,
        origin_z=-5.0,
        rows=rows,
        source_path=None,
    )
    assert g.is_walkable_world_m(0.0, 0.0) is False
    sp = g.first_walkable_spawn_world_m()
    assert sp is not None
    wx, wz = sp
    assert g.is_walkable_world_m(wx, wz) is True
    # Spirale : première tuile franchissable du ring r=1 autour du T sous (0,0) → coin (1,1)
    assert wx == -2.0 and wz == -2.0


def test_load_pixie_grid_direct() -> None:
    p = _grid_file()
    if not p.exists():
        pytest.skip("seed pixie_seat.grid.json absent (monorepo partiel)")
    g = VillageTileGrid.load(p)
    assert g.w > 10
    assert g.is_walkable_world_m(0.0, 0.0) is True


def test_nearest_walkable_snaps_from_tree_tile() -> None:
    g = VillageTileGrid(
        tile_m=2.0,
        w=5,
        h=5,
        origin_x=-5.0,
        origin_z=-5.0,
        rows=(
            ".....",
            ".....",
            "..T..",
            ".....",
            ".....",
        ),
        source_path=None,
    )
    sp = g.nearest_walkable_tile_center_world_m(0.0, 0.0)
    assert sp is not None
    assert sp == g.first_walkable_spawn_world_m()


def test_game_state_loads_tile_grid_from_ci_fixture(minimal_village_grid_env: None) -> None:
    gs = GameState()
    assert gs._village_tile_grid is not None
    assert gs._village_tile_grid.w == 5 and gs._village_tile_grid.h == 5


def test_player_spawn_emits_json_log(caplog: pytest.LogCaptureFixture, minimal_village_grid_env: None) -> None:
    caplog.set_level(logging.INFO)
    gs = GameState()
    gs.add_player("LogTesteur")
    assert any("player_spawn" in rec.message for rec in caplog.records)


def test_tick_blocks_move_outside_tile_grid(minimal_village_grid_env: None) -> None:
    """Hors de la bbox tuilée : non franchissable → position inchangée sur XZ."""
    gs = GameState()
    assert gs._village_tile_grid is not None
    g = gs._village_tile_grid
    p = gs.add_player("Testeur")
    p.x, p.y, p.z = 0.0, 0.0, 0.0
    x0, z0 = p.x, p.z
    # Vitesse vers l'extérieur de la carte (certainement non walkable)
    p.vx = 1e6
    p.vz = 0.0
    p.vy = 0.0
    gs.tick(0.05)
    assert abs(p.x - x0) < 1.0 and abs(p.z - z0) < 1.0


def test_npc_tick_blocked_by_tile_grid_like_player(minimal_village_grid_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(GameState, "_npc_step", lambda self, npc, dt: None)
    gs = GameState()
    g = gs._village_tile_grid
    assert g is not None
    npc = gs.get_npc("npc:merchant")
    assert npc is not None
    start_x: float | None = None
    start_z: float | None = None
    tree_gx: int | None = None
    for gz in range(g.h):
        for gx in range(1, g.w):
            if g.rows[gz][gx] != "T":
                continue
            if g.rows[gz][gx - 1] not in (".", "R"):
                continue
            tree_gx = gx
            start_x = g.origin_x + (gx - 1 + 0.5) * g.tile_m
            start_z = g.origin_z + (gz + 0.5) * g.tile_m
            break
        if start_x is not None:
            break
    assert start_x is not None and tree_gx is not None
    npc.x, npc.y, npc.z = start_x, 0.0, start_z
    npc.busy_timer = 0.0
    dt = 0.05
    tree_left_x = g.origin_x + tree_gx * g.tile_m + 0.05
    npc.vx = (tree_left_x - start_x) / dt
    npc.vz = 0.0
    npc.vy = 0.0
    x0, z0 = npc.x, npc.z
    assert not g.is_walkable_world_m(x0 + npc.vx * dt, z0)
    gs.tick(dt)
    assert npc.x == x0 and npc.z == z0


def test_tick_blocks_move_into_tree_tile(minimal_village_grid_env: None) -> None:
    gs = GameState()
    g = gs._village_tile_grid
    assert g is not None
    start_x: float | None = None
    start_z: float | None = None
    tree_gx: int | None = None
    for gz in range(g.h):
        for gx in range(1, g.w):
            if g.rows[gz][gx] != "T":
                continue
            if g.rows[gz][gx - 1] not in (".", "R"):
                continue
            tree_gx = gx
            start_x = g.origin_x + (gx - 1 + 0.5) * g.tile_m
            start_z = g.origin_z + (gz + 0.5) * g.tile_m
            break
        if start_x is not None:
            break
    assert start_x is not None and start_z is not None and tree_gx is not None

    p = gs.add_player("Testeur2")
    p.x, p.y, p.z = start_x, 0.0, start_z
    assert g.is_walkable_world_m(p.x, p.z)
    dt = 0.05
    # Un pas suffisant pour que nx tombe dans la tuile T à l'est (vitesse uniquement sur X)
    tree_left_x = g.origin_x + tree_gx * g.tile_m + 0.05
    p.vx = (tree_left_x - start_x) / dt
    p.vz = 0.0
    p.vy = 0.0
    x0, z0 = p.x, p.z
    assert not g.is_walkable_world_m(x0 + p.vx * dt, z0)
    gs.tick(dt)
    assert p.x == x0 and p.z == z0


def test_try_load_returns_none_for_missing_path(monkeypatch) -> None:
    def _only_bad() -> list[Path]:
        return [Path("/nope/absent.grid.json")]

    monkeypatch.setattr(vtg_mod, "_candidate_paths", _only_bad)
    assert try_load_village_tile_grid() is None
