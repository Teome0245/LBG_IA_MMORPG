import json
import os
import time
from fastapi import APIRouter
from pydantic import BaseModel, Field
from lbg_agents.dispatch import invoke_after_route

from introspection.deterministic_classifier import DeterministicIntentClassifier
from introspection.llm_intent_classifier import hybrid_classify
from services import metrics as svc_metrics
from shared_registry import capability_registry

router = APIRouter()


class RouteRequest(BaseModel):
    actor_id: str
    text: str = Field(..., min_length=1)
    context: dict[str, object] = Field(default_factory=dict)


class RouteResponse(BaseModel):
    intent: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    routed_to: str
    output: dict[str, object] = Field(default_factory=dict)


_classifier = DeterministicIntentClassifier()


def _dialogue_context_for_route(context: dict[str, object]) -> dict[str, object]:
    """Ajoute les préférences LLM décidées par l'orchestrateur, sans écraser un choix explicite."""
    ctx = dict(context)
    if not isinstance(ctx.get("dialogue_target"), str) or not str(ctx.get("dialogue_target")).strip():
        target = os.environ.get("LBG_ORCHESTRATOR_DIALOGUE_TARGET_DEFAULT", "fast").strip().lower()
        if target not in ("local", "remote", "fast", "auto"):
            target = "fast"
        ctx["dialogue_target"] = target
    if not isinstance(ctx.get("dialogue_profile"), str) or not str(ctx.get("dialogue_profile")).strip():
        profile = os.environ.get("LBG_ORCHESTRATOR_DIALOGUE_PROFILE_DEFAULT", "").strip()
        if profile:
            ctx["dialogue_profile"] = profile
    return ctx


@router.post("/route", response_model=RouteResponse)
def route_intent(payload: RouteRequest) -> RouteResponse:
    t0 = time.perf_counter()
    svc_metrics.inc("orchestrator_route_requests_total")
    ctx = payload.context if isinstance(payload.context, dict) else {}
    npc_name = ctx.get("npc_name")
    trace_id = ctx.get("_trace_id")
    trace_id = trace_id if isinstance(trace_id, str) and trace_id.strip() else None

    route_meta: dict[str, object] = {}

    # Sonde DevOps : priorité absolue (valider le fil de transmission même avec npc_name / autre bruit).
    if isinstance(ctx.get("devops_action"), dict):
        intent, confidence = ("devops_probe", 1.0)
    # Desktop (hybride) : priorité explicite via action structurée (évite les faux positifs).
    elif isinstance(ctx.get("desktop_action"), dict):
        intent, confidence = ("desktop_control", 1.0)
    # OpenGame : génération de prototype uniquement via action structurée et sandboxée.
    elif isinstance(ctx.get("opengame_action"), dict):
        intent, confidence = ("prototype_game", 1.0)
    # Chef de projet : priorité explicite (payload ou drapeau).
    elif ctx.get("pm_focus") is True or isinstance(ctx.get("project_pm"), dict):
        intent, confidence = ("project_pm", 1.0)
    # Gameplay monde (v1) : commit aid déterministe
    elif isinstance(ctx.get("world_action"), dict):
        intent, confidence = ("world_aid", 1.0)
    # Action monde demandée via dialogue PNJ : garder le flux LLM dialogue même si le texte parle de quête.
    elif (
        isinstance(ctx.get("world_npc_id"), str)
        and str(ctx.get("world_npc_id")).strip()
        and isinstance(ctx.get("_world_action_kind"), str)
        and str(ctx.get("_world_action_kind")).strip().lower() in ("aid", "quest")
    ):
        intent, confidence = ("npc_dialogue", 1.0)
    else:
        # Priorité : si le texte exprime clairement une quête/mission/etc., respecter le classifieur
        # même si un PNJ est ciblé (ex: une quête donnée par un PNJ).
        intent, confidence, route_meta = hybrid_classify(payload.text, ctx, _classifier.classify)

        # Règle produit : si un NPC est explicitement ciblé côté client, forcer le dialogue
        # uniquement quand le texte n'a pas déjà déclenché une autre intention "métier".
        if intent == "unknown" and isinstance(npc_name, str) and npc_name.strip():
            intent, confidence = ("npc_dialogue", 0.9)
    cap = capability_registry.get(intent) or capability_registry.get("unknown")
    assert cap is not None
    ctx_for_agent = _dialogue_context_for_route(ctx) if cap.routed_to == "agent.dialogue" else payload.context
    try:
        agent_out = invoke_after_route(
            cap.routed_to,
            actor_id=payload.actor_id,
            text=payload.text,
            context=ctx_for_agent,
        )
    except Exception:
        svc_metrics.inc("orchestrator_route_errors_total")
        raise
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    svc_metrics.inc("orchestrator_route_success_total")
    out_body: dict[str, object] = {"capability": cap.name, **agent_out}
    if route_meta:
        out_body["orchestrator_route_meta"] = route_meta
    print(
        json.dumps(
            {
                "event": "orchestrator.route",
                "trace_id": trace_id,
                "actor_id": payload.actor_id,
                "intent": intent,
                "confidence": confidence,
                "routed_to": cap.routed_to,
                "elapsed_ms": elapsed_ms,
                "intent_source": route_meta.get("intent_source") if route_meta else None,
            },
            ensure_ascii=False,
        )
    )
    return RouteResponse(
        intent=intent,
        confidence=confidence,
        routed_to=cap.routed_to,
        output=out_body,
    )

