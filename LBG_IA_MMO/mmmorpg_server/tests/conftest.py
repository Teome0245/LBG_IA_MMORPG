"""Fixtures pytest : grille village minimale (CI sans `mmo_server/.../pixie_seat.grid.json`)."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_MINIMAL_VILLAGE_GRID = Path(__file__).resolve().parent / "fixtures" / "minimal_village.grid.json"


@pytest.fixture
def minimal_village_grid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    assert FIXTURE_MINIMAL_VILLAGE_GRID.is_file(), f"fichier manquant : {FIXTURE_MINIMAL_VILLAGE_GRID}"
    monkeypatch.setenv("MMMORPG_VILLAGE_GRID_JSON", str(FIXTURE_MINIMAL_VILLAGE_GRID))
