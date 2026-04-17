"""Isolation des fichiers d’état : chaque test écrit dans un JSON dédié (tmp)."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _mmo_state_path_per_test(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_MMO_STATE_PATH", str(tmp_path / "world_state.json"))
