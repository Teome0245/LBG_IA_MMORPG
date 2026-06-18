"""Remédiation assistée (rapatrié de LBG_Project_03) : selfcheck → plan → apply → validate.

Aucune commande shell libre : les actions « apply » repassent par ``devops_executor`` (allowlist,
dry-run, approbation). Le plan est purement consultatif ; rien n'est exécuté sans ``apply`` explicite.
Les unités à redémarrer restent bornées par ``LBG_DEVOPS_SYSTEMD_RESTART_ALLOWLIST`` côté exécuteur.
"""

from __future__ import annotations

import re
from typing import Any

from lbg_agents.infra_memory_remediation import (
    build_memory_remediation_plan,
    format_memory_plan_reply,
)


def _suggest_from_step(step: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if step.get("healthy") is True:
        return out
    kind = step.get("kind")
    res = step.get("result") if isinstance(step.get("result"), dict) else {}
    if kind == "systemd_is_active":
        unit = str(step.get("unit") or res.get("unit") or "").strip()
        if unit.endswith(".service"):
            out.append(
                {
                    "level": "safe",
                    "label": f"Redémarrer {unit} (allowlist restart + approbation)",
                    "devops_action": {"kind": "systemd_restart", "unit": unit},
                    "requires_approval": True,
                }
            )
            out.append(
                {
                    "level": "manual",
                    "label": f"Diagnostic manuel : journalctl -u {unit} -n 80",
                    "command_hint": f"journalctl -u {unit} -n 80 --no-pager",
                }
            )
    elif kind == "http_get":
        url = str(step.get("url") or res.get("url") or "").strip()
        if url:
            out.append(
                {
                    "level": "safe",
                    "label": f"Re-sonder HTTP {url}",
                    "devops_action": {"kind": "http_get", "url": url},
                    "requires_approval": False,
                }
            )
    return out


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for it in items:
        key = str(it.get("devops_action")) + "|" + str(it.get("command_hint"))
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def build_plan_from_selfcheck(selfcheck_out: dict[str, Any]) -> dict[str, Any]:
    res = selfcheck_out.get("result") if isinstance(selfcheck_out.get("result"), dict) else {}
    steps = res.get("steps") if isinstance(res.get("steps"), list) else []
    hints = res.get("remediation_hints") if isinstance(res.get("remediation_hints"), list) else []
    suggestions: list[dict[str, Any]] = []
    for s in steps:
        if isinstance(s, dict):
            suggestions.extend(_suggest_from_step(s))
    suggestions = _dedupe(suggestions)
    return {
        "kind": "remediation_plan",
        "selfcheck_ok": bool(res.get("ok")),
        "selfcheck_dry_run": bool(res.get("dry_run")),
        "hints": hints,
        "suggested_actions": suggestions,
        "next_steps": [
            "Choisir une action « safe » et relancer en remediation_apply avec devops_approval (hors dry-run).",
            "Relancer en remediation_validate après apply pour confirmer le retour à la normale.",
        ],
    }


def _format_plan_reply(plan: dict[str, Any]) -> str:
    lines = [
        "Plan de remédiation (suggestions — rien n'est exécuté sans apply explicite)",
        f"Selfcheck : {'OK' if plan.get('selfcheck_ok') else 'KO'}"
        + (" (dry-run)" if plan.get("selfcheck_dry_run") else ""),
    ]
    for h in (plan.get("hints") or [])[:6]:
        if isinstance(h, str) and h.strip():
            lines.append(f"  → {h.strip()}")
    actions = plan.get("suggested_actions") or []
    if actions:
        lines.append("Actions proposées :")
        for i, a in enumerate(actions[:8], 1):
            if isinstance(a, dict):
                lines.append(f"  {i}. [{a.get('level', '?')}] {a.get('label', '?')}")
    else:
        lines.append("Aucune action automatique proposée — voir hints ou diagnostic manuel.")
    return "\n".join(lines)


def run_remediation(
    *,
    actor_id: str,
    text: str,
    action: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    """Orchestrateur de remédiation. ``action.step`` ∈ {plan, apply, validate}."""
    # Import tardif : évite une dépendance circulaire avec devops_executor.
    from lbg_agents.devops_executor import is_devops_dry_run, run_devops_action

    step = str(action.get("step") or action.get("kind") or "plan").strip().lower()
    if step in ("remediation_plan", "remediation_apply", "remediation_validate"):
        step = step.replace("remediation_", "")

    if step == "plan":
        if action.get("source") == "memory" or action.get("step") == "plan_memory":
            from lbg_agents.infra_watchdog import run_infra_watchdog

            wd = run_infra_watchdog(actor_id=actor_id, persist=False)
            plan = build_memory_remediation_plan(wd)
            return {
                "agent": "remediation",
                "handler": "devops",
                "actor_id": actor_id,
                "request_text": text,
                "remediation_action": action,
                "watchdog": wd,
                "result": plan,
                "ok": True,
                "reply": format_memory_plan_reply(plan),
                "remediation_hints": plan.get("hints") or [],
                "meta": {"read_only": True, "source": "infra_memory"},
            }
        sc_ctx = {**context, "devops_action": {"kind": "selfcheck"}}
        sc_ctx.setdefault("devops_dry_run", context.get("devops_dry_run", True))
        sc = run_devops_action(actor_id=actor_id, text=text, action={"kind": "selfcheck"}, context=sc_ctx)
        plan = build_plan_from_selfcheck(sc)
        return {
            "agent": "remediation",
            "handler": "devops",
            "actor_id": actor_id,
            "request_text": text,
            "remediation_action": action,
            "selfcheck": sc,
            "result": plan,
            "ok": True,
            "reply": _format_plan_reply(plan),
            "remediation_hints": plan.get("hints") or [],
            "meta": {"read_only": True},
        }

    if step == "apply":
        devops_action = action.get("devops_action") or context.get("devops_action")
        if not isinstance(devops_action, dict):
            return {
                "agent": "remediation",
                "handler": "devops",
                "actor_id": actor_id,
                "ok": False,
                "error": "apply requiert remediation_action.devops_action (ou context.devops_action).",
                "reply": "Remédiation apply : action DevOps manquante.",
            }
        if not is_devops_dry_run(context) and not context.get("devops_approval"):
            return {
                "agent": "remediation",
                "handler": "devops",
                "actor_id": actor_id,
                "ok": False,
                "outcome": "approval_required",
                "error": "devops_approval requis pour apply hors dry-run.",
                "reply": "Remédiation : renseigner devops_approval (ou activer le dry-run).",
            }
        applied = run_devops_action(actor_id=actor_id, text=text, action=devops_action, context=context)
        ok = not applied.get("error")
        res = applied.get("result")
        if isinstance(res, dict) and res.get("ok") is False:
            ok = False
        return {
            "agent": "remediation",
            "handler": "devops",
            "actor_id": actor_id,
            "remediation_action": action,
            "applied": applied,
            "ok": ok,
            "result": {"kind": "remediation_apply", "ok": ok},
            "reply": f"Apply {devops_action.get('kind')} — {'OK' if ok else 'échec'}",
            "meta": {"dry_run": is_devops_dry_run(context)},
        }

    if step in ("validate", "validation"):
        sc_ctx = {**context, "devops_dry_run": False}
        sc = run_devops_action(actor_id=actor_id, text=text, action={"kind": "selfcheck"}, context=sc_ctx)
        res = sc.get("result") if isinstance(sc.get("result"), dict) else {}
        ok = bool(res.get("ok"))
        return {
            "agent": "remediation",
            "handler": "devops",
            "actor_id": actor_id,
            "remediation_action": action,
            "selfcheck": sc,
            "ok": ok,
            "result": {"kind": "remediation_validate", "ok": ok},
            "reply": f"Validation selfcheck — {'OK' if ok else 'KO'}",
            "remediation_hints": res.get("remediation_hints") or [],
        }

    return {
        "agent": "remediation",
        "handler": "devops",
        "actor_id": actor_id,
        "ok": False,
        "error": f"step inconnu: {step!r} (attendu plan | apply | validate).",
        "reply": "Remédiation : step inconnu.",
    }


def default_remediation_action_from_text(text: str) -> dict[str, Any] | None:
    t = (text or "").strip().lower()
    if not re.search(r"\b(remediat|remédiation|remediation|corrige|corriger|fix ops|plan ops)\b", t):
        return None
    if re.search(r"\b(apply|appliquer|execut|exécut)\b", t):
        return {"step": "apply"}
    if re.search(r"\b(valid|vérif|verif)", t):
        return {"step": "validate"}
    return {"step": "plan"}
