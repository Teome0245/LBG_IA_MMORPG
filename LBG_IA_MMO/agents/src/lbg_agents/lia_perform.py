"""Catalogue d'actions perform (métier / gestes) pour Lia."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_CATALOG_CACHE: dict[str, Any] | None = None


def catalog_path() -> Path:
    raw = os.environ.get("LBG_LIA_PERFORM_CATALOG_JSON", "").strip()
    if raw:
        return Path(raw)
    for candidate in (
        Path("/opt/LBG_IA_MMO/content/core3/lia_perform_catalog.json"),
        Path(__file__).resolve().parents[3] / "content" / "core3" / "lia_perform_catalog.json",
    ):
        if candidate.is_file():
            return candidate
    return Path("content/core3/lia_perform_catalog.json")


def load_perform_catalog() -> dict[str, Any]:
    global _CATALOG_CACHE
    if _CATALOG_CACHE is not None:
        return _CATALOG_CACHE
    path = catalog_path()
    if not path.is_file():
        _CATALOG_CACHE = {"performs": []}
        return _CATALOG_CACHE
    _CATALOG_CACHE = json.loads(path.read_text(encoding="utf-8"))
    return _CATALOG_CACHE


def perform_ids() -> list[str]:
    cat = load_perform_catalog()
    raw = cat.get("performs")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for row in raw:
        if isinstance(row, dict) and row.get("id"):
            out.append(str(row["id"]).strip())
    return out


def is_valid_perform(perform_id: str) -> bool:
    pid = (perform_id or "").strip().lower()
    return pid in {p.lower() for p in perform_ids()}


def perform_catalog_hint() -> str:
    cat = load_perform_catalog()
    rows = cat.get("performs")
    if not isinstance(rows, list) or not rows:
        return "perform : message = id (dance, greet, search, forage, meditate, conduct, …)."
    parts: list[str] = []
    for row in rows[:12]:
        if not isinstance(row, dict):
            continue
        pid = str(row.get("id", "")).strip()
        label = str(row.get("label", "")).strip()
        if pid:
            parts.append(f"{pid}" + (f" ({label})" if label else ""))
    return (
        "perform : geste métier / roleplay — message = id parmi "
        + ", ".join(parts)
        + ". Préfère dance ou greet en cantina, search/forage en exploration, conduct pour guider."
    )
