import json
import os
import time
from fastapi import APIRouter
from pydantic import BaseModel, Field
from lbg_agents.dispatch import invoke_after_route

from introspection.deterministic_classifier import DeterministicIntentClassifier
from introspection.llm_intent_classifier import hybrid_classify
from services.action_policy import evaluate_action_policy
from services import metrics as svc_metrics
from services import proactive as svc_proactive
from shared_registry import capability_registry
from router.agentic import elevate_to_job, should_elevate_to_agentic

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
    # Core3 Prime : bot joueur / PNJ pilotes (sidecar 245)
    elif isinstance(ctx.get("core3_action"), dict):
        intent, confidence = ("core3_bot_action", 1.0)
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
    policy = evaluate_action_policy(cap, ctx)
    if not policy.allowed:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        svc_metrics.inc("orchestrator_route_success_total")
        out_body: dict[str, object] = {
            "capability": cap.name,
            "ok": False,
            "outcome": policy.decision,
            "error": policy.reason,
            "policy": policy.model_dump(),
        }
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
                    "policy_decision": policy.decision,
                    "policy_allowed": policy.allowed,
                },
                ensure_ascii=False,
            )
        )
        svc_proactive.enrich_route_output(
            actor_id=payload.actor_id,
            text=payload.text,
            intent=intent,
            context=ctx,
            out_body=out_body,
        )
        return RouteResponse(intent=intent, confidence=confidence, routed_to=cap.routed_to, output=out_body)
    # Élévation agentique : si activée et intent actionnable, on délègue au moteur de jobs
    # (planification + exécution de fond + auto-correction) au lieu d'un dispatch one-shot.
    if should_elevate_to_agentic(intent, ctx):
        try:
            agentic_out = elevate_to_job(
                text=payload.text,
                actor_id=payload.actor_id,
                intent=intent,
                context=dict(ctx_for_agent),
            )
        except Exception:
            svc_metrics.inc("orchestrator_route_errors_total")
            raise
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        svc_metrics.inc("orchestrator_route_success_total")
        svc_metrics.inc("orchestrator_route_agentic_total")
        out_body = {"capability": cap.name, "policy": policy.model_dump(), **agentic_out}
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
                    "agentic": True,
                    "job_id": agentic_out.get("job_id"),
                    "policy_decision": policy.decision,
                    "policy_allowed": policy.allowed,
                },
                ensure_ascii=False,
            )
        )
        svc_proactive.enrich_route_output(
            actor_id=payload.actor_id,
            text=payload.text,
            intent=intent,
            context=ctx,
            out_body=out_body,
        )
        return RouteResponse(intent=intent, confidence=confidence, routed_to=cap.routed_to, output=out_body)

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
    out_body: dict[str, object] = {"capability": cap.name, "policy": policy.model_dump(), **agent_out}
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
                "policy_decision": policy.decision,
                "policy_allowed": policy.allowed,
            },
            ensure_ascii=False,
        )
    )
    svc_proactive.enrich_route_output(
        actor_id=payload.actor_id,
        text=payload.text,
        intent=intent,
        context=ctx,
        out_body=out_body,
    )
    return RouteResponse(
        intent=intent,
        confidence=confidence,
        routed_to=cap.routed_to,
        output=out_body,
    )

