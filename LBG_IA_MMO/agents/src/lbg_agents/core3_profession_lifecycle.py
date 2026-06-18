"""Cycles metier longs par joueur IA (vrais joueurs, pas ancres PNJ)."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lbg_agents.core3_players import Core3IaPlayer

LIFECYCLE_PHASES = (
    "learning",
    "mastery_practice",
    "secondary_learning",
    "decay",
    "transition",
)


@dataclass(frozen=True)
class ProfessionLifecycleView:
    player_id: str
    primary: str
    secondary: str
    phase: str
    focus_profession: str
    primary_mastery_pct: float
    secondary_mastery_pct: float
    cycle_index: int
    forgotten: tuple[str, ...]
    prompt_block: str


def config_path() -> Path:
    raw = os.environ.get("LBG_CORE3_PROFESSION_LIFECYCLE_JSON", "").strip()
    if raw:
        return Path(raw)
    for candidate in (
        Path("/opt/LBG_IA_MMO/content/core3/core3_profession_lifecycle.json"),
        Path(__file__).resolve().parents[3] / "content" / "core3" / "core3_profession_lifecycle.json",
    ):
        if candidate.is_file():
            return candidate
    return Path("content/core3/core3_profession_lifecycle.json")


def state_path() -> Path:
    raw = os.environ.get("LBG_CORE3_PLAYER_PROFESSION_STATE_JSON", "").strip()
    if raw:
        return Path(raw)
    for candidate in (
        Path("/opt/lbg-new-mmo-clean/MMOCoreORB/bin/ia_bridge/player_profession_state.json"),
        Path(__file__).resolve().parents[3] / "content" / "core3" / "ia_bridge" / "player_profession_state.json",
    ):
        parent = candidate.parent
        if parent.is_dir() or not candidate.is_absolute():
            return candidate
    return Path("content/core3/ia_bridge/player_profession_state.json")


def load_lifecycle_config() -> dict[str, Any]:
    path = config_path()
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def load_state_registry() -> dict[str, Any]:
    path = state_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    players = data.get("players") if isinstance(data, dict) else None
    return players if isinstance(players, dict) else {}


def save_state_registry(players: dict[str, Any]) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"version": 1, "updated_at": int(time.time()), "players": players}
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _default_row(player: Core3IaPlayer) -> dict[str, Any]:
    now = int(time.time())
    return {
        "primary": player.profession_current or "entertainer",
        "secondary": player.profession_secondary or "artisan",
        "phase": "learning",
        "primary_mastery_pct": 0.0,
        "secondary_mastery_pct": 0.0,
        "phase_started_at": now,
        "cycle_index": 0,
        "forgotten": [],
        "last_tick_at": now,
    }


def _phase_hours(cfg: dict[str, Any], phase: str) -> float:
    hours = cfg.get("real_hours") if isinstance(cfg.get("real_hours"), dict) else {}
    return float(hours.get(phase) or 48)


def _threshold(cfg: dict[str, Any]) -> float:
    return float(cfg.get("mastery_threshold_pct") or 90)


def _advance_phase(row: dict[str, Any], cfg: dict[str, Any], now: int) -> dict[str, Any]:
    phase = str(row.get("phase") or "learning")
    started = int(row.get("phase_started_at") or now)
    elapsed_h = max(0.0, (now - started) / 3600.0)
    primary = str(row.get("primary") or "")
    secondary = str(row.get("secondary") or "")
    primary_pct = float(row.get("primary_mastery_pct") or 0)
    secondary_pct = float(row.get("secondary_mastery_pct") or 0)
    threshold = _threshold(cfg)

    if phase == "learning":
        if primary_pct >= threshold or elapsed_h >= _phase_hours(cfg, "learning"):
            row = {**row, "phase": "mastery_practice", "phase_started_at": now, "primary_mastery_pct": max(primary_pct, threshold)}
        return row

    if phase == "mastery_practice":
        if elapsed_h >= _phase_hours(cfg, "mastery_practice"):
            row = {
                **row,
                "phase": "secondary_learning",
                "phase_started_at": now,
                "secondary_mastery_pct": max(secondary_pct, 5.0),
            }
        return row

    if phase == "secondary_learning":
        if secondary_pct >= threshold or elapsed_h >= _phase_hours(cfg, "learning"):
            row = {**row, "phase": "decay", "phase_started_at": now, "secondary_mastery_pct": max(secondary_pct, threshold)}
        return row

    if phase == "decay":
        if elapsed_h >= _phase_hours(cfg, "decay"):
            row = {**row, "phase": "transition", "phase_started_at": now}
        else:
            row.setdefault("decay_forget_sent", False)
        return row

    if phase == "transition":
        if elapsed_h >= _phase_hours(cfg, "transition"):
            forgotten = list(row.get("forgotten") or [])
            if primary and primary not in forgotten:
                forgotten.append(primary)
            new_primary = secondary or primary
            new_secondary = primary if primary != new_primary else "scout"
            row = {
                **row,
                "primary": new_primary,
                "secondary": new_secondary,
                "phase": "learning",
                "phase_started_at": now,
                "primary_mastery_pct": 0.0,
                "secondary_mastery_pct": 0.0,
                "cycle_index": int(row.get("cycle_index") or 0) + 1,
                "forgotten": forgotten[-6:],
                "decay_forget_sent": False,
            }
        return row

    return {**row, "phase": "learning", "phase_started_at": now}


def _tick_mastery(row: dict[str, Any], cfg: dict[str, Any], *, activity: bool) -> dict[str, Any]:
    if not activity:
        return row
    phase = str(row.get("phase") or "learning")
    learn_rate = float(cfg.get("learning_progress_pct_per_tick") or 0.15)
    decay_rate = float(cfg.get("decay_progress_pct_per_tick") or 0.08)
    primary_pct = float(row.get("primary_mastery_pct") or 0)
    secondary_pct = float(row.get("secondary_mastery_pct") or 0)

    if phase in {"learning", "mastery_practice"}:
        primary_pct = min(100.0, primary_pct + learn_rate)
    elif phase == "secondary_learning":
        secondary_pct = min(100.0, secondary_pct + learn_rate)
    elif phase == "decay":
        primary_pct = max(0.0, primary_pct - decay_rate)
    return {**row, "primary_mastery_pct": primary_pct, "secondary_mastery_pct": secondary_pct}


def focus_profession_for_phase(row: dict[str, Any], cfg: dict[str, Any]) -> str:
    phase = str(row.get("phase") or "learning")
    mapping = cfg.get("scene_focus_by_phase") if isinstance(cfg.get("scene_focus_by_phase"), dict) else {}
    focus = str(mapping.get(phase) or "primary")
    primary = str(row.get("primary") or "")
    secondary = str(row.get("secondary") or "")
    if focus == "secondary":
        return secondary or primary
    if focus == "transition":
        return secondary if phase in {"decay", "transition"} else primary
    return primary


def scene_tags_for_profession(cfg: dict[str, Any], profession: str) -> set[str]:
    tags_map = cfg.get("profession_scene_tags") if isinstance(cfg.get("profession_scene_tags"), dict) else {}
    raw = tags_map.get(profession.strip().lower()) or []
    if isinstance(raw, list):
        return {str(t).strip().lower() for t in raw if str(t).strip()}
    return set()


def scene_matches_focus(scene_id: str, focus_profession: str, cfg: dict[str, Any]) -> bool:
    sid = scene_id.strip().lower()
    if not sid or not focus_profession:
        return False
    tags = scene_tags_for_profession(cfg, focus_profession)
    if sid in tags:
        return True
    return any(tag in sid for tag in tags)


def pick_scene_index_for_lifecycle(
    scenes: list[dict[str, Any]],
    *,
    base_index: int,
    focus_profession: str,
    cfg: dict[str, Any],
) -> int:
    if not scenes:
        return 0
    n = len(scenes)
    for offset in range(n):
        idx = (base_index + offset) % n
        sid = str(scenes[idx].get("id") or "").strip()
        if scene_matches_focus(sid, focus_profession, cfg):
            return idx
    return base_index % n


def build_prompt_block(view: ProfessionLifecycleView) -> str:
    return (
        f"Cycle metier (joueur autonome, pas ancre PNJ): phase={view.phase}, "
        f"metier actif={view.focus_profession}, principal={view.primary} "
        f"({view.primary_mastery_pct:.0f}%), secondaire={view.secondary} "
        f"({view.secondary_mastery_pct:.0f}%), cycle={view.cycle_index}. "
        f"Objectif: progresser comme un vrai joueur (economie, social, quetes), "
        f"pas de conscience collective."
    )


def tick_player_lifecycle(
    player: Core3IaPlayer,
    *,
    activity: bool = True,
    persist: bool = True,
) -> ProfessionLifecycleView:
    if not player.profession_dynamic:
        return ProfessionLifecycleView(
            player_id=player.id,
            primary=player.profession_current,
            secondary=player.profession_secondary,
            phase="fixed",
            focus_profession=player.profession_current,
            primary_mastery_pct=100.0,
            secondary_mastery_pct=0.0,
            cycle_index=0,
            forgotten=(),
            prompt_block=player_prompt_context_static(player),
        )

    cfg = load_lifecycle_config()
    registry = load_state_registry()
    row = dict(registry.get(player.id) or _default_row(player))
    now = int(time.time())
    row["last_tick_at"] = now
    row = _tick_mastery(row, cfg, activity=activity)
    row = _advance_phase(row, cfg, now)

    focus = focus_profession_for_phase(row, cfg)
    view = ProfessionLifecycleView(
        player_id=player.id,
        primary=str(row.get("primary") or player.profession_current),
        secondary=str(row.get("secondary") or player.profession_secondary),
        phase=str(row.get("phase") or "learning"),
        focus_profession=focus,
        primary_mastery_pct=float(row.get("primary_mastery_pct") or 0),
        secondary_mastery_pct=float(row.get("secondary_mastery_pct") or 0),
        cycle_index=int(row.get("cycle_index") or 0),
        forgotten=tuple(str(x) for x in (row.get("forgotten") or []) if str(x).strip()),
        prompt_block="",
    )
    view = ProfessionLifecycleView(**{**view.__dict__, "prompt_block": build_prompt_block(view)})

    if persist:
        registry[player.id] = row
        save_state_registry(registry)
    return view


def player_prompt_context_static(player: Core3IaPlayer) -> str:
    from lbg_agents.core3_players import player_prompt_context

    return player_prompt_context(player)


def effective_profession_current(player: Core3IaPlayer) -> str:
    view = tick_player_lifecycle(player, activity=False, persist=False)
    return view.focus_profession or player.profession_current


def lifecycle_context_dict(player: Core3IaPlayer, *, activity: bool = True) -> dict[str, str]:
    view = tick_player_lifecycle(player, activity=activity, persist=True)
    return {
        "profession_current": view.focus_profession,
        "focus_profession": view.focus_profession,
        "profession_primary": view.primary,
        "profession_secondary": view.secondary,
        "profession_phase": view.phase,
        "primary_mastery_pct": f"{view.primary_mastery_pct:.0f}",
        "secondary_mastery_pct": f"{view.secondary_mastery_pct:.0f}",
        "lifecycle_block": view.prompt_block,
    }


def decay_forget_profession(player: Core3IaPlayer) -> str | None:
    """Metier a desapprendre pendant la phase decay (primaire en oubli)."""
    registry = load_state_registry()
    row = registry.get(player.id)
    if not isinstance(row, dict) or str(row.get("phase") or "") != "decay":
        return None
    if row.get("decay_forget_sent"):
        return None
    return str(row.get("primary") or player.profession_current or "").strip() or None


def mark_decay_forget_sent(player_id: str) -> None:
    registry = load_state_registry()
    row = dict(registry.get(player_id) or {})
    if str(row.get("phase") or "") != "decay":
        return
    row["decay_forget_sent"] = True
    registry[player_id] = row
    save_state_registry(registry)


def deterministic_decay_action(
    player: Core3IaPlayer,
    *,
    enqueue,
) -> dict[str, Any] | None:
    prof = decay_forget_profession(player)
    if not prof:
        return None
    out = enqueue(
        player,
        action="skill_forget",
        message=prof,
    )
    mark_decay_forget_sent(player.id)
    out["reason"] = "lifecycle_decay_forget"
    return out
