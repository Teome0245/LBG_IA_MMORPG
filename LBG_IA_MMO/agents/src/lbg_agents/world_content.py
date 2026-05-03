"""Catalogue monde partagé (races, bestiaire) — JSON sous LBG_IA_MMO/content/world/."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_races_by_id: dict[str, dict[str, Any]] | None = None
_creatures_by_id: dict[str, dict[str, Any]] | None = None


def reset_cache() -> None:
    global _races_by_id, _creatures_by_id
    _races_by_id = None
    _creatures_by_id = None


def content_dir() -> Path:
    raw = os.environ.get("LBG_WORLD_CONTENT_DIR", "").strip()
    if raw:
        return Path(raw)
    # lbg_agents/world_content.py -> parents[3] = LBG_IA_MMO
    return Path(__file__).resolve().parents[3] / "content" / "world"


def load_races_by_id() -> dict[str, dict[str, Any]]:
    global _races_by_id
    if _races_by_id is not None:
        return _races_by_id
    path = content_dir() / "races.json"
    out: dict[str, dict[str, Any]] = {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _races_by_id = out
        return out
    rows = data.get("races") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        _races_by_id = out
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        rid = row.get("id")
        if isinstance(rid, str) and rid.strip():
            out[rid.strip()] = row
    _races_by_id = out
    return out


def load_creatures_by_id() -> dict[str, dict[str, Any]]:
    global _creatures_by_id
    if _creatures_by_id is not None:
        return _creatures_by_id
    path = content_dir() / "creatures.json"
    out: dict[str, dict[str, Any]] = {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _creatures_by_id = out
        return out
    rows = data.get("creatures") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        _creatures_by_id = out
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        rid = row.get("id")
        if isinstance(rid, str) and rid.strip():
            out[rid.strip()] = row
    _creatures_by_id = out
    return out


def list_race_ids() -> list[str]:
    return sorted(load_races_by_id().keys())


def race_display_map() -> dict[str, str]:
    """Carte ``race_id`` → libellé affichable (pour APIs / clients légers)."""
    return {rid: race_display_name(rid) for rid in load_races_by_id().keys()}


def race_display_name(race_id: str) -> str:
    m = load_races_by_id().get((race_id or "").strip())
    if not isinstance(m, dict):
        return (race_id or "").strip() or race_id
    dn = m.get("display_name")
    return dn.strip() if isinstance(dn, str) and dn.strip() else str(m.get("id", race_id))


def format_race_for_prompt(race_id: str) -> str | None:
    rid = (race_id or "").strip()
    if not rid:
        return None
    m = load_races_by_id().get(rid)
    if not isinstance(m, dict):
        return f"Race (référence): {rid}."
    dn = m.get("display_name")
    name = dn.strip() if isinstance(dn, str) and dn.strip() else rid
    lore = m.get("lore_one_liner")
    morph = m.get("morphology")
    bits: list[str] = [f"Race du personnage: {name} ({rid})."]
    if isinstance(morph, str) and morph.strip():
        bits.append(morph.strip())
    if isinstance(lore, str) and lore.strip():
        bits.append(lore.strip())
    fa = m.get("abilities")
    if isinstance(fa, list) and fa:
        feats = [str(x).strip() for x in fa[:4] if isinstance(x, str) and str(x).strip()]
        if feats:
            bits.append("Traits typiques: " + ", ".join(feats) + ".")
    return " ".join(bits)


def format_creature_refs_for_prompt(ids: object, *, max_refs: int = 6) -> str | None:
    if not isinstance(ids, list):
        return None
    raw: list[str] = []
    for x in ids:
        if isinstance(x, str) and x.strip():
            raw.append(x.strip())
    if not raw:
        return None
    by = load_creatures_by_id()
    parts: list[str] = []
    for i in raw[: max(1, min(max_refs, 12))]:
        c = by.get(i)
        if isinstance(c, dict):
            nm = c.get("name")
            bio = c.get("biome")
            d = c.get("danger_level")
            if isinstance(nm, str) and nm.strip():
                if isinstance(bio, str) and bio.strip() and d is not None:
                    parts.append(f"{nm.strip()} ({bio.strip()}, danger {d})")
                else:
                    parts.append(nm.strip())
            else:
                parts.append(i)
        else:
            parts.append(i)
    if not parts:
        return None
    return "Créatures mentionnées (bestiaire): " + "; ".join(parts) + "."
