"""
Planificateur d'objectifs pour le moteur de jobs autonome ("type Cowork").

Transforme un objectif en langage naturel en un **plan** = liste d'étapes
exécutables, chacune mappée sur une capability du registry central.

Deux sources possibles :

- ``deterministic`` (défaut, hermétique, testable) : on découpe l'objectif en
  clauses puis on réutilise ``propose_action_from_text`` (la même brique que
  ``POST /v1/action-proposal``). Une clause sans action sûre devient une étape
  ``note`` (capability ``unknown``, simple accusé/clarification).
- ``llm`` (optionnel, opt-in) : un LLM borné propose un plan JSON ; chaque étape
  est revalidée contre une **allowlist** de capabilities et contre le registry.
  Toute anomalie ⇒ repli déterministe.

Sécurité (périmètre restreint du premier incrément) :

- seules les capabilities de ``PLANNER_ALLOWED_CAPABILITIES`` sont planifiables ;
- les actions à effet de bord sont forcées en **dry-run** dans le ``context_patch``
  (``desktop_dry_run`` / ``devops_dry_run`` / ``opengame_dry_run``). L'exécution
  réelle reste pilotée plus tard par le moteur de jobs via un token d'approbation.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from services.action_proposal import ActionProposal, propose_action_from_text
from services.lia_jobs import (
    LIA_ACTOR_ID,
    lia_core3_context_patch,
    lia_core3_plan_action,
    lia_tick_prompt_from_objective,
    objective_mentions_lia_mmo,
)
from shared_registry import capability_registry

# Capabilities qu'un plan autonome a le droit d'invoquer.
PLANNER_ALLOWED_CAPABILITIES = frozenset(
    {
        "npc_dialogue",
        "project_pm",
        "devops_probe",
        "network_inventory",
        "core3_bot_action",
        "desktop_control",
        "prototype_game",
        "unknown",
    }
)

# Drapeaux de dry-run injectés selon la clé d'action, pour rester en périmètre sûr.
_DRY_RUN_FLAG_BY_KEY = {
    "desktop_action": "desktop_dry_run",
    "devops_action": "devops_dry_run",
    "opengame_action": "opengame_dry_run",
}

_MAX_STEPS = 8


@dataclass
class PlanStep:
    capability: str
    routed_to: str
    summary: str
    risk_level: str
    text: str
    action_context_key: str | None = None
    action: dict[str, object] = field(default_factory=dict)
    context_patch: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "capability": self.capability,
            "routed_to": self.routed_to,
            "action_context_key": self.action_context_key,
            "action": dict(self.action),
            "context_patch": dict(self.context_patch),
            "summary": self.summary,
            "risk_level": self.risk_level,
            "text": self.text,
        }


@dataclass
class PlanResult:
    steps: list[PlanStep]
    source: str  # "deterministic" | "llm"
    reason: str | None = None


# --------------------------------------------------------------------------- #
# Découpage déterministe
# --------------------------------------------------------------------------- #

_CLAUSE_SPLIT_RE = re.compile(
    r"\s*(?:\n+|;|\.|→|->|\bpuis\b|\bensuite\b|\baprès\b|\bapres\b|\bet ensuite\b|\bensuite\b)\s*",
    re.IGNORECASE,
)

# « … checkup et dis-moi / résume … » → deux étapes (sonde puis synthèse dialogue).
_SYNTHESIS_ET_SPLIT_RE = re.compile(
    r"\s+\bet\s+(?=(?:me\s+)?(?:dis|dire|racont|résume|resume|explique|synth|liste|décris|decris|donne|présente|presente))",
    re.IGNORECASE,
)


def split_objective(objective: str) -> list[str]:
    raw = (objective or "").strip()
    if not raw:
        return []
    m = _SYNTHESIS_ET_SPLIT_RE.search(raw)
    if m:
        left, right = raw[: m.start()].strip(" ,-"), raw[m.end() :].strip(" ,-")
        if len(left) >= 2 and len(right) >= 2:
            return [left, right][: _MAX_STEPS]
    parts = [p.strip(" ,-") for p in _CLAUSE_SPLIT_RE.split(raw)]
    clauses = [p for p in parts if len(p) >= 2]
    return clauses[:_MAX_STEPS] if clauses else [raw]


def _force_dry_run(context_patch: dict[str, object]) -> dict[str, object]:
    patch = dict(context_patch)
    for action_key, dry_flag in _DRY_RUN_FLAG_BY_KEY.items():
        if action_key in patch:
            patch[dry_flag] = True
    return patch


def _step_from_proposal(proposal: ActionProposal, text: str) -> PlanStep:
    return PlanStep(
        capability=proposal.capability,
        routed_to=proposal.routed_to,
        action_context_key=proposal.action_context_key,
        action=dict(proposal.action),
        context_patch=_force_dry_run(proposal.context_patch),
        summary=proposal.summary,
        risk_level=proposal.risk_level,
        text=text,
    )


def _objective_is_network_infra_survey(normalized: str) -> bool:
    """Objectifs type cartographie LAN / infra / appareils (plan Cowork multi-étapes)."""
    has_scope = re.search(
        r"\b(réseau|reseau|réseaux|reseaux|infra|infrastructure|appareil|appareils|"
        r"lan|vm|machines?|topologie|environnement)\b",
        normalized,
    )
    has_intent = re.search(
        r"\b(analyse|analyser|analys|établir|établie|établis|cartographie|cartograph|inventaire|audit|"
        r"découvr|decouvr|présents?|presents?|recens|établissement|résume|resume)\b",
        normalized,
    )
    return bool(has_scope and has_intent)


def _objective_is_vm_memory_supervision(normalized: str) -> bool:
    return bool(
        re.search(r"\b(mémoire|memoire|memory|ram|swap)\b", normalized)
        and re.search(
            r"\b(supervis|surveill|contrôl|control|sond|analys|audit|compare|"
            r"fuites?|libér|liber|charge|chargement|246|245|110)\b",
            normalized,
        )
    )


def _plan_vm_memory_supervision(objective: str, ctx: dict[str, object]) -> PlanResult | None:
    """Plan Cowork : sonde mémoire VM + synthèse."""
    norm = (objective or "").strip().lower()
    if not _objective_is_vm_memory_supervision(norm):
        return None

    cap = capability_registry.get("devops_probe")
    if cap is None:
        return None

    steps: list[PlanStep] = [
        PlanStep(
            capability=cap.name,
            routed_to=cap.routed_to,
            action_context_key="devops_action",
            action={"kind": "vm_memory_probe"},
            context_patch=_force_dry_run({"devops_action": {"kind": "vm_memory_probe"}}),
            summary="Sonde mémoire read-only (SSH) — 246 Prime, 245 PreCU, 110 Ollama, 140 core.",
            risk_level=cap.risk_level,
            text="Supervision mémoire VM LAN (free, swap, top processus)",
        )
    ]

    cap_dlg = capability_registry.get("npc_dialogue")
    if cap_dlg is not None:
        steps.append(
            PlanStep(
                capability=cap_dlg.name,
                routed_to=cap_dlg.routed_to,
                action_context_key=cap_dlg.action_context_key,
                action={},
                context_patch={"_job_synthesis": True},
                summary="Synthèse mémoire : comparaison 246/245/110, alertes, pistes.",
                risk_level=cap_dlg.risk_level,
                text=(
                    f"{objective.strip()}\n\n"
                    "Résume en français : mémoire par VM, processus dominant, swap, "
                    "si 246 « charge sans libérer » (cache Linux / core3-clean), "
                    "et recommandations (watchdog, restart Prime, RAM VM, Ollama)."
                ),
            )
        )

    return PlanResult(
        steps=steps[:_MAX_STEPS],
        source="deterministic",
        reason="plan supervision mémoire VM (sonde SSH + synthèse)",
    )


def _objective_is_proxmox_supervision(normalized: str) -> bool:
    return bool(
        re.search(r"\b(proxmox|hyperviseur|hypervisor|pve)\b", normalized)
        and re.search(
            r"\b(supervis|surveill|état|etat|status|cluster|vm|ressources?|charge)\b",
            normalized,
        )
    )


def _plan_proxmox_supervision(objective: str, ctx: dict[str, object]) -> PlanResult | None:
    norm = (objective or "").strip().lower()
    if not _objective_is_proxmox_supervision(norm):
        return None

    cap = capability_registry.get("devops_probe")
    if cap is None:
        return None

    steps: list[PlanStep] = [
        PlanStep(
            capability=cap.name,
            routed_to=cap.routed_to,
            action_context_key="devops_action",
            action={"kind": "proxmox_status"},
            context_patch=_force_dry_run({"devops_action": {"kind": "proxmox_status"}}),
            summary="Sonde Proxmox read-only — cluster + VMs LAN.",
            risk_level=cap.risk_level,
            text="Supervision Proxmox (version, VMs, RAM/CPU par rôle LAN)",
        )
    ]

    cap_dlg = capability_registry.get("npc_dialogue")
    if cap_dlg is not None:
        steps.append(
            PlanStep(
                capability=cap_dlg.name,
                routed_to=cap_dlg.routed_to,
                action_context_key=cap_dlg.action_context_key,
                action={},
                context_patch={"_job_synthesis": True},
                summary="Synthèse Proxmox : VMs hors ligne, charge RAM, actions suggérées.",
                risk_level=cap_dlg.risk_level,
                text=(
                    f"{objective.strip()}\n\n"
                    "Résume en français : état cluster Proxmox, VMs core/front/precu/prime, "
                    "alertes RAM, et si une VM est arrêtée ou surchargée."
                ),
            )
        )

    return PlanResult(
        steps=steps[:_MAX_STEPS],
        source="deterministic",
        reason="plan supervision Proxmox (API read-only + synthèse)",
    )


def _plan_network_infra_survey(objective: str, ctx: dict[str, object]) -> PlanResult | None:
    """Plan Cowork 4 étapes : selfcheck → inventaire LAN → registry → synthèse."""
    norm = (objective or "").strip().lower()
    if not _objective_is_network_infra_survey(norm):
        return None

    steps: list[PlanStep] = []

    r_self = propose_action_from_text("devops selfcheck dry-run infrastructure", ctx)
    if r_self.proposal is not None:
        steps.append(_step_from_proposal(r_self.proposal, "Selfcheck DevOps (sondes allowlistées, read-only)"))
    else:
        cap = capability_registry.get("devops_probe")
        if cap is not None:
            steps.append(
                PlanStep(
                    capability=cap.name,
                    routed_to=cap.routed_to,
                    action_context_key="devops_action",
                    action={"kind": "selfcheck"},
                    context_patch=_force_dry_run({"devops_action": {"kind": "selfcheck"}}),
                    summary="Selfcheck DevOps read-only sur les sondes allowlistées.",
                    risk_level=cap.risk_level,
                    text="Selfcheck DevOps (infrastructure)",
                )
            )

    r_net = propose_action_from_text("inventaire réseau lan appareils cartographie", ctx)
    if r_net.proposal is not None:
        steps.append(_step_from_proposal(r_net.proposal, "Inventaire réseau LAN (sondes HTTP/TCP)"))
    else:
        cap_net = capability_registry.get("network_inventory")
        if cap_net is not None:
            steps.append(
                PlanStep(
                    capability=cap_net.name,
                    routed_to=cap_net.routed_to,
                    action_context_key=cap_net.action_context_key,
                    action={},
                    context_patch={},
                    summary="Inventaire réseau LAN read-only (core/front/mmo/desktop).",
                    risk_level=cap_net.risk_level,
                    text="Inventaire réseau LAN — cartographie des appareils connus",
                )
            )

    r_caps = propose_action_from_text("établie la liste des agents disponible et leurs capacité", ctx)
    if r_caps.proposal is not None:
        steps.append(_step_from_proposal(r_caps.proposal, "Inventaire agents / capabilities (registry)"))

    cap_dlg = capability_registry.get("npc_dialogue")
    if cap_dlg is not None:
        steps.append(
            PlanStep(
                capability=cap_dlg.name,
                routed_to=cap_dlg.routed_to,
                action_context_key=cap_dlg.action_context_key,
                action={},
                context_patch={"_job_synthesis": True},
                summary="Synthèse réseau / infra / appareils à partir des étapes précédentes.",
                risk_level=cap_dlg.risk_level,
                text=(
                    f"{objective.strip()}\n\n"
                    "Résume en français : état des sondes, agents/capabilities disponibles, "
                    "et pistes pour compléter la cartographie (sans inventer de machines non vues)."
                ),
            )
        )

    if not steps:
        return None
    return PlanResult(
        steps=steps[:_MAX_STEPS],
        source="deterministic",
        reason="plan réseau/infra (selfcheck + inventaire LAN + registry + synthèse)",
    )


def _objective_needs_lia_synthesis(normalized: str) -> bool:
    return bool(
        re.search(
            r"\b(résume|resume|dis[- ]?moi|explique|synth|rapport|decris|décris|raconte)\b",
            normalized,
        )
    )


def _plan_lia_mmo(objective: str, ctx: dict[str, object]) -> PlanResult | None:
    """Plan Cowork Lia : tick Core3 (+ synthèse optionnelle)."""
    norm = (objective or "").strip().lower()
    if not objective_mentions_lia_mmo(norm):
        return None

    cap = capability_registry.get("core3_bot_action")
    if cap is None:
        return None

    prompt = lia_tick_prompt_from_objective(objective)
    patch = lia_core3_context_patch(prompt=prompt)
    patch["_lia_job_actor"] = LIA_ACTOR_ID

    steps: list[PlanStep] = [
        PlanStep(
            capability=cap.name,
            routed_to=cap.routed_to,
            action_context_key=cap.action_context_key,
            action=lia_core3_plan_action(prompt=prompt),
            context_patch=patch,
            summary="Tour Lia en MMO (player_think incarnation, enqueue sidecar).",
            risk_level=cap.risk_level,
            text=prompt,
        )
    ]

    if _objective_needs_lia_synthesis(norm):
        cap_dlg = capability_registry.get("npc_dialogue")
        if cap_dlg is not None:
            steps.append(
                PlanStep(
                    capability=cap_dlg.name,
                    routed_to=cap_dlg.routed_to,
                    action_context_key=cap_dlg.action_context_key,
                    action={},
                    context_patch={"_job_synthesis": True},
                    summary="Synthèse du tour Lia (observation / action en jeu).",
                    risk_level=cap_dlg.risk_level,
                    text=(
                        f"{objective.strip()}\n\n"
                        "Résume en français ce que Lia a observé ou fait en jeu "
                        "(d'après l'étape Core3 précédente, sans inventer)."
                    ),
                )
            )

    return PlanResult(
        steps=steps[:_MAX_STEPS],
        source="deterministic",
        reason="plan Lia MMO (core3_bot_action + synthèse optionnelle)",
    )


def _note_step(text: str) -> PlanStep:
    cap = capability_registry.get("unknown")
    assert cap is not None
    return PlanStep(
        capability=cap.name,
        routed_to=cap.routed_to,
        action_context_key=None,
        action={},
        context_patch={},
        summary=f"Noter / clarifier : {text[:160]}",
        risk_level=cap.risk_level,
        text=text,
    )


def plan_deterministic(objective: str, context: dict[str, object] | None = None) -> PlanResult:
    ctx = context if isinstance(context, dict) else {}
    lia = _plan_lia_mmo(objective, ctx)
    if lia is not None:
        return lia
    mem = _plan_vm_memory_supervision(objective, ctx)
    if mem is not None:
        return mem
    prox = _plan_proxmox_supervision(objective, ctx)
    if prox is not None:
        return prox
    survey = _plan_network_infra_survey(objective, ctx)
    if survey is not None:
        return survey
    clauses = split_objective(objective)
    if not clauses:
        return PlanResult(steps=[], source="deterministic", reason="Objectif vide.")
    steps: list[PlanStep] = []
    for clause in clauses:
        result = propose_action_from_text(clause, ctx)
        if result.proposal is not None and result.proposal.capability in PLANNER_ALLOWED_CAPABILITIES:
            steps.append(_step_from_proposal(result.proposal, clause))
        else:
            steps.append(_note_step(clause))
    return PlanResult(steps=steps, source="deterministic")


# --------------------------------------------------------------------------- #
# Planner LLM optionnel (opt-in)
# --------------------------------------------------------------------------- #

_LLM_SYSTEM_PROMPT = """Tu es un planificateur de tâches (style ReAct) pour un orchestrateur multi-agents sous garde-fous.
On te donne un objectif en français (parfois avec des souvenirs et un journal d'erreurs).

Raisonne d'abord intérieurement (Pensée → Plan), PUIS réponds UNIQUEMENT par un JSON valide
(sans markdown, sans texte autour), de la forme :
{"steps":[{"capability":"<cap>","summary":"<court>","text":"<instruction>"}]}

Méthode de raisonnement (ReAct) :
1. Décompose l'objectif en étapes minimales et ordonnées (chaque étape = une seule capability).
2. Anticipe l'échec : commence par les étapes de lecture/diagnostic (read-only / dry-run) avant toute action sensible.
3. Si un journal d'erreurs est fourni : NE répète PAS l'étape qui a échoué telle quelle ; change d'angle (autre cap, étape de diagnostic intermédiaire, reformulation).
4. Si des souvenirs d'objectifs similaires existent : réutilise ce qui a fonctionné.
5. N'abandonne pas : produis toujours au moins une étape exploitable.

Capabilities autorisées (exactement une par étape) :
- npc_dialogue : répondre / rédiger / synthétiser en langage naturel
- project_pm : consulter jalons, roadmap, planning
- devops_probe : vérifier la santé infra (selfcheck read-only)
- network_inventory : cartographier les hôtes LAN connus (sondes read-only)
- core3_bot_action : faire jouer Lia en MMO (incarnation orchestrateur, sidecar Core3)
- unknown : étape de réflexion / clarification / note

Règles dures :
- 1 à 6 étapes, ordonnées.
- N'invente aucune autre capability.
- Ne demande JAMAIS d'action destructive : pas d'écriture disque réelle, pas de redémarrage.
- `text` : l'instruction concrète de l'étape, en français."""


def planner_llm_enabled(context: dict[str, Any] | None = None) -> bool:
    if isinstance(context, dict):
        raw = context.get("_planner")
        if isinstance(raw, str):
            s = raw.strip().lower()
            if s == "deterministic":
                return False
            if s == "llm":
                return True
    return os.environ.get("LBG_JOBS_PLANNER_LLM", "").strip().lower() in ("1", "true", "yes", "on")


def _llm_base_url() -> str:
    return os.environ.get("LBG_JOBS_PLANNER_LLM_BASE_URL", "").strip().rstrip("/")


def _llm_model() -> str:
    return os.environ.get("LBG_JOBS_PLANNER_LLM_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"


def _resolve_secret_ref(raw: str | None) -> str:
    s = (raw or "").strip()
    if len(s) >= 4 and s.startswith("${") and s.endswith("}"):
        key = s[2:-1].strip()
        if key:
            return os.environ.get(key, "").strip()
    return s


def _llm_api_key() -> str:
    return _resolve_secret_ref(os.environ.get("LBG_JOBS_PLANNER_LLM_API_KEY", "")).strip()


def _llm_timeout_s() -> float:
    try:
        return float(os.environ.get("LBG_JOBS_PLANNER_LLM_TIMEOUT_S", "30").strip())
    except ValueError:
        return 30.0


def _parse_model_content(content: str) -> dict[str, Any] | None:
    s = content.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```\s*$", "", s)
    try:
        out = json.loads(s)
        return out if isinstance(out, dict) else None
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, re.DOTALL)
        if not m:
            return None
        try:
            out = json.loads(m.group(0))
            return out if isinstance(out, dict) else None
        except json.JSONDecodeError:
            return None


# Capabilities que le planner LLM peut produire (sous-ensemble "texte/lecture" sûr).
_LLM_ALLOWED = frozenset(
    {"npc_dialogue", "project_pm", "devops_probe", "network_inventory", "core3_bot_action", "unknown"}
)


def _step_from_llm(raw: dict[str, Any]) -> PlanStep | None:
    cap_name = raw.get("capability")
    if not isinstance(cap_name, str) or cap_name.strip() not in _LLM_ALLOWED:
        return None
    cap = capability_registry.get(cap_name.strip())
    if cap is None:
        return None
    text = raw.get("text")
    text_s = text.strip() if isinstance(text, str) and text.strip() else ""
    summary = raw.get("summary")
    summary_s = summary.strip() if isinstance(summary, str) and summary.strip() else (text_s[:120] or cap.description)
    context_patch: dict[str, object] = {}
    action: dict[str, object] = {}
    if cap.name == "devops_probe":
        action = {"kind": "selfcheck"}
        context_patch = {"devops_action": {"kind": "selfcheck"}, "devops_dry_run": True}
    elif cap.name == "core3_bot_action":
        prompt = text_s or summary_s
        action = lia_core3_plan_action(prompt=prompt)
        context_patch = lia_core3_context_patch(prompt=prompt)
        context_patch["_lia_job_actor"] = LIA_ACTOR_ID
    return PlanStep(
        capability=cap.name,
        routed_to=cap.routed_to,
        action_context_key=cap.action_context_key,
        action=action,
        context_patch=context_patch,
        summary=summary_s,
        risk_level=cap.risk_level,
        text=text_s or summary_s,
    )


def _llm_user_content(
    objective: str,
    *,
    error_log: list[dict[str, Any]] | None = None,
    memories: list[dict[str, Any]] | None = None,
) -> str:
    """Message utilisateur : objectif + souvenirs + journal d'erreurs (pour le replan)."""
    parts = [f"Objectif : {objective.strip()[:3000]}"]
    if memories:
        lines = []
        for m in memories[:3]:
            g = str(m.get("goal", ""))[:120]
            out = str(m.get("outcome", ""))
            reso = str(m.get("resolution", ""))[:160]
            lines.append(f"- « {g} » → {out}" + (f" ; résolution : {reso}" if reso else ""))
        if lines:
            parts.append("Souvenirs d'objectifs similaires (réutilise ce qui a marché) :\n" + "\n".join(lines))
    if error_log:
        lines = []
        for e in error_log[-3:]:
            cap = str(e.get("capability", ""))
            err = str(e.get("error", ""))[:200]
            lines.append(f"- étape {cap} a échoué : {err}")
        if lines:
            parts.append(
                "Tentative précédente en échec — REPLANIFIE différemment (n'abandonne pas, "
                "évite de répéter la même étape qui a échoué) :\n" + "\n".join(lines)
            )
    return "\n\n".join(parts)


def plan_llm(
    objective: str,
    *,
    error_log: list[dict[str, Any]] | None = None,
    memories: list[dict[str, Any]] | None = None,
) -> PlanResult | None:
    base = _llm_base_url()
    if not base:
        return None
    url = f"{base}/chat/completions"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    key = _llm_api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    body: dict[str, Any] = {
        "model": _llm_model(),
        "messages": [
            {"role": "system", "content": _LLM_SYSTEM_PROMPT},
            {"role": "user", "content": _llm_user_content(objective, error_log=error_log, memories=memories)[:4000]},
        ],
        "temperature": 0.1,
        "max_tokens": 700,
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=_llm_timeout_s()) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
        return None
    try:
        j = json.loads(raw)
    except json.JSONDecodeError:
        return None
    choices = j.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    msg = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = msg.get("content") if isinstance(msg, dict) else None
    if not isinstance(content, str):
        return None
    parsed = _parse_model_content(content)
    if not parsed:
        return None
    raw_steps = parsed.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        return None
    steps: list[PlanStep] = []
    for raw_step in raw_steps[:_MAX_STEPS]:
        if not isinstance(raw_step, dict):
            continue
        step = _step_from_llm(raw_step)
        if step is not None:
            steps.append(step)
    if not steps:
        return None
    return PlanResult(steps=steps, source="llm")


# --------------------------------------------------------------------------- #
# Point d'entrée
# --------------------------------------------------------------------------- #


def plan_objective(
    objective: str,
    context: dict[str, object] | None = None,
    *,
    error_log: list[dict[str, Any]] | None = None,
    memories: list[dict[str, Any]] | None = None,
) -> PlanResult:
    """Planifie un objectif. LLM si activé et disponible, sinon repli déterministe.

    ``error_log`` / ``memories`` (replan + apprentissage) ne sont exploités que par le
    planner LLM ; le planner déterministe reste hermétique et reproductible.
    """
    ctx = context if isinstance(context, dict) else {}
    lia = _plan_lia_mmo(objective, ctx)
    if lia is not None:
        return lia
    mem = _plan_vm_memory_supervision(objective, ctx)
    if mem is not None:
        return mem
    prox = _plan_proxmox_supervision(objective, ctx)
    if prox is not None:
        return prox
    survey = _plan_network_infra_survey(objective, ctx)
    if survey is not None:
        return survey
    if planner_llm_enabled(context):
        llm = plan_llm(objective, error_log=error_log, memories=memories)
        if llm is not None and llm.steps:
            return llm
    return plan_deterministic(objective, context)
