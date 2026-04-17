import json
import time
from fastapi import APIRouter
from pydantic import BaseModel, Field
from lbg_agents.dispatch import invoke_after_route

from introspection.deterministic_classifier import DeterministicIntentClassifier
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


@router.post("/route", response_model=RouteResponse)
def route_intent(payload: RouteRequest) -> RouteResponse:
    t0 = time.perf_counter()
    ctx = payload.context if isinstance(payload.context, dict) else {}
    npc_name = ctx.get("npc_name")
    trace_id = ctx.get("_trace_id")
    trace_id = trace_id if isinstance(trace_id, str) and trace_id.strip() else None

    # Sonde DevOps : priorité absolue (valider le fil de transmission même avec npc_name / autre bruit).
    if isinstance(ctx.get("devops_action"), dict):
        intent, confidence = ("devops_probe", 1.0)
    # Gameplay monde (v1) : commit aid déterministe
    elif isinstance(ctx.get("world_action"), dict):
        intent, confidence = ("world_aid", 1.0)
    else:
        # Priorité : si le texte exprime clairement une quête/mission/etc., respecter le classifieur
        # même si un PNJ est ciblé (ex: une quête donnée par un PNJ).
        intent, confidence = _classifier.classify(payload.text)

        # Règle produit : si un NPC est explicitement ciblé côté client, forcer le dialogue
        # uniquement quand le texte n'a pas déjà déclenché une autre intention "métier".
        if intent == "unknown" and isinstance(npc_name, str) and npc_name.strip():
            intent, confidence = ("npc_dialogue", 0.9)
    cap = capability_registry.get(intent) or capability_registry.get("unknown")
    assert cap is not None
    agent_out = invoke_after_route(
        cap.routed_to,
        actor_id=payload.actor_id,
        text=payload.text,
        context=payload.context,
    )
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
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
            },
            ensure_ascii=False,
        )
    )
    return RouteResponse(
        intent=intent,
        confidence=confidence,
        routed_to=cap.routed_to,
        output={"capability": cap.name, **agent_out},
    )

