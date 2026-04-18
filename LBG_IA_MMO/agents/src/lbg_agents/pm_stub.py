"""Stub déterministe — agent « chef de projet » (jalons, risques, liens doc)."""

from __future__ import annotations

import os
import pathlib
import re
from typing import Any


_DEFAULT_PLAN_PATHS = (
    "/opt/LBG_IA_MMO/docs/plan_de_route.md",  # VM (systemd)
    "docs/plan_de_route.md",  # dev (cwd repo)
)


def _read_plan_text() -> str | None:
    """
    Lecture bornée du plan de route (pas d’accès fichier arbitraire).

    - Chemin configurable via `LBG_PM_PLAN_PATH`
    - Sinon : chemins par défaut connus (VM / dev)
    """
    candidates: list[str] = []
    p = os.environ.get("LBG_PM_PLAN_PATH", "").strip()
    if p:
        candidates.append(p)
    candidates.extend(_DEFAULT_PLAN_PATHS)
    for c in candidates:
        try:
            path = pathlib.Path(c)
            if not path.exists() or not path.is_file():
                continue
            data = path.read_text(encoding="utf-8", errors="ignore")
            return data[:40000]
        except OSError:
            continue
    return None


def _extract_etape_actuelle(plan_text: str) -> str | None:
    """
    Extrait une seule ligne « Étape actuelle » pour aider le chef de projet.
    """
    for ln in plan_text.splitlines():
        s = ln.strip()
        if not s:
            continue
        # Exemple: **Étape actuelle** : ...
        if s.lower().startswith("**étape actuelle**") or s.lower().startswith("**etape actuelle**"):
            return s[:600]
    return None


def _extract_file_attente(plan_text: str) -> str | None:
    for ln in plan_text.splitlines():
        s = ln.strip()
        if not s:
            continue
        low = s.lower()
        if low.startswith("**file d’attente") or low.startswith("**file d'attente"):
            return s[:800]
    return None


def _strip_md_noise(s: str) -> str:
    t = s.replace("**", "").strip()
    return re.sub(r"\s+", " ", t).strip()


def _milestones_max() -> int:
    raw = os.environ.get("LBG_PM_MILESTONES_MAX", "8").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 8
    return max(1, min(n, 30))


def _tasks_max() -> int:
    raw = os.environ.get("LBG_PM_TASKS_MAX", "12").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 12
    return max(1, min(n, 40))


