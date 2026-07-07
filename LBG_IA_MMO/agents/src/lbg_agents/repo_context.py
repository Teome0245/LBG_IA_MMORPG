"""Contexte codebase léger pour l'assistant PM (style copilote Cursor)."""

from __future__ import annotations

import os
import pathlib
import re
import subprocess
from typing import Any

from lbg_agents.pm_stub import _read_plan_text

_SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        "dist",
        "build",
        ".cursor",
        "pilot_web",
    }
)
_KEY_FILES = (
    "README.md",
    "CLAUDE.md",
    "docs/plan_de_route.md",
    "docs/ui_refactor_plan.md",
    "AGENTS.md",
)
_MAX_GREP_HITS = 20
_MAX_FILE_BYTES = 250_000


def resolve_repo_root() -> pathlib.Path | None:
    raw = os.environ.get("LBG_REPO_ROOT", "").strip()
    if raw:
        p = pathlib.Path(raw)
        if p.is_dir():
            return p.resolve()
    plan = os.environ.get("LBG_PM_PLAN_PATH", "").strip()
    if plan:
        parent = pathlib.Path(plan).resolve().parent.parent
        if parent.is_dir() and (parent / "pilot_shell").is_dir():
            return parent
    for candidate in (
        pathlib.Path.cwd(),
        pathlib.Path(__file__).resolve().parents[3],
        pathlib.Path("/opt/LBG_IA_MMO"),
    ):
        if (candidate / "docs" / "plan_de_route.md").is_file():
            return candidate.resolve()
        if (candidate / "pilot_shell").is_dir():
            return candidate.resolve()
    return None


def build_tree_summary(*, max_depth: int = 2, max_lines: int = 60) -> str:
    root = resolve_repo_root()
    if root is None:
        return "(Arbre repo indisponible — définir LBG_REPO_ROOT.)"
    lines: list[str] = [f"Racine : {root}", ""]
    count = 0

    def walk(dir_path: pathlib.Path, depth: int, prefix: str) -> None:
        nonlocal count
        if depth > max_depth or count >= max_lines:
            return
        try:
            entries = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            return
        for entry in entries:
            if count >= max_lines:
                return
            if entry.name in _SKIP_DIRS or entry.name.startswith("."):
                continue
            rel = entry.relative_to(root)
            if entry.is_dir():
                lines.append(f"{prefix}{rel}/")
                count += 1
                walk(entry, depth + 1, prefix)
            else:
                if entry.suffix in (".py", ".ts", ".tsx", ".md", ".json", ".yaml", ".yml", ".sh"):
                    lines.append(f"{prefix}{rel}")
                    count += 1

    walk(root, 0, "")
    return "\n".join(lines)


def _read_key_snippets() -> str:
    root = resolve_repo_root()
    if root is None:
        return ""
    parts: list[str] = []
    for name in _KEY_FILES:
        path = root / name
        if not path.is_file():
            continue
        try:
            data = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        snippet = data[:2500].strip()
        if snippet:
            parts.append(f"### {name}\n{snippet}")
    return "\n\n".join(parts)


def grep_repo(pattern: str, *, max_hits: int = _MAX_GREP_HITS) -> list[dict[str, Any]]:
    """Recherche texte dans le repo (rg si dispo, sinon scan Python)."""
    root = resolve_repo_root()
    if root is None:
        return [{"ok": False, "error": "repo_root introuvable"}]
    pat = (pattern or "").strip()
    if not pat or len(pat) > 200:
        return [{"ok": False, "error": "pattern vide ou trop long"}]

    rg = subprocess.run(
        [
            "rg",
            "-n",
            "--max-count",
            str(max_hits),
            "--glob",
            "!node_modules/**",
            "--glob",
            "!.git/**",
            "--glob",
            "!pilot_web/**",
            pat,
            str(root),
        ],
        capture_output=True,
        text=True,
        timeout=12,
    )
    if rg.returncode in (0, 1):
        hits: list[dict[str, Any]] = []
        for line in (rg.stdout or "").splitlines()[:max_hits]:
            m = re.match(r"^(.+?):(\d+):(.*)$", line)
            if not m:
                continue
            file_path, line_no, content = m.group(1), m.group(2), m.group(3)
            try:
                rel = str(pathlib.Path(file_path).resolve().relative_to(root))
            except ValueError:
                rel = file_path
            hits.append(
                {
                    "ok": True,
                    "file": rel,
                    "line": int(line_no),
                    "content": content.strip()[:240],
                }
            )
        return hits or [{"ok": True, "file": "", "line": 0, "content": "(aucune occurrence)"}]

    # Repli Python
    try:
        rx = re.compile(pat, re.IGNORECASE)
    except re.error as e:
        return [{"ok": False, "error": f"regex invalide : {e}"}]

    hits_py: list[dict[str, Any]] = []
    for path in root.rglob("*"):
        if len(hits_py) >= max_hits:
            break
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.suffix not in (".py", ".ts", ".tsx", ".md", ".json", ".yaml", ".yml", ".sh", ".toml"):
            continue
        try:
            if path.stat().st_size > _MAX_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = str(path.relative_to(root))
        for i, line in enumerate(text.splitlines(), start=1):
            if rx.search(line):
                hits_py.append({"ok": True, "file": rel, "line": i, "content": line.strip()[:240]})
                if len(hits_py) >= max_hits:
                    break
    return hits_py or [{"ok": True, "file": "", "line": 0, "content": "(aucune occurrence)"}]


def repo_context_block(*, user_text: str = "") -> str:
    """Bloc prompt : arbre + extraits clés + grep optionnel sur mots du message."""
    parts = [
        "## Contexte codebase (lecture seule)",
        "",
        build_tree_summary(),
    ]
    snippets = _read_key_snippets()
    if snippets:
        parts.extend(["", "## Extraits documentation", "", snippets])

    keywords = _keywords_from_text(user_text)
    if keywords:
        parts.extend(["", "## Grep automatique (mots-clés utilisateur)"])
        for kw in keywords[:3]:
            hits = grep_repo(kw, max_hits=8)
            parts.append(f"\n`{kw}` :")
            for h in hits[:8]:
                if h.get("file"):
                    parts.append(f"- {h['file']}:{h.get('line', '?')} — {h.get('content', '')[:120]}")
    return "\n".join(parts)[:18000]


def _keywords_from_text(text: str) -> list[str]:
    t = (text or "").strip().lower()
    if not t:
        return []
    found: list[str] = []
    for m in re.finditer(r"\b(pilot_chat|core3|orchestrator|pilot_shell|plan_de_route|assistant/chat)\b", t, re.I):
        found.append(m.group(0))
    for m in re.finditer(r"\b(linux-\d{2,3}|core3|devops|mmo)\b", t, re.I):
        w = m.group(0)
        if w not in found:
            found.append(w)
    if re.search(r"\b(où|ou|cherche|grep|fichier|code)\b", t):
        for m in re.finditer(r"`([^`]{3,40})`", text):
            found.append(m.group(1))
    return found[:5]
