"""Agent Économie macro — signaux shops JSON, règles seuils, actions proposées (dry-run par défaut)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from lbg_agents.core3_economy_loop import load_economy_config


def execute_sql_mcp_query(query: str, server_id: str = "precu") -> dict[str, Any]:
    """Exécute une requête SQL en utilisant la validation et la config du package MCP SQL."""
    try:
        import sys
        here = Path(__file__).resolve()
        root_dir = here.parents[3]
        tools_path = root_dir / "tools"
        if str(tools_path) not in sys.path:
            sys.path.insert(0, str(tools_path))
        
        from mcp_lbg_sql_server.server import _db_config, _validate_readonly
        
        ok, err = _validate_readonly(query)
        if not ok:
            return {"ok": False, "error": err}
            
        import pymysql
        if pymysql is None:
            return {"ok": False, "error": "pymysql non disponible"}
            
        cfg = _db_config(server_id)
        with pymysql.connect(**cfg) as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall()
                return {"ok": True, "rows": rows}
    except Exception as e:
        return {"ok": False, "error": f"Erreur SQL MCP : {e}"}


def economy_rules_path() -> Path:
    raw = os.environ.get("LBG_ECONOMY_RULES_JSON", "").strip()
    if raw:
        return Path(raw)
    for candidate in (
        Path("/opt/LBG_IA_MMO/content/core3/economy_rules_v1.json"),
        Path(__file__).resolve().parents[3] / "content" / "core3" / "economy_rules_v1.json",
    ):
        if candidate.is_file():
            return candidate
    return Path("content/core3/economy_rules_v1.json")


def load_economy_rules() -> dict[str, Any]:
    path = economy_rules_path()
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    return {
        "schema_version": 1,
        "stock_low_threshold": 15,
        "stock_critical_threshold": 5,
        "inflation_price_ratio": 2.5,
    }


def _shop_items(shop: dict[str, Any]) -> list[dict[str, Any]]:
    items = shop.get("items")
    if not isinstance(items, list):
        return []
    return [row for row in items if isinstance(row, dict)]


def collect_shop_signals(
    economy: dict[str, Any] | None = None,
    *,
    stock_overrides: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Construit les signaux à partir de core3_economy.json (+ overrides optionnels)."""
    cfg = economy if isinstance(economy, dict) else load_economy_config()
    shops = cfg.get("shops")
    if not isinstance(shops, list):
        return []

    overrides = stock_overrides if isinstance(stock_overrides, dict) else {}
    signals: list[dict[str, Any]] = []
    for shop in shops:
        if not isinstance(shop, dict):
            continue
        shop_id = str(shop.get("shop_id") or "").strip()
        pilot_id = str(shop.get("pilot_id") or "").strip()
        for item in _shop_items(shop):
            template = str(item.get("template") or "").strip()
            if not template:
                continue
            key = f"{shop_id}:{template}"
            stock_raw = overrides.get(key, item.get("stock"))
            try:
                stock = int(stock_raw)
            except (TypeError, ValueError):
                stock = 0
            try:
                price = int(item.get("price") or 0)
            except (TypeError, ValueError):
                price = 0
            signals.append(
                {
                    "shop_id": shop_id,
                    "pilot_id": pilot_id,
                    "item_template": template,
                    "label": str(item.get("label") or "").strip(),
                    "stock": stock,
                    "price": price,
                    "location_id": str(shop.get("location_id") or "").strip(),
                }
            )
    return signals


def _median_price(signals: list[dict[str, Any]], template: str) -> float | None:
    prices = [int(s["price"]) for s in signals if s.get("item_template") == template and int(s.get("price") or 0) > 0]
    if not prices:
        return None
    prices.sort()
    mid = len(prices) // 2
    if len(prices) % 2:
        return float(prices[mid])
    return (prices[mid - 1] + prices[mid]) / 2.0