def _extract_milestones(plan_text: str) -> list[dict[str, Any]]:
    """
    Jalons = dernières lignes du tableau « État courant » (| YYYY-MM-DD | … |).
    """
    rows: list[tuple[str, str]] = []
    for ln in plan_text.splitlines():
        s = ln.strip()
        m = re.match(r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(.*)$", s)
        if not m:
            continue
        date, rest = m.group(1), m.group(2)
        rest = rest.rstrip()
        if rest.endswith("|"):
            rest = rest[:-1].strip()
        if re.match(r"^-+$", rest.replace(" ", "")):
            continue
        if rest.lower().startswith("date") and "changement" in rest.lower():
            continue
        rows.append((date, rest))
    cap = _milestones_max()
    picked = rows[-cap:] if len(rows) > cap else rows
    out: list[dict[str, Any]] = []
    for i, (date, raw) in enumerate(picked):
        summary = _strip_md_noise(raw)[:220]
        out.append(
            {
                "id": f"m-{date}-{i}",
                "date": date,
                "summary": summary,
                "raw": raw[:400],
            }
        )
    return out


def _tasks_from_etape(etape: str | None) -> list[dict[str, Any]]:
    if not etape:
        return []
    body = etape.split(":", 1)[-1].strip()
    chunks = [c.strip() for c in re.split(r"[;•]|(?:\s+—\s+)", body) if c.strip()]
    if not chunks:
        chunks = [_strip_md_noise(body)[:200]]
    out: list[dict[str, Any]] = []
    for i, ch in enumerate(chunks[:6], start=1):
        t = _strip_md_noise(ch)[:140]
        if not t:
            continue
        out.append(
            {
                "id": f"t-etape-{i}",
                "title": t,
                "status": "open",
                "source": "plan_de_route:etape_actuelle",
            }
        )
    return out


def _tasks_from_file_attente(line: str | None) -> list[dict[str, Any]]:
    if not line:
        return []
    body = line.split(":", 1)[-1].strip()
    t = _strip_md_noise(body)[:240]
    if not t:
        return []
    return [{"id": "t-file-attente-1", "title": t, "status": "open", "source": "plan_de_route:file_attente"}]


def _tasks_from_milestones(milestones: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, m in enumerate(milestones[-3:], start=1):
        d = str(m.get("date") or "")
        s = str(m.get("summary") or "")[:100]
        title = f"Vérifier le jalon du {d}: {s}".strip()
        out.append(
            {
                "id": f"t-milestone-{i}",
                "title": title[:200],
                "status": "open",
                "source": "plan_de_route:etat_courant",
            }
        )
    return out


def run_pm_stub(*, actor_id: str, text: str, context: dict[str, Any]) -> dict[str, Any]:
    t = text.strip()
    site = context.get("agent_site")
    site = site.strip() if isinstance(site, str) and site.strip() else None
    hints: list[str] = []
    tl = t.lower()
    include_plan = context.get("pm_include_plan") is True or bool(
        re.search(
            r"\b(plan de route|roadmap|étape actuelle|etape actuelle|jalons?|tâches?|tasks?|milestones?)\b",
            tl,
        )
    )
    include_structure = (
        include_plan
        or context.get("pm_include_structure") is True
        or context.get("pm_include_tasks") is True
        or context.get("pm_include_milestones") is True
    )
    if re.search(r"\b(risque|blocage|dépendance)\b", tl):
        hints.append("Lister les dépendances externes (LLM, VM, secrets) et un plan de contournement.")
    if re.search(r"\bjalon|milestone|release\b", tl):
        hints.append("Aligner les jalons sur des smokes mesurables (LAN + pytest) dans le plan de route.")
    if re.search(r"\bplan de route|roadmap|vision\b", tl):
        hints.append("Relire docs/plan_de_route.md — une seule « prochaine étape » actionnable à la fois.")
    if not hints:
        hints.append(
            "Structurer la demande (objectif, périmètre, critère de done) puis mettre à jour le plan de route."
        )
    out: dict[str, Any] = {
        "agent": "pm_stub",
        "handler": "project_pm",
        "actor_id": actor_id,
        "brief": {
            "title": "Point projet (stub)",
            "summary": t[:400] + ("…" if len(t) > 400 else ""),
            "hints": hints,
            "docs": ["docs/plan_de_route.md", "docs/architecture.md"],
        },
    }
    if include_plan:
        plan = _read_plan_text()
        if isinstance(plan, str):
            step = _extract_etape_actuelle(plan)
        else:
            step = None
        out["brief"]["current_step"] = step
        out["brief"]["current_step_found"] = step is not None

    if include_structure:
        plan = _read_plan_text()
        if isinstance(plan, str):
            milestones = _extract_milestones(plan)
            fa = _extract_file_attente(plan)
            tasks: list[dict[str, Any]] = []
            tasks.extend(_tasks_from_etape(_extract_etape_actuelle(plan)))
            tasks.extend(_tasks_from_file_attente(fa))
            tasks.extend(_tasks_from_milestones(milestones))
            # Dédupliquer par titre (simple) puis cap global
            seen: set[str] = set()
            deduped: list[dict[str, Any]] = []
            for task in tasks:
                title = str(task.get("title") or "")
                key = title.lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                deduped.append(task)
            cap = _tasks_max()
            out["brief"]["milestones"] = milestones
            out["brief"]["tasks"] = deduped[:cap]
            out["brief"]["file_attente"] = fa
            out["brief"]["file_attente_found"] = fa is not None
        else:
            out["brief"]["milestones"] = []
            out["brief"]["tasks"] = []
            out["brief"]["file_attente"] = None
            out["brief"]["file_attente_found"] = False
    if site:
        out["agent_site"] = site
    return out
