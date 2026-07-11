"""Routage exécution player_ia : sonde L1 vs think/tick L2."""

from __future__ import annotations

from team.models import TeamTask
from team.player_ia_probe import probe_player_ia
from team.player_ia_think import execute_player_ia_think, resolve_player_ia_mode


def execute_player_ia(task: TeamTask) -> dict[str, object]:
    if resolve_player_ia_mode(task) == "think_tick":
        return execute_player_ia_think(task)
    return probe_player_ia(task)
