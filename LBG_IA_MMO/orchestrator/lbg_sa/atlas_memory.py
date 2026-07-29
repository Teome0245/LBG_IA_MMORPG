"""Apprentissages Atlas (admin_infra) → namespace team/atlas."""

from __future__ import annotations

from typing import Any

from lbg_sa.memory_store import get_memory_store, lbg_sa_memory_enabled
from lbg_sa.module_registry import get_module

_ATLAS_NS = "team/atlas"


def atlas_memory_namespace() -> str:
    mod = get_module("atlas_llm")
    return mod.memory_namespace if mod else _ATLAS_NS


def _gap_lines(platform: dict[str, Any], ollama: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for g in platform.get("gaps") or []:
        if isinstance(g, str) and g.strip():
            lines.append(g.strip())
    for g in ollama.get("gaps") or []:
        if isinstance(g, str) and g.strip():
            lines.append(g.strip())
    return lines[:12]


def build_atlas_learning_summary(
    *,
    platform: dict[str, Any],
    ollama: dict[str, Any],
    workflow_ok: bool,
) -> str:
    perimeter = platform.get("perimeter") if isinstance(platform.get("perimeter"), list) else []
    hosts_ok = int(platform.get("hosts_ok") or 0)
    hosts_total = int(platform.get("hosts_total") or 0)
    gaps = _gap_lines(platform, ollama)
    status = "ok" if workflow_ok else "attention"
    gap_part = f" ; gaps: {'; '.join(gaps[:4])}" if gaps else ""
    ollama_track = str(ollama.get("track") or "ollama")
    topo = ""
    if isinstance(ollama.get("topology"), dict):
        topo = f" ; heavy={ollama['topology'].get('heavy')} light={ollama['topology'].get('light')}"
    elif isinstance(platform.get("topology"), dict):
        topo = " ; dual-llm 110/111"
    return (
        f"Atlas run — {status} ; périmètre {hosts_ok}/{hosts_total} "
        f"({', '.join(str(p) for p in perimeter[:6])}) ; {ollama_track}{topo}{gap_part}"
    )[:2000]


def record_atlas_admin_infra_run(
    task_id: str,
    *,
    platform: dict[str, Any],
    ollama: dict[str, Any],
    workflow_ok: bool,
) -> dict[str, object]:
    """Append une leçon et retourne un bloc pour le résultat workflow."""
    if not lbg_sa_memory_enabled():
        return {"enabled": False, "recorded": False, "namespace": atlas_memory_namespace()}

    store = get_memory_store(atlas_memory_namespace())
    summary = build_atlas_learning_summary(platform=platform, ollama=ollama, workflow_ok=workflow_ok)
    tags = ["atlas", "admin_infra", "lbg_sa"]
    if not workflow_ok:
        tags.append("gap")
    if platform.get("gaps"):
        tags.append("perimeter")
    store.append_learning(
        summary,
        tags=tags,
        payload={
            "workflow_ok": workflow_ok,
            "hosts_ok": platform.get("hosts_ok"),
            "hosts_total": platform.get("hosts_total"),
            "ollama_ok": ollama.get("ok"),
            "gap_count": len(_gap_lines(platform, ollama)),
        },
        source_task_id=task_id,
    )
    return {
        "enabled": True,
        "recorded": True,
        "namespace": atlas_memory_namespace(),
        "path": str(store.path()) if store.path() else None,
        "summary": summary,
    }


def recall_atlas_hints(query: str = "atlas admin_infra bench ollama périmètre", *, limit: int = 3) -> dict[str, object]:
    if not lbg_sa_memory_enabled():
        return {"enabled": False, "hints": "", "entries": 0}
    store = get_memory_store(atlas_memory_namespace())
    entries = store.recall(query, limit=limit)
    return {
        "enabled": True,
        "hints": store.context_hints(query, limit=limit),
        "entries": len(entries),
    }
