"""
Exécuteur OpenGame — forge de prototypes orchestrée.

L'agent valide une demande de génération, résout une cible dans une sandbox,
produit un plan et audite l'appel. L'exécution réelle de la CLI OpenGame reste
désactivée par défaut et exige des garde-fous explicites.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_PROJECT_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")


def _truthy(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def opengame_dry_run(context: dict[str, Any] | None = None) -> bool:
    """
    Dry-run par défaut.

    `LBG_OPENGAME_DRY_RUN=0` permet de demander une exécution réelle plus tard,
    mais le squelette actuel refuse encore l'exécution effective.
    """
    env = os.environ.get("LBG_OPENGAME_DRY_RUN", "").strip()
    if env:
        return _truthy(env)
    if isinstance(context, dict) and context.get("opengame_dry_run") is False:
        return False
    return True


def opengame_execution_enabled() -> bool:
    return _truthy(os.environ.get("LBG_OPENGAME_EXECUTION_ENABLED", "0"))


def _opengame_bin() -> str:
    return os.environ.get("LBG_OPENGAME_BIN", "opengame").strip() or "opengame"


def _timeout_s() -> int:
    raw = os.environ.get("LBG_OPENGAME_TIMEOUT_S", "900").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 900
    return max(30, min(n, 7200))


def _max_output_chars() -> int:
    raw = os.environ.get("LBG_OPENGAME_MAX_OUTPUT_CHARS", "12000").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 12000
    return max(1000, min(n, 100000))


def opengame_requires_approval() -> bool:
    return bool(os.environ.get("LBG_OPENGAME_APPROVAL_TOKEN", "").strip())


def opengame_approval_ok(context: dict[str, Any] | None = None) -> bool:
    token = os.environ.get("LBG_OPENGAME_APPROVAL_TOKEN", "").strip()
    if not token:
        return True
    if not isinstance(context, dict):
        return False
    got = context.get("opengame_approval")
    if not isinstance(got, str):
        return False
    return secrets.compare_digest(got, token)


def _sandbox_root() -> Path:
    raw = os.environ.get("LBG_OPENGAME_SANDBOX_DIR", "").strip()
    if not raw:
        raw = "generated_games/opengame"
    return Path(raw).expanduser().resolve()


def _safe_project_name(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    name = raw.strip()
    if not _PROJECT_NAME_RE.fullmatch(name):
        return None
    if ".." in name:
        return None
    return name


def _target_dir(sandbox: Path, project_name: str) -> Path | None:
    target = (sandbox / project_name).resolve()
    try:
        target.relative_to(sandbox)
    except ValueError:
        return None
    return target


def _audit_write(line: dict[str, Any]) -> None:
    line = dict(line)
    line["ts"] = datetime.now(timezone.utc).isoformat()
    raw = json.dumps(line, ensure_ascii=False)

    if _truthy(os.environ.get("LBG_OPENGAME_AUDIT_STDOUT", "1")):
        print(raw)

    path = os.environ.get("LBG_OPENGAME_AUDIT_LOG_PATH", "").strip()
    if not path:
        return
    try:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.open("a", encoding="utf-8").write(raw + "\n")
    except Exception as e:
        print(
            json.dumps(
                {"event": "agents.opengame.audit_file_error", "error": f"{type(e).__name__}: {e}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )


def _prompt_preview(prompt: str) -> str:
    return prompt if len(prompt) <= 160 else prompt[:157] + "..."


def _clip_output(raw: str | bytes | None) -> str:
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        text = raw.decode("utf-8", errors="replace")
    else:
        text = raw
    limit = _max_output_chars()
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated {len(text) - limit} chars]"


def _dir_has_entries(path: Path) -> bool:
    try:
        next(path.iterdir())
    except StopIteration:
        return False
    except FileNotFoundError:
        return False
    return True


def _base(
    *,
    actor_id: str,
    text: str,
    kind: str,
    context: dict[str, Any],
    dry_run: bool,
) -> dict[str, Any]:
    return {
        "agent": "opengame_executor",
        "handler": "opengame",
        "actor_id": actor_id,
        "request_text": text,
        "kind": kind,
        "meta": {
            "dry_run": dry_run,
            "execution_enabled": opengame_execution_enabled(),
            "approval_gate_active": opengame_requires_approval(),
            "adr": "docs/adr/0003-opengame-forge-prototypes.md",
        },
    }


def run_opengame_action(
    *,
    actor_id: str,
    text: str,
    action: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    trace_id = context.get("_trace_id") if isinstance(context.get("_trace_id"), str) else None
    kind = str(action.get("kind") or "").strip()
    dry_run = opengame_dry_run(context)
    base = _base(actor_id=actor_id, text=text, kind=kind, context=context, dry_run=dry_run)

    def finish(out: dict[str, Any], *, outcome: str) -> dict[str, Any]:
        _audit_write(
            {
                "event": "agents.opengame.audit",
                "trace_id": trace_id,
                "agent": "opengame_executor",
                "capability": "prototype_game",
                "action_kind": kind,
                "outcome": outcome,
                "dry_run": dry_run,
                "execution_enabled": opengame_execution_enabled(),
                "approval_gate_active": opengame_requires_approval(),
                "project_name": out.get("project_name"),
                "sandbox_dir": out.get("sandbox_dir"),
                "target_dir": out.get("target_dir"),
            }
        )
        return out

    if kind != "generate_prototype":
        return finish(
            {
                **base,
                "ok": False,
                "outcome": "bad_request",
                "error": "Action OpenGame inconnue ou absente.",
                "hint": 'Ex. {"opengame_action":{"kind":"generate_prototype","project_name":"snake","prompt":"Build a Snake clone"}}',
            },
            outcome="bad_request",
        )

    prompt = action.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        prompt = text
    prompt = prompt.strip()
    if not prompt:
        return finish(
            {**base, "ok": False, "outcome": "bad_request", "error": "Prompt requis pour OpenGame."},
            outcome="bad_request",
        )
    if len(prompt) > 4000:
        return finish(
            {**base, "ok": False, "outcome": "bad_request", "error": "Prompt trop long (max 4000 caractères)."},
            outcome="bad_request",
        )

    project_name = _safe_project_name(action.get("project_name"))
    if project_name is None:
        return finish(
            {
                **base,
                "ok": False,
                "outcome": "bad_request",
                "error": "project_name requis, stable, sans chemin, max 64 caractères.",
            },
            outcome="bad_request",
        )

    sandbox = _sandbox_root()
    target = _target_dir(sandbox, project_name)
    if target is None:
        return finish(
            {**base, "ok": False, "outcome": "sandbox_denied", "error": "Cible hors sandbox OpenGame."},
            outcome="sandbox_denied",
        )

    opengame_bin = _opengame_bin()
    planned_command = [opengame_bin, "-p", "<prompt>", "--approval-mode", "auto-edit"]
    planned = {
        "tool": "opengame",
        "command": planned_command,
        "cwd": str(target),
        "prompt_preview": _prompt_preview(prompt),
        "timeout_s": _timeout_s(),
        "notes": [
            "La CLI OpenGame est lancée uniquement si dry-run=0 et LBG_OPENGAME_EXECUTION_ENABLED=1.",
            "Le mode --yolo n'est pas utilisé par cet agent.",
            "Le code généré devra rester dans la sandbox et être promu manuellement.",
        ],
    }

    if dry_run:
        return finish(
            {
                **base,
                "ok": True,
                "outcome": "dry_run",
                "project_name": project_name,
                "sandbox_dir": str(sandbox),
                "target_dir": str(target),
                "planned": planned,
            },
            outcome="dry_run_planned",
        )

    if not opengame_execution_enabled():
        return finish(
            {
                **base,
                "ok": False,
                "outcome": "execution_disabled",
                "error": "Exécution OpenGame désactivée (LBG_OPENGAME_EXECUTION_ENABLED=1 requis).",
                "project_name": project_name,
                "sandbox_dir": str(sandbox),
                "target_dir": str(target),
                "planned": planned,
            },
            outcome="execution_disabled",
        )

    if opengame_requires_approval() and not opengame_approval_ok(context):
        return finish(
            {
                **base,
                "ok": False,
                "outcome": "approval_denied",
                "error": "Approval token requis (context.opengame_approval).",
                "project_name": project_name,
                "sandbox_dir": str(sandbox),
                "target_dir": str(target),
                "planned": planned,
            },
            outcome="approval_denied",
        )

    resolved_bin = shutil.which(opengame_bin)
    if not resolved_bin:
        return finish(
            {
                **base,
                "ok": False,
                "outcome": "tool_missing",
                "error": f"CLI OpenGame introuvable sur PATH ({opengame_bin!r}).",
                "project_name": project_name,
                "sandbox_dir": str(sandbox),
                "target_dir": str(target),
                "planned": planned,
            },
            outcome="tool_missing",
        )

    try:
        sandbox.mkdir(parents=True, exist_ok=True)
        if target.exists() and _dir_has_entries(target):
            return finish(
                {
                    **base,
                    "ok": False,
                    "outcome": "target_not_empty",
                    "error": "Le dossier cible existe déjà et n'est pas vide ; nettoyage ou nouveau project_name requis.",
                    "project_name": project_name,
                    "sandbox_dir": str(sandbox),
                    "target_dir": str(target),
                    "planned": planned,
                },
                outcome="target_not_empty",
            )
        target.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return finish(
            {
                **base,
                "ok": False,
                "outcome": "sandbox_error",
                "error": f"{type(e).__name__}: {e}",
                "project_name": project_name,
                "sandbox_dir": str(sandbox),
                "target_dir": str(target),
                "planned": planned,
            },
            outcome="sandbox_error",
        )

    command = [resolved_bin, "-p", prompt, "--approval-mode", "auto-edit"]
    try:
        completed = subprocess.run(
            command,
            cwd=str(target),
            text=True,
            capture_output=True,
            timeout=_timeout_s(),
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        return finish(
            {
                **base,
                "ok": False,
                "outcome": "timeout",
                "error": f"OpenGame timeout après {_timeout_s()}s.",
                "project_name": project_name,
                "sandbox_dir": str(sandbox),
                "target_dir": str(target),
                "planned": planned,
                "stdout_preview": _clip_output(e.stdout),
                "stderr_preview": _clip_output(e.stderr),
            },
            outcome="timeout",
        )
    except Exception as e:
        return finish(
            {
                **base,
                "ok": False,
                "outcome": "execution_error",
                "error": f"{type(e).__name__}: {e}",
                "project_name": project_name,
                "sandbox_dir": str(sandbox),
                "target_dir": str(target),
                "planned": planned,
            },
            outcome="execution_error",
        )

    ok = completed.returncode == 0
    return finish(
        {
            **base,
            "ok": ok,
            "outcome": "success" if ok else "command_failed",
            "project_name": project_name,
            "sandbox_dir": str(sandbox),
            "target_dir": str(target),
            "planned": planned,
            "returncode": completed.returncode,
            "stdout_preview": _clip_output(completed.stdout),
            "stderr_preview": _clip_output(completed.stderr),
        },
        outcome="success" if ok else "command_failed",
    )
