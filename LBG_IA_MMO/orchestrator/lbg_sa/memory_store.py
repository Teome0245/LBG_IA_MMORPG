"""Mémoire LBG Studios Agents (LBG_SA) — namespaces JSONL ancrés sur LBG_TEAM_DB_PATH."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from hybrid_proactive_agent import LongTermMemoryStore, MemoryEntry

_NAMESPACE_RE = re.compile(r"^[a-z][a-z0-9_/\-]{0,63}$")
_store_cache: dict[str, LbgSaMemoryStore] = {}


def _env_first(*keys: str, default: str = "") -> str:
    """Lit LBG_STUDIOS_AGENTS_* puis alias LBG_SA_*."""
    for key in keys:
        val = os.environ.get(key, "").strip()
        if val:
            return val
    return default


def lbg_sa_memory_enabled() -> bool:
    raw = _env_first(
        "LBG_STUDIOS_AGENTS_MEMORY_ENABLED",
        "LBG_SA_MEMORY_ENABLED",
        default="1",
    )
    return raw.lower() in ("1", "true", "yes", "on")


# Alias historique du nom de fonction (imports internes).
studios_agents_memory_enabled = lbg_sa_memory_enabled


def team_db_path() -> str:
    return os.environ.get("LBG_TEAM_DB_PATH", "/var/lib/lbg-ia-mmo/team_tasks.db").strip()


def memory_root() -> Path:
    explicit = _env_first("LBG_STUDIOS_AGENTS_MEMORY_ROOT", "LBG_SA_MEMORY_ROOT")
    if explicit:
        return Path(explicit)
    db = team_db_path()
    if db == ":memory:":
        return Path(_env_first("LBG_STUDIOS_AGENTS_MEMORY_ROOT", "LBG_SA_MEMORY_ROOT", default="/tmp/lbg-sa-memory"))
    parent = Path(os.path.dirname(db) or ".")
    return parent / "lbg_sa" / "memory"


def _sanitize_namespace(namespace: str) -> str:
    ns = (namespace or "").strip().lower().replace("\\", "/")
    if not ns or not _NAMESPACE_RE.match(ns):
        raise ValueError(f"namespace lbg_sa invalide: {namespace!r}")
    return ns


def _namespace_file(namespace: str) -> Path:
    ns = _sanitize_namespace(namespace)
    safe = ns.replace("/", "__")
    return memory_root() / f"{safe}.jsonl"


class LbgSaMemoryStore:
    """Facade par namespace au-dessus de LongTermMemoryStore (salle d'archives)."""

    def __init__(self, namespace: str, *, max_entries: int | None = None) -> None:
        self.namespace = _sanitize_namespace(namespace)
        raw_max = _env_first(
            "LBG_STUDIOS_AGENTS_MEMORY_MAX_ENTRIES",
            "LBG_SA_MEMORY_MAX_ENTRIES",
            default="500",
        )
        try:
            default_max = int(raw_max)
        except ValueError:
            default_max = 500
        self._max = max_entries if max_entries is not None else max(50, min(default_max, 5000))
        path = _namespace_file(self.namespace) if lbg_sa_memory_enabled() else None
        self._inner = LongTermMemoryStore(path=path, max_entries=self._max)

    def append_learning(
        self,
        summary: str,
        *,
        tags: list[str] | None = None,
        payload: dict[str, Any] | None = None,
        source_task_id: str = "",
    ) -> None:
        if not lbg_sa_memory_enabled():
            return
        text = (summary or "").strip()
        if not text:
            return
        merged_tags = [f"ns:{self.namespace}"]
        for t in tags or []:
            if isinstance(t, str) and t.strip():
                merged_tags.append(t.strip())
        body = dict(payload or {})
        if source_task_id:
            body.setdefault("source_task_id", source_task_id)
        body.setdefault("namespace", self.namespace)
        entry = MemoryEntry(summary=text[:2000], tags=merged_tags[:24], payload=body)
        self._inner.append(entry)

    def recall(self, query: str, *, limit: int = 5) -> list[MemoryEntry]:
        return self._inner.recall(query, limit=limit)

    def context_hints(self, query: str, *, limit: int = 3) -> str:
        return self._inner.context_hints(query, limit=limit)

    def path(self) -> Path | None:
        return _namespace_file(self.namespace) if lbg_sa_memory_enabled() else None


def get_memory_store(namespace: str) -> LbgSaMemoryStore:
    ns = _sanitize_namespace(namespace)
    if ns not in _store_cache:
        _store_cache[ns] = LbgSaMemoryStore(ns)
    return _store_cache[ns]


def reset_memory_cache_for_tests() -> None:
    _store_cache.clear()
