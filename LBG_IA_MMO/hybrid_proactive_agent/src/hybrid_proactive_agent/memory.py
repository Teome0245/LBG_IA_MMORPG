from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class MemoryEntry(BaseModel):
    """Épisode stocké pour rappel ultérieur (mémoire longue)."""

    ts: float = Field(default_factory=time.time)
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class LongTermMemoryStore:
    """
    Stockage append-only : RAM + option fichier JSONL.
    Rappel par score textuel (mots) — pas d'embedding ; suffisant pour prototype et tests.
    """

    def __init__(self, path: Path | None = None, max_entries: int = 500) -> None:
        self._path = path
        self._max = max_entries
        self._entries: list[MemoryEntry] = []
        if path and path.exists():
            self._load_jsonl(path)

    def _load_jsonl(self, path: Path) -> None:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            self._entries.append(MemoryEntry.model_validate(data))
        self._entries = self._entries[-self._max :]

    def append(self, entry: MemoryEntry) -> None:
        self._entries.append(entry)
        if len(self._entries) > self._max:
            self._entries = self._entries[-self._max :]
        if self._path:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as f:
                f.write(entry.model_dump_json() + "\n")

    def recall(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        """Entrées les plus pertinentes (recouvrement mots-clés)."""
        q = query.lower().split()
        if not q:
            return list(reversed(self._entries[-limit:]))

        def score(e: MemoryEntry) -> int:
            blob = (e.summary + " " + " ".join(e.tags)).lower()
            return sum(1 for w in q if w and w in blob)

        ranked = sorted(self._entries, key=score, reverse=True)
        return [e for e in ranked if score(e) > 0][:limit] or list(reversed(self._entries[-limit:]))

    def context_hints(self, query: str, limit: int = 3) -> str:
        """Bloc texte à injecter dans un prompt système."""
        lines: list[str] = []
        for e in self.recall(query, limit=limit):
            tag_p = f" [{', '.join(e.tags)}]" if e.tags else ""
            lines.append(f"- {e.summary}{tag_p}")
        return "\n".join(lines) if lines else ""
