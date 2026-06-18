"""Registre data-driven des joueurs IA Core3 (Phase G)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Core3IaPlayer:
    id: str
    actor_id: str
    account: str
    character: str
    firstname: str
    role: str
    profession_current: str
    profession_dynamic: bool
    profession_secondary: str
    progression_goals: tuple[str, ...]
    behavior_profile_id: str
    session_json: str
    env_file: str
    systemd_unit: str
    capabilities: tuple[str, ...]
    enabled: bool
    autonomy_enabled: bool


def registry_path() -> Path:
    raw = os.environ.get("LBG_CORE3_IA_PLAYERS_JSON", "").strip()
    if raw:
        return Path(raw)
    for candidate in (
        Path("/opt/LBG_IA_MMO/content/core3/core3_ia_players.json"),
        Path(__file__).resolve().parents[3] / "content" / "core3" / "core3_ia_players.json",
    ):
        if candidate.is_file():
            return candidate
    return Path("content/core3/core3_ia_players.json")


def _row_to_player(row: dict[str, Any]) -> Core3IaPlayer:
    return Core3IaPlayer(
        id=str(row["id"]).strip(),
        actor_id=str(row["actor_id"]).strip(),
        account=str(row["account"]).strip(),
        character=str(row["character"]).strip(),
        firstname=str(row["firstname"]).strip(),
        role=str(row.get("role") or "").strip(),
        profession_current=str(row.get("profession_current") or "").strip(),
        profession_dynamic=bool(row.get("profession_dynamic", True)),
        profession_secondary=str(row.get("profession_secondary") or "").strip(),
        progression_goals=tuple(str(x).strip() for x in row.get("progression_goals", []) if str(x).strip()),
        behavior_profile_id=str(row.get("behavior_profile_id") or "").strip(),
        session_json=str(row["session_json"]).strip(),
        env_file=str(row["env_file"]).strip(),
        systemd_unit=str(row["systemd_unit"]).strip(),
        capabilities=tuple(str(x).strip() for x in row.get("capabilities", []) if str(x).strip()),
        enabled=bool(row.get("enabled", True)),
        autonomy_enabled=bool(row.get("autonomy_enabled", True)),
    )


def load_players_registry() -> dict[str, Any]:
    path = registry_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("players"), list):
        raise ValueError(f"registre joueurs IA invalide: {path}")
    return data


def list_ai_players(*, enabled_only: bool = False) -> list[Core3IaPlayer]:
    data = load_players_registry()
    players = [_row_to_player(row) for row in data["players"] if isinstance(row, dict)]
    if enabled_only:
        return [p for p in players if p.enabled]
    return players


def list_autonomy_players() -> list[Core3IaPlayer]:
    return [p for p in list_ai_players(enabled_only=True) if p.autonomy_enabled]


def player_behavior_profile_id(player: Core3IaPlayer) -> str:
    from lbg_agents.core3_behavior_profiles import resolve_player_behavior_profile_id

    return resolve_player_behavior_profile_id(
        behavior_profile_id=player.behavior_profile_id,
        profession_current=player.profession_current,
        role=player.role,
    )


def get_ai_player(player_id_or_firstname: str) -> Core3IaPlayer:
    wanted = player_id_or_firstname.strip().lower()
    for player in list_ai_players():
        if player.id.lower() == wanted or player.firstname.lower() == wanted:
            return player
    raise KeyError(f"joueur IA inconnu: {player_id_or_firstname}")


def player_prompt_context(player: Core3IaPlayer) -> str:
    dynamic = "dynamique" if player.profession_dynamic else "fixe"
    caps = ", ".join(player.capabilities)
    secondary = (
        f", second métier cible={player.profession_secondary}"
        if player.profession_secondary
        else ""
    )
    goals = (
        f" Objectifs progression: {', '.join(player.progression_goals)}."
        if player.progression_goals
        else ""
    )
    return (
        f"Joueur IA {player.firstname} ({player.character}), rôle={player.role}, "
        f"métier courant={player.profession_current} ({dynamic}){secondary}, capabilities={caps}."
        f"{goals}"
    )
