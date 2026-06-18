"""Boucle economie MVP par phase de cycle metier (forage → craft → vente)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from lbg_agents.core3_players import Core3IaPlayer
from lbg_agents.core3_profession_lifecycle import ProfessionLifecycleView

ECONOMY_STEPS = ("forage", "craft", "vendor_sell", "vendor_buy", "trainer")


def economy_config_path() -> Path:
    raw = os.environ.get("LBG_CORE3_ECONOMY_JSON", "").strip()
    if raw:
        return Path(raw)
    for candidate in (
        Path("/opt/LBG_IA_MMO/content/core3/core3_economy.json"),
        Path(__file__).resolve().parents[3] / "content" / "core3" / "core3_economy.json",
    ):
        if candidate.is_file():
            return candidate
    return Path("content/core3/core3_economy.json")


def load_economy_config() -> dict[str, Any]:
    path = economy_config_path()
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def default_craft_recipe_id() -> str:
    chains = load_economy_config().get("craft_chains")
    if isinstance(chains, list) and chains:
        first = chains[0]
        if isinstance(first, dict):
            return str(first.get("id") or "craft:mos_ration_pack").strip()
    return "craft:mos_ration_pack"


def default_vendor_pilot() -> str:
    shops = load_economy_config().get("shops")
    if isinstance(shops, list):
        for shop in shops:
            if isinstance(shop, dict) and str(shop.get("shop_id") or "") == "shop:mos_cantina_bar":
                return str(shop.get("pilot_id") or "npc:core3_barman_jax")
    return "npc:core3_scribe"


def _snapshot_flag(snap: dict[str, Any], key: str) -> bool:
    val = snap.get(key)
    if isinstance(val, bool):
        return val
    return str(val or "").strip().lower() in {"1", "true", "yes", "on"}


def pick_economy_step(
    player: Core3IaPlayer,
    *,
    snapshot: dict[str, Any] | None,
    lifecycle: ProfessionLifecycleView | None,
) -> str:
    snap = snapshot if isinstance(snapshot, dict) else {}
    phase = lifecycle.phase if lifecycle else "learning"
    focus = (lifecycle.focus_profession if lifecycle else player.profession_current).strip().lower()
    inv_count = int(snap.get("inventory_count") or 0)
    inv_full = _snapshot_flag(snap, "inventory_full") or _snapshot_flag(snap, "inventory_near_full")

    if phase == "decay":
        return "vendor_sell" if inv_count > 0 else "trainer"

    if phase == "transition":
        return "vendor_buy"

    if inv_full:
        return "vendor_sell"

    if inv_count >= 2 and "craft_combine" in player.capabilities:
        return "craft"

    if focus in {"scout", "artisan"}:
        return "forage"

    if focus == "entertainer":
        return "vendor_buy"

    if focus in {"vendor", "marksman", "brawler", "medic"}:
        return "trainer"

    return "forage" if "forage" in player.capabilities else "trainer"


def economy_prompt_block(step: str) -> str:
    labels = {
        "forage": "Economie: collecter ressources (forage/search).",
        "craft": "Economie: craft_combine ration pack si assez de matieres.",
        "vendor_sell": "Economie: vendor_sell surplus au comptoir cantina.",
        "vendor_buy": "Economie: vendor_buy item 0 pour apprendre le commerce.",
        "trainer": "Economie: visite trainer pour monter le metier actif.",
    }
    return labels.get(step, "")


def deterministic_economy_action(
    player: Core3IaPlayer,
    *,
    snapshot: dict[str, Any] | None,
    lifecycle: ProfessionLifecycleView | None,
    enqueue,
) -> dict[str, Any] | None:
    snap = snapshot if isinstance(snapshot, dict) else {}
    step = pick_economy_step(player, snapshot=snap, lifecycle=lifecycle)
    vendor = default_vendor_pilot()
    recipe = default_craft_recipe_id()

    if step == "forage":
        if _snapshot_flag(snap, "in_interior"):
            out = enqueue(
                player,
                action="move_to",
                message="mos_eisley_outdoor",
                snapshot=snap,
                target_xyz=(3520.0, -4810.0, 5.0),
            )
            out["reason"] = "economy_exit_for_forage"
            return out
        out = enqueue(player, action="perform", message="forage", snapshot=snap)
        out["reason"] = "economy_forage"
        return out

    if step == "craft":
        out = enqueue(player, action="craft_combine", message=recipe, snapshot=snap)
        out["reason"] = "economy_craft"
        return out

    if step == "vendor_sell":
        out = enqueue(
            player,
            action="vendor_sell",
            message=f"{vendor}|0",
            snapshot=snap,
        )
        out["reason"] = "economy_vendor_sell"
        return out

    if step == "vendor_buy":
        out = enqueue(
            player,
            action="vendor_buy",
            message=f"{vendor}|0",
            snapshot=snap,
        )
        out["reason"] = "economy_vendor_buy"
        return out

    if step == "trainer":
        if _snapshot_flag(snap, "in_interior"):
            out = enqueue(player, action="interact", message="examine:trainer", snapshot=snap)
        else:
            out = enqueue(player, action="housing_enter", message="training", snapshot=snap)
        out["reason"] = "economy_trainer"
        return out

    return None
