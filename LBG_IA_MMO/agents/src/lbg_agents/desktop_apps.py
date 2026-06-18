"""Alias et aides pour ``open_app`` (worker desktop hybride).

Rapatrié de LBG_Project_03 (`lbg_agents/desktop_apps.py` + `desktop_dispatch`) :
- inférence ``open_app`` depuis un texte libre (« lance vghd sur mon pc »),
- normalisation d'alias d'apps (notepad→notepadpp, swg→swgemu, msword→word…),
- extraction d'un chemin ``.exe`` Windows fourni dans l'objectif,
- ``learn:true`` par défaut (allowlist auto-apprise sur le worker) — `LBG_DESKTOP_OPEN_APP_LEARN`,
- messages d'erreur worker → conseils actionnables (`hint_for_desktop_error`).

Module **auto-suffisant** (pur, sans dépendance orchestrateur) : réutilisé par
``orchestrator/services/action_proposal.py`` et ``lbg_agents/dispatch.py``.
"""

from __future__ import annotations

import os
import re
from typing import Any

_OPEN_APP_VERB_RE = re.compile(
    r"\b(?:ouvrir|ouvre|ouvrez|lancer|lance|lancez|demarrer|démarrer|demarre|démarre|demarrez|démarrez|start|launch|open|exécute|execute|exécuter|executer)\b",
    re.IGNORECASE,
)

_OPEN_APP_STOP_TOKENS = frozenset(
    {
        "le", "la", "les", "un", "une", "the", "a", "an",
        "mon", "ma", "mes", "ton", "ta", "pc", "poste",
        "machine", "ordinateur", "windows", "linux",
    }
)

# Apps Office / bureautique : souvent hors PATH → learn + chemin complet sur le PC.
_OFFICE_APPS = frozenset({"word", "winword", "msword", "excel", "outlook", "powerpoint"})

# Jeux / apps hors PATH : learn + chemin explicite (objectif ou LBG_DESKTOP_APP_MAP_JSON).
_CUSTOM_EXE_APPS = frozenset({"swgemu", "word", "winword", "msword"})

_APP_ALIASES: dict[str, str] = {
    "msword": "word",
    "winword": "word",
    "notepad": "notepadpp",
    "notepad++": "notepadpp",
    "mozilla": "firefox",
    "firefox.exe": "firefox",
    "swgemu.exe": "swgemu",
    "swg": "swgemu",
    "starwarsgalaxies": "swgemu",
}

_WIN_EXE_PATH_RE = re.compile(
    r"(?:\(\s*)?([A-Za-z]:[\\/][^\s)\]\"']+\.exe)\s*\)?",
    re.IGNORECASE,
)

_ERROR_HINTS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"WinError\s*2|fichier sp.cifi. est introuvable|FileNotFoundError|introuvable", re.I),
        "Exécutable introuvable sur le PC Windows. Sur le worker (Agent_IA), éditer "
        "C:\\Agent_IA\\desktop.env : ajouter le chemin complet dans LBG_DESKTOP_APP_MAP_JSON, ex. "
        '"word":["C:\\\\Program Files\\\\Microsoft Office\\\\root\\\\Office16\\\\WINWORD.EXE"] '
        'ou "swgemu":["J:\\\\swgemu\\\\StarWarsGalaxies\\\\SWGEmu.exe"]. '
        "Ou indiquer le chemin dans l'objectif entre parenthèses, ou learn:true + LBG_DESKTOP_LEARN_ENABLED=1.",
    ),
    (
        re.compile(r"allowlist|non autoris", re.I),
        "Allowlist worker : réessayez avec learn (auto) — sur le PC activer "
        "LBG_DESKTOP_LEARN_ENABLED=1 dans C:\\Agent_IA\\desktop.env puis relancer le worker, "
        "ou ajouter l'app à LBG_DESKTOP_APP_ALLOWLIST.",
    ),
    (
        re.compile(r"approval", re.I),
        "Jeton desktop requis : fournir context.desktop_approval (ou cocher Dry-run dans le pilot).",
    ),
]


def default_desktop_action_from_text(text: str) -> dict[str, Any] | None:
    """Infère une action ``open_app`` depuis un texte libre, ou ``None`` si rien de sûr.

    Aligné sur ``action_proposal._propose_open_app`` : verbe d'ouverture + token suivant,
    coupé sur ``sur|on|avec|pour|dans`` et nettoyé de « application/appli/prog/programme ».
    """
    raw = (text or "").strip()
    if not raw:
        return None
    normalized = re.sub(r"\s+", " ", raw.lower())
    if not _OPEN_APP_VERB_RE.search(normalized):
        return None
    matches = list(_OPEN_APP_VERB_RE.finditer(raw))
    if not matches:
        return None
    tail = raw[matches[-1].end() :].strip()
    tail = re.sub(
        r"^\s*(?:l['′'])?\s*(?:application|appli|prog|programme)\s+",
        "",
        tail,
        flags=re.IGNORECASE,
    ).strip()
    tail_chunk = re.split(r"\s+(?:sur|on|avec|pour|dans)\s+", tail, maxsplit=1)[0].strip()
    slug = _sanitize_app_slug(tail_chunk)
    if not slug:
        return None
    return {"kind": "open_app", "app": slug, "args": [], "learn": False}


