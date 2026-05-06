from __future__ import annotations

from typing import Literal

from capabilities.spec import CapabilitySpec
from pydantic import BaseModel, Field


PolicyDecision = Literal["safe_read", "dry_run", "approval_required", "forbidden", "approved_action"]


class ActionPolicyResult(BaseModel):
    decision: PolicyDecision
    allowed: bool
    reason: str
    capability: str
    risk_level: str
    action_kind: str | None = None
    action_context_key: str | None = None
    constraints: list[str] = Field(default_factory=list)


_DEVOPS_SAFE_READ_KINDS = {"http_get", "systemd_is_active", "selfcheck"}
_DEVOPS_APPROVAL_KINDS = {"read_log_tail", "systemd_restart"}
_DESKTOP_KINDS = {
    "open_url",
    "search_web_open",
    "mail_imap_preview",
    "notepad_append",
    "open_app",
    "observe_screen",
    "click_xy",
    "move_xy",
    "drag_xy",
    "type_text",
    "hotkey",
    "scroll",
    "wait_ms",
    "run_steps",
    "comfyui_queue",
    "comfyui_patch_and_queue",
    "comfyui_history",
    "comfyui_view",
}


def evaluate_action_policy(capability: CapabilitySpec, context: dict[str, object]) -> ActionPolicyResult:
    """Décision déterministe avant dispatch agent.

    Les workers restent l'autorité fine pour les allowlists et secrets. Cette couche évite surtout
    qu'une action à risque parte vers un agent sans dry-run ni approbation explicite.
    """
    constraints = [c.name for c in capability.constraints if c.enforceable]
    action_key = capability.action_context_key
    action = context.get(action_key) if action_key else None
    action_kind = _action_kind(action)

    if action_key and action is not None and not isinstance(action, dict):
        return _result(
            capability,
            "forbidden",
            False,
            f"`context.{action_key}` doit être un objet JSON.",
            action_kind=action_kind,
            constraints=constraints,
        )

    if capability.risk_level != "high":
        return _result(
            capability,
            "safe_read",
            True,
            "Capability non classée à haut risque.",
            action_kind=action_kind,
            constraints=constraints,
        )

    if capability.name == "devops_probe":
        return _evaluate_devops(capability, context, action, action_kind, constraints)
    if capability.name == "desktop_control":
        return _evaluate_desktop(capability, context, action, action_kind, constraints)
    if capability.name == "prototype_game":
        return _evaluate_opengame(capability, context, action, action_kind, constraints)

    if _has_any_approval(context):
        return _result(
            capability,
            "approved_action",
            True,
            "Capability à haut risque autorisée par approbation explicite.",
            action_kind=action_kind,
            constraints=constraints,
        )
    return _result(
        capability,
        "approval_required",
        False,
        "Capability à haut risque : approbation explicite requise avant exécution.",
        action_kind=action_kind,
        constraints=constraints,
    )


def _evaluate_devops(
    capability: CapabilitySpec,
    context: dict[str, object],
    action: object,
    action_kind: str | None,
    constraints: list[str],
) -> ActionPolicyResult:
    if action is None:
        return _result(
            capability,
            "safe_read",
            True,
            "Pas d'action DevOps explicite : le handler infère une sonde read-only ou refuse.",
            action_kind=action_kind,
            constraints=constraints,
        )
    if _truthy(context.get("devops_dry_run")):
        return _result(
            capability,
            "dry_run",
            True,
            "Dry-run DevOps explicite.",
            action_kind=action_kind,
            constraints=constraints,
        )
    if action_kind in _DEVOPS_SAFE_READ_KINDS:
        return _result(
            capability,
            "safe_read",
            True,
            "Sonde DevOps read-only ; les allowlists restent vérifiées par l'agent.",
            action_kind=action_kind,
            constraints=constraints,
        )
    if action_kind in _DEVOPS_APPROVAL_KINDS:
        if _non_empty_str(context.get("devops_approval")):
            return _result(
                capability,
                "approved_action",
                True,
                "Action DevOps sensible avec approbation explicite.",
                action_kind=action_kind,
                constraints=constraints,
            )
        return _result(
            capability,
            "approval_required",
            False,
            "Action DevOps sensible : `context.devops_approval` requis ou dry-run.",
            action_kind=action_kind,
            constraints=constraints,
        )
    return _result(
        capability,
        "forbidden",
        False,
        "Action DevOps inconnue ou non autorisée par la policy orchestrateur.",
        action_kind=action_kind,
        constraints=constraints,
    )


