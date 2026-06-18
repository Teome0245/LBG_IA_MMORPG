"""Mémoire d'expériences ops ("apprentissage léger") pour le moteur de jobs.

Rapatrié de LBG_Project_03 (`orchestrator/memory/store.py`) en version **sans dépendance**
(pas de Chroma) : un journal append-only ``experiences.jsonl`` + un index mémoire, et un
rappel par recouvrement de tokens (``recall_similar``). Le planner réinjecte ces souvenirs
pour éviter de répéter les mêmes échecs.

Best-effort : aucune erreur disque ne remonte ; en l'absence de fichier, tout reste en mémoire.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

_MAX_NOTES = 500
_TOKEN_RE_SPLIT = None  # compilé paresseusement


@dataclass
class ExperienceNote:
    goal: str
    outcome: str  # "success" | "failed"
    problem: str = ""
    resolution: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    id: str = ""


_loaded = False
_notes: list[dict[str, Any]] = []


def memory_enabled() -> bool:
    return os.environ.get("LBG_JOBS_MEMORY_ENABLED", "1").strip().lower() in ("1", "true", "yes", "on")


def memory_path() -> str:
    """Chemin du journal d'expériences. Défaut : à côté de l'état des jobs.

    Vide si la persistance des jobs est désactivée (``LBG_JOBS_STATE_PATH=""``) et qu'aucun
    chemin explicite n'est fourni : la mémoire reste alors **volatile** (RAM uniquement).
    """
    p = os.environ.get("LBG_JOBS_MEMORY_PATH", "").strip()
    if p:
        return p
    state = os.environ.get("LBG_JOBS_STATE_PATH", "/var/lib/lbg/jobs/state.json").strip()
    if not state:
        return ""
    parent = os.path.dirname(state) or "."
    return os.path.join(parent, "experiences.jsonl")


def reset_for_tests() -> None:
    global _loaded, _notes
    _loaded = False
    _notes = []


def _tokens(text: str) -> set[str]:
    import re

    return {t for t in re.split(r"[^a-z0-9]+", (text or "").lower()) if len(t) >= 3}


def _ensure_loaded() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    path = memory_path()
    if not path:
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    note = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(note, dict) and isinstance(note.get("goal"), str):
                    _notes.append(note)
    except FileNotFoundError:
        return
    except Exception:
        return
    if len(_notes) > _MAX_NOTES:
        del _notes[: len(_notes) - _MAX_NOTES]


def record_experience(
    goal: str,
    *,
    outcome: str,
    problem: str = "",
    resolution: str = "",
    tags: list[str] | None = None,
) -> None:
    """Enregistre une expérience (succès/échec). Best-effort."""
    if not memory_enabled():
        return
    g = (goal or "").strip()
    if not g:
        return
    _ensure_loaded()
    note = asdict(
        ExperienceNote(
            goal=g[:500],
            outcome=(outcome or "").strip() or "unknown",
            problem=(problem or "")[:800],
            resolution=(resolution or "")[:800],
            tags=[t for t in (tags or []) if isinstance(t, str) and t.strip()][:8],
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            id=uuid.uuid4().hex[:12],
        )
    )
    _notes.append(note)
    if len(_notes) > _MAX_NOTES:
        del _notes[: len(_notes) - _MAX_NOTES]
    path = memory_path()
    if not path:
        return
    try:
        parent = os.path.dirname(path) or "."
        os.makedirs(parent, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(note, ensure_ascii=False) + "\n")
    except Exception:
        # L'index mémoire reste la source de vérité courante.
        return


def recall_similar(goal: str, k: int = 3) -> list[dict[str, Any]]:
    """Souvenirs les plus proches de l'objectif (recouvrement de tokens). Best-effort."""
    if not memory_enabled():
        return []
    _ensure_loaded()
    if not _notes:
        return []
    q = _tokens(goal)
    if not q:
        return []
    scored: list[tuple[float, dict[str, Any]]] = []
    for note in _notes:
        nt = _tokens(str(note.get("goal", "")))
        if not nt:
            continue
        overlap = len(q & nt)
        if overlap <= 0:
            continue
        score = overlap / float(len(q | nt))
        scored.append((score, note))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [note for _, note in scored[: max(1, k)]]


def format_memories_for_prompt(memories: list[dict[str, Any]] | None) -> str:
    """Bloc texte court (souvenirs) pour un prompt de planification LLM."""
    if not memories:
        return ""
    lines = []
    for m in memories[:3]:
        goal = str(m.get("goal", ""))[:120]
        outcome = str(m.get("outcome", ""))
        reso = str(m.get("resolution", ""))[:160]
        prob = str(m.get("problem", ""))[:160]
        lines.append(f"- objectif « {goal} » → {outcome}" + (f" ; résolution : {reso}" if reso else "") + (f" ; souci : {prob}" if prob else ""))
    return "\n".join(lines)
