from __future__ import annotations

import math
import time
from enum import Enum
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field

ProactifMode = Literal["proactif_leger", "proactif_avance", "autonome"]


class InternalGoalStatus(str, Enum):
    en_cours = "en_cours"
    bloque = "bloque"
    termine = "termine"


class InternalGoal(BaseModel):
    id: str
    progression: float = Field(0.0, ge=0.0, le=1.0)
    status: InternalGoalStatus = InternalGoalStatus.en_cours


class ActionKind(str, Enum):
    question = "question"
    suggestion = "suggestion"
    plan = "plan"
    wait = "wait"
    autonomous_nudge = "autonomous_nudge"


class QuestionCategory(str, Enum):
    clarification = "clarification"
    exploration = "exploration"
    hypothese = "hypothese"
    projection = "projection"
    suggestion = "suggestion"
    verification = "verification"


class ProactiveAction(BaseModel):
    kind: ActionKind
    message: str
    mode: ProactifMode
    question_category: QuestionCategory | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class AgentInternalState(BaseModel):
    curiosite: float = Field(0.5, ge=0.0, le=1.0)
    tension: float = Field(0.2, ge=0.0, le=1.0)
    mode: ProactifMode = "proactif_leger"
    objectifs: list[InternalGoal] = Field(default_factory=list)
    memoire_courte: list[str] = Field(default_factory=list)
    last_user_ts: float = Field(default_factory=time.time)
    silence_seconds_est: float = 0.0


DEFAULT_GOALS = (
    InternalGoal(id="comprendre_utilisateur", progression=0.2),
    InternalGoal(id="clarifier_contexte", progression=0.1),
    InternalGoal(id="proposer_plan", progression=0.0),
    InternalGoal(id="verifier_coherence", progression=0.05),
)