def evaluate_rules(
    signals: list[dict[str, Any]],
    *,
    rules: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Évalue les signaux ; retourne une liste d'évaluations (signal type + métadonnées)."""
    r = rules if isinstance(rules, dict) else load_economy_rules()
    low = int(r.get("stock_low_threshold") or 15)
    critical = int(r.get("stock_critical_threshold") or 5)
    inflation_ratio = float(r.get("inflation_price_ratio") or 2.5)

    evaluations: list[dict[str, Any]] = []
    for sig in signals:
        stock = int(sig.get("stock") or 0)
        template = str(sig.get("item_template") or "")
        price = int(sig.get("price") or 0)
        shop_id = str(sig.get("shop_id") or "")

        if stock <= 0:
            evaluations.append(
                {
                    "signal": "stock_empty",
                    "severity": "critical",
                    "shop_id": shop_id,
                    "item_template": template,
                    "stock": stock,
                    "pilot_id": sig.get("pilot_id"),
                }
            )
            continue

        if stock <= critical:
            evaluations.append(
                {
                    "signal": "resource_scarcity",
                    "severity": "critical",
                    "shop_id": shop_id,
                    "item_template": template,
                    "stock": stock,
                    "pilot_id": sig.get("pilot_id"),
                }
            )
            continue

        if stock <= low:
            evaluations.append(
                {
                    "signal": "stock_low",
                    "severity": "warn",
                    "shop_id": shop_id,
                    "item_template": template,
                    "stock": stock,
                    "pilot_id": sig.get("pilot_id"),
                }
            )

        median = _median_price(signals, template)
        if median and price > median * inflation_ratio:
            evaluations.append(
                {
                    "signal": "price_inflation",
                    "severity": "warn",
                    "shop_id": shop_id,
                    "item_template": template,
                    "price": price,
                    "median_price": median,
                    "pilot_id": sig.get("pilot_id"),
                }
            )

    evaluations.sort(key=lambda row: (0 if row.get("severity") == "critical" else 1, str(row.get("shop_id"))))
    return evaluations


def _quest_for_scarcity(shop_id: str, template: str) -> tuple[str, str]:
    if shop_id == "shop:mos_cantina_bar":
        return "quest:mos_gather_bar_fruit", "npc:core3_barman_jax"
    if "fruit_s1" in template:
        return "quest:mos_gather_bar_fruit", "npc:core3_barman_jax"
    return "quest:mos_gather_bar_spice", "npc:core3_scribe"


def propose_actions(evaluations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Traduit les évaluations en actions macro (sans exécution)."""
    actions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ev in evaluations:
        signal = str(ev.get("signal") or "")
        shop_id = str(ev.get("shop_id") or "")
        template = str(ev.get("item_template") or "")
        key = f"{signal}:{shop_id}:{template}"
        if key in seen:
            continue
        seen.add(key)

        if signal in {"resource_scarcity", "stock_empty", "stock_low"}:
            quest_id, giver = _quest_for_scarcity(shop_id, template)
            actions.append(
                {
                    "action": "offer_quest",
                    "signal": signal,
                    "severity": ev.get("severity"),
                    "shop_id": shop_id,
                    "item_template": template,
                    "stock": ev.get("stock"),
                    "quest_id": quest_id,
                    "giver_pilot_id": giver,
                }
            )
        elif signal == "price_inflation":
            actions.append(
                {
                    "action": "adjust_price_json",
                    "signal": signal,
                    "severity": ev.get("severity"),
                    "shop_id": shop_id,
                    "item_template": template,
                    "suggested_price": int(float(ev.get("median_price") or 0) * 1.1),
                    "note": "dry_run — modifier core3_economy.json manuellement ou via job approuvé",
                }
            )
    return actions


def run_economy_director_tick(
    *,
    dry_run: bool = True,
    economy: dict[str, Any] | None = None,
    stock_overrides: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Tick macro économie — lecture seule ; n'écrit pas en prod si dry_run=True."""
    signals = collect_shop_signals(economy, stock_overrides=stock_overrides)
    evaluations = evaluate_rules(signals)
    proposed = propose_actions(evaluations)
    
    # Validation / Test de connectivité à MariaDB via notre helper SQL sécurisé (Option B)
    db_status = {"ok": False, "error": "Non testé"}
    try:
        # Exécuter une requête simple en lecture seule : SELECT 1 (ou SHOW TABLES)
        res_db = execute_sql_mcp_query("SELECT 1 as alive", server_id="precu")
        if res_db.get("ok"):
            db_status = {"ok": True, "server": "192.168.0.245", "alive": True}
        else:
            db_status = {"ok": False, "error": res_db.get("error")}
    except Exception as e:
        db_status = {"ok": False, "error": str(e)}

    return {
        "ok": True,
        "agent": "economy_director",
        "dry_run": dry_run,
        "ts": int(time.time()),
        "signal_count": len(signals),
        "evaluation_count": len(evaluations),
        "proposed_actions": proposed,
        "evaluations": evaluations[:20],
        "database_status": db_status,
    }