def _sanitize_app_slug(raw_tail: str) -> str | None:
    """Nom court d'app sans chemin / URL ; aligné sur la validation dialogue ``open_app``."""
    t = (raw_tail or "").strip().strip("\"'«»")
    if not t or re.search(r"https?://", t):
        return None
    if "\\" in t or "/" in t or ".." in t:
        return None
    first = re.split(r"\s+", t, maxsplit=1)[0].strip("\"'«»")
    if not first:
        return None
    if len(first) > 80:
        first = first[:80]
    if not re.match(r"^[A-Za-z0-9_.\-]+$", first):
        return None
    if first.lower() in _OPEN_APP_STOP_TOKENS:
        return None
    return first


def extract_exe_path_from_goal(goal: str) -> str | None:
    """Extrait un chemin Windows ``.exe`` depuis l'objectif, ex. ``(J:\\swgemu\\…\\SWGEmu.exe)``."""
    raw = (goal or "").strip()
    if not raw:
        return None
    m = re.search(r"\(\s*([A-Za-z]:[\\/][^)\s]+?\.exe)\s*\)", raw, re.I)
    if m:
        return m.group(1).replace("/", "\\")
    m = _WIN_EXE_PATH_RE.search(raw)
    if m:
        return m.group(1).replace("/", "\\")
    return None


def normalize_desktop_app(app: str) -> str:
    raw = (app or "").strip().lower()
    return _APP_ALIASES.get(raw, raw)


def supervised_auto_learn_enabled() -> bool:
    """``learn:true`` par défaut côté orchestrateur (allowlist auto-apprise sur le worker)."""
    return os.environ.get("LBG_DESKTOP_OPEN_APP_LEARN", "1").strip().lower() in ("1", "true", "yes", "on")


def enrich_open_app_action(action: dict[str, Any], *, force_learn: bool | None = None) -> dict[str, Any]:
    """Normalise l'app (alias) et pose ``learn`` (défaut : auto-learn activé)."""
    out = dict(action)
    app = normalize_desktop_app(str(out.get("app") or ""))
    if app:
        out["app"] = app
    want_learn = force_learn if force_learn is not None else supervised_auto_learn_enabled()
    if want_learn and "learn" not in out:
        out["learn"] = True
    elif app in _OFFICE_APPS and "learn" not in out:
        out["learn"] = True
    elif app in _CUSTOM_EXE_APPS and "learn" not in out:
        out["learn"] = True
    cmd = out.get("command")
    if isinstance(cmd, str) and cmd.strip():
        out["command"] = cmd.strip().replace("/", "\\")
    return out


def open_app_action_from_goal(goal: str, *, learn: bool | None = None) -> dict[str, Any] | None:
    """Action desktop complète (``kind`` open_app) dérivée du texte, ou ``None``."""
    inferred = default_desktop_action_from_text(goal)
    if inferred is None:
        return None
    app = normalize_desktop_app(str(inferred.get("app") or ""))
    if not app:
        return None
    act: dict[str, Any] = {
        "kind": "open_app",
        "app": app,
        "args": inferred.get("args") if isinstance(inferred.get("args"), list) else [],
    }
    exe = extract_exe_path_from_goal(goal)
    if exe:
        act["command"] = exe
    return enrich_open_app_action(act, force_learn=learn)


def open_app_args_from_goal(goal: str, *, learn: bool | None = None) -> dict[str, Any] | None:
    """Arguments ``open_app`` (app / learn / args / command) dérivés du texte, ou ``None``."""
    act = open_app_action_from_goal(goal, learn=learn)
    if act is None:
        return None
    out: dict[str, Any] = {
        "app": act["app"],
        "learn": bool(act.get("learn")),
        "args": act.get("args") if isinstance(act.get("args"), list) else [],
    }
    if isinstance(act.get("command"), str) and act["command"].strip():
        out["command"] = act["command"]
    return out


def hint_for_desktop_error(message: str) -> str | None:
    """Conseil actionnable pour un message d'erreur worker (chemin/allowlist/approval)."""
    msg = (message or "").strip()
    if not msg:
        return None
    for pat, hint in _ERROR_HINTS:
        if pat.search(msg):
            return hint
    return None