class HybridProactiveEngine:
    """
    Moteur d'impulsion : modes léger / avancé / autonome, tension, curiosité, objectifs internes.

    Couche **comportementale déterministe** : aucun appel réseau. Pour des réponses langagières
    riches, brancher ``message_generator`` (ex. appel LLM).
    """

    def __init__(
        self,
        *,
        tension_autonome_seuil: float = 0.6,
        message_generator: Callable[[str, AgentInternalState, dict[str, Any]], str] | None = None,
    ) -> None:
        self._tension_autonome_seuil = tension_autonome_seuil
        self._message_generator = message_generator
        self.state = AgentInternalState(objectifs=list(DEFAULT_GOALS))

    def reset(self) -> None:
        self.state = AgentInternalState(objectifs=list(DEFAULT_GOALS))

    def observe_user_turn(
        self,
        user_message: str | None,
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = context if isinstance(context, dict) else {}
        now = time.time()
        self.state.last_user_ts = now
        self.state.silence_seconds_est = 0.0
        if user_message:
            text = user_message.strip()
            if text:
                self.state.memoire_courte.append(text[-500:])
                self.state.memoire_courte = self.state.memoire_courte[-12:]
            self._bump_goal("comprendre_utilisateur", 0.15 if text else 0.0)
        self._apply_context_signals(ctx, user_message)

    def tick_silence(self, dt_seconds: float) -> None:
        """Appeler depuis une boucle timer lorsque l'utilisateur est silencieux."""
        self.state.silence_seconds_est += max(0.0, dt_seconds)
        if self.state.silence_seconds_est > 30:
            self.state.tension = min(1.0, self.state.tension + 0.03 * (dt_seconds / 30.0))
        if self.state.silence_seconds_est > 120:
            self.state.curiosite = min(1.0, self.state.curiosite + 0.01 * (dt_seconds / 120.0))
        self._stagnation_tension()

    def _apply_context_signals(self, ctx: dict[str, Any], user_message: str | None) -> None:
        missing = 0
        for key in ("intent", "objectif", "contraintes"):
            if not ctx.get(key):
                missing += 1
        if missing:
            self.state.curiosite = min(1.0, self.state.curiosite + 0.08 * missing)
            self._set_goal_status("clarifier_contexte", InternalGoalStatus.en_cours)
        else:
            self._bump_goal("clarifier_contexte", 0.2)

        if ctx.get("incoherent"):
            self.state.tension = min(1.0, self.state.tension + 0.25)
            self._set_goal_status("verifier_coherence", InternalGoalStatus.bloque)

        self._stagnation_tension()

        text = (user_message or "").lower()
        if any(w in text for w in ("flou", "pas sûr", "je sais pas", "jsp", "maybe")):
            self.state.curiosite = min(1.0, self.state.curiosite + 0.12)
            self.state.tension = min(1.0, self.state.tension + 0.1)

    def _bump_goal(self, goal_id: str, delta: float) -> None:
        for g in self.state.objectifs:
            if g.id == goal_id:
                g.progression = min(1.0, g.progression + delta)
                if g.progression >= 0.95:
                    g.status = InternalGoalStatus.termine
                elif g.status == InternalGoalStatus.bloque and delta > 0:
                    g.status = InternalGoalStatus.en_cours
                break

    def _set_goal_status(self, goal_id: str, status: InternalGoalStatus) -> None:
        for g in self.state.objectifs:
            if g.id == goal_id:
                g.status = status
                break

    def _stagnation_tension(self) -> None:
        for g in self.state.objectifs:
            if g.status == InternalGoalStatus.en_cours and g.progression < 0.35:
                self.state.tension = min(1.0, self.state.tension + 0.04)
            if g.status == InternalGoalStatus.bloque:
                self.state.tension = min(1.0, self.state.tension + 0.08)

    def choose_mode(self, context: dict[str, Any] | None = None) -> ProactifMode:
        ctx = context if isinstance(context, dict) else {}
        if self.state.tension >= self._tension_autonome_seuil or (
            self.state.silence_seconds_est >= 45
            and any(g.status == InternalGoalStatus.bloque for g in self.state.objectifs)
        ):
            self.state.mode = "autonome"
            return "autonome"
        fuzzy = bool(ctx.get("objectif_flou")) or self.state.curiosite >= 0.55
        if fuzzy or ctx.get("missing_info") or self.state.curiosite >= 0.65:
            self.state.mode = "proactif_avance"
            return "proactif_avance"
        self.state.mode = "proactif_leger"
        return "proactif_leger"

    def decide(self, context: dict[str, Any] | None = None) -> ProactiveAction:
        ctx = context if isinstance(context, dict) else {}
        mode = self.choose_mode(ctx)

        if mode == "proactif_leger":
            return self._act_light(ctx)
        if mode == "proactif_avance":
            return self._act_advanced(ctx)
        return self._act_autonomous(ctx)

    def cooldown_decay(self, factor: float = 0.92) -> None:
        """Après une action proactive, réduit l'emballement."""
        self.state.tension *= factor
        self.state.curiosite *= math.sqrt(factor)

    def _prompt_hint(self, template_key: str, ctx: dict[str, Any]) -> str:
        if self._message_generator:
            return self._message_generator(template_key, self.state, ctx)
        return template_key

    def _act_light(self, ctx: dict[str, Any]) -> ProactiveAction:
        if not ctx.get("intent"):
            msg = self._prompt_hint(
                "Souhaites-tu plutôt une assistance ponctuelle, de l'exploration, ou un agent intégré à un pipeline ?",
                ctx,
            )
            return ProactiveAction(
                kind=ActionKind.question,
                message=msg,
                mode="proactif_leger",
                question_category=QuestionCategory.clarification,
            )
        msg = self._prompt_hint(
            "Je peux reformuler ce que j'ai compris et proposer la prochaine micro-étape utile — tu veux que je le fasse ?",
            ctx,
        )
        return ProactiveAction(
            kind=ActionKind.suggestion,
            message=msg,
            mode="proactif_leger",
            question_category=QuestionCategory.suggestion,
        )

    def _act_advanced(self, ctx: dict[str, Any]) -> ProactiveAction:
        msg = self._prompt_hint(
            "Voici une structure possible : (1) perception du contexte, (2) moteur motivation/tension, "
            "(3) action (question, plan, initiative). On valide ensemble cette découpe ou tu préfères une autre ?",
            ctx,
        )
        self._bump_goal("proposer_plan", 0.1)
        return ProactiveAction(
            kind=ActionKind.plan,
            message=msg,
            mode="proactif_avance",
            question_category=QuestionCategory.verification,
            meta={"sous_objectifs": ["perception", "motivation", "action"]},
        )

    def _act_autonomous(self, ctx: dict[str, Any]) -> ProactiveAction:
        blocked = [g.id for g in self.state.objectifs if g.status == InternalGoalStatus.bloque]
        msg = self._prompt_hint(
            "Je n'ai pas assez de signal sur ton objectif principal ; "
            f"j'hypothèses trois pistes en attente (bloqué sur : {', '.join(blocked) or 'rien'}). "
            "Dis-moi laquelle te correspond, ou corrige-en une.",
            ctx,
        )
        return ProactiveAction(
            kind=ActionKind.autonomous_nudge,
            message=msg,
            mode="autonome",
            question_category=QuestionCategory.hypothese,
        )


def integration_hints(
    state: AgentInternalState,
    world_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Indices pour un orchestrateur, un Pilot ou un routeur : sans exécuter d'action métier.

    Champs typiques côté monde (optionnel) : ``npc_id``, ``session_id``.
    """
    wc = world_context if isinstance(world_context, dict) else {}
    hints: dict[str, Any] = {
        "hybrid_proactive_mode": state.mode,
        "hybrid_tension": round(state.tension, 3),
        "hybrid_curiosite": round(state.curiosite, 3),
        "suggest_clarify_intent": state.mode != "proactif_leger",
        "allow_autonomous_followup": state.mode == "autonome",
    }
    if wc.get("npc_id"):
        hints["mmo_npc_id"] = wc["npc_id"]
    if wc.get("session_id"):
        hints["mmo_session_id"] = wc["session_id"]
    return hints