def _evaluate_desktop(
    capability: CapabilitySpec,
    context: dict[str, object],
    action: object,
    action_kind: str | None,
    constraints: list[str],
) -> ActionPolicyResult:
    if action is None:
        return _result(
            capability,
            "forbidden",
            False,
            "`context.desktop_action` est requis pour toute action poste.",
            action_kind=action_kind,
            constraints=constraints,
        )
    if action_kind not in _DESKTOP_KINDS:
        return _result(
            capability,
            "forbidden",
            False,
            "Action desktop inconnue ou non autorisée par la policy orchestrateur.",
            action_kind=action_kind,
            constraints=constraints,
        )
    if _truthy(context.get("desktop_dry_run")):
        return _result(
            capability,
            "dry_run",
            True,
            "Dry-run desktop explicite.",
            action_kind=action_kind,
            constraints=constraints,
        )
    if _non_empty_str(context.get("desktop_approval")):
        return _result(
            capability,
            "approved_action",
            True,
            "Action desktop réelle avec approbation explicite.",
            action_kind=action_kind,
            constraints=constraints,
        )
    return _result(
        capability,
        "approval_required",
        False,
        "Action desktop réelle : `context.desktop_approval` requis ou dry-run.",
        action_kind=action_kind,
        constraints=constraints,
    )


def _evaluate_opengame(
    capability: CapabilitySpec,
    context: dict[str, object],
    action: object,
    action_kind: str | None,
    constraints: list[str],
) -> ActionPolicyResult:
    if action is None:
        return _result(
            capability,
            "forbidden",
            False,
            "`context.opengame_action` est requis pour la forge OpenGame.",
            action_kind=action_kind,
            constraints=constraints,
        )
    if _truthy(context.get("opengame_dry_run")) or context.get("opengame_dry_run") is not False:
        return _result(
            capability,
            "dry_run",
            True,
            "Forge OpenGame considérée en dry-run tant qu'un opt-in réel n'est pas explicite.",
            action_kind=action_kind,
            constraints=constraints,
        )
    if _non_empty_str(context.get("opengame_approval")):
        return _result(
            capability,
            "approved_action",
            True,
            "Forge OpenGame réelle avec approbation explicite.",
            action_kind=action_kind,
            constraints=constraints,
        )
    return _result(
        capability,
        "approval_required",
        False,
        "Forge OpenGame réelle : `context.opengame_approval` requis ou dry-run.",
        action_kind=action_kind,
        constraints=constraints,
    )


def _result(
    capability: CapabilitySpec,
    decision: PolicyDecision,
    allowed: bool,
    reason: str,
    *,
    action_kind: str | None,
    constraints: list[str],
) -> ActionPolicyResult:
    return ActionPolicyResult(
        decision=decision,
        allowed=allowed,
        reason=reason,
        capability=capability.name,
        risk_level=capability.risk_level,
        action_kind=action_kind,
        action_context_key=capability.action_context_key,
        constraints=constraints,
    )


def _action_kind(action: object) -> str | None:
    if not isinstance(action, dict):
        return None
    raw = action.get("kind")
    if not isinstance(raw, str):
        return None
    kind = raw.strip()
    return kind or None


def _truthy(value: object) -> bool:
    if value is True:
        return True
    if not isinstance(value, str):
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _non_empty_str(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _has_any_approval(context: dict[str, object]) -> bool:
    return any(_non_empty_str(context.get(k)) for k in ("desktop_approval", "devops_approval", "opengame_approval"))
