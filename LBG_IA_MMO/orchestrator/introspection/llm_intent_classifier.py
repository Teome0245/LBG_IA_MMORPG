"""
Classifieur d'intention optionnel via LLM (API type OpenAI : POST …/chat/completions).

Sécurité : seuls des intents « texte seul » sont autorisés (pas desktop/world/opengame
sans action structurée — le routeur les gère déjà avant ce classifieur).
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

ALLOWED_INTENTS = frozenset(
    {
        "npc_dialogue",
        "quest_request",
        "combat_action",
        "devops_probe",
        "project_pm",
        "unknown",
    }
)

SYSTEM_PROMPT = """Tu es un routeur d'intentions pour un orchestrateur multi-agents (MMO, DevOps, chef de projet).
Réponds UNIQUEMENT par un JSON valide, sans markdown ni texte autour, de la forme :
{"intent":"<intent>","confidence":<nombre entre 0 et 1>,"assistant_reply":"<1 à 3 phrases en français>"}

Valeurs possibles pour intent (exactement une) :
- npc_dialogue : parler à un personnage, jeu de rôle, conversation dans le monde fictif
- quest_request : quête, mission, objectif à accomplir dans le jeu
- combat_action : combat, attaque, affrontement
- devops_probe : infrastructure, santé des services, diagnostic technique, logs, systemd, selfcheck
- project_pm : chef de projet, jalons, roadmap, vision produit, planning
- unknown : rien ne correspond clairement ou trop ambigu

Règles :
- Ne renvoie JAMAIS desktop_control, world_aid, prototype_game (réservés au contexte JSON structuré côté client).
- assistant_reply : ce que l'utilisateur comprendra (résumé de l'action routée ou demande de précision).
- confidence : ta certitude (ex. 0.85 si clair, 0.45 si flou — dans ce cas intent peut être unknown)."""


def intent_llm_env_enabled() -> bool:
    v = os.environ.get("LBG_ORCHESTRATOR_INTENT_LLM", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def should_use_llm_intent(context: dict[str, Any]) -> bool:
    raw = context.get("_intent_classify")
    if isinstance(raw, str):
        s = raw.strip().lower()
        if s == "deterministic":
            return False
        if s == "llm":
            return True
    return intent_llm_env_enabled()


def _base_url() -> str:
    return os.environ.get("LBG_ORCHESTRATOR_INTENT_LLM_BASE_URL", "").strip().rstrip("/")


def _model() -> str:
    return os.environ.get("LBG_ORCHESTRATOR_INTENT_LLM_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"


def _api_key() -> str:
    return os.environ.get("LBG_ORCHESTRATOR_INTENT_LLM_API_KEY", "").strip()


def _timeout_s() -> float:
    try:
        return float(os.environ.get("LBG_ORCHESTRATOR_INTENT_LLM_TIMEOUT_S", "25").strip())
    except ValueError:
        return 25.0


def _override_conf() -> float:
    """Si le classifieur déterministe a déjà trouvé une intention, le LLM ne la remplace que si confidence >= ce seuil."""
    try:
        return float(os.environ.get("LBG_ORCHESTRATOR_INTENT_LLM_OVERRIDE_CONF", "0.92").strip())
    except ValueError:
        return 0.92


def _parse_model_content(content: str) -> dict[str, Any] | None:
    s = content.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```\s*$", "", s)
    try:
        out = json.loads(s)
        return out if isinstance(out, dict) else None
    except json.JSONDecodeError:
        m = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", s, re.DOTALL)
        if not m:
            return None
        try:
            out = json.loads(m.group(0))
            return out if isinstance(out, dict) else None
        except json.JSONDecodeError:
            return None


def classify_intent_llm(user_text: str) -> tuple[str, float, dict[str, Any]] | None:
    base = _base_url()
    if not base:
        return None
    url = f"{base}/chat/completions"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    key = _api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    body: dict[str, Any] = {
        "model": _model(),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text.strip()[:4000]},
        ],
        "temperature": 0.15,
        "max_tokens": 350,
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=_timeout_s()) as resp:
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
    out = _parse_model_content(content)
    if not out:
        return None
    intent_raw = out.get("intent")
    if not isinstance(intent_raw, str):
        return None
    intent = intent_raw.strip()
    if intent not in ALLOWED_INTENTS:
        intent = "unknown"
    try:
        confidence = float(out.get("confidence", 0.7))
    except (TypeError, ValueError):
        confidence = 0.7
    confidence = max(0.0, min(1.0, confidence))
    meta: dict[str, Any] = {"intent_source": "llm"}
    reply = out.get("assistant_reply")
    if isinstance(reply, str) and reply.strip():
        meta["assistant_reply"] = reply.strip()[:2000]
    return intent, confidence, meta


def hybrid_classify(
    text: str,
    context: dict[str, Any],
    deterministic_classify: Any,
) -> tuple[str, float, dict[str, Any]]:
    """
    Appelle le classifieur déterministe puis, si autorisé, le LLM.
    Si le déterministe a déjà une intention connue (non unknown), le LLM ne la remplace
    que si sa propre confidence >= LBG_ORCHESTRATOR_INTENT_LLM_OVERRIDE_CONF.
    """
    det_intent, det_conf = deterministic_classify(text)
    meta_base: dict[str, Any] = {"intent_source": "deterministic"}

    if not should_use_llm_intent(context):
        return det_intent, det_conf, meta_base
    if not _base_url():
        return det_intent, det_conf, {**meta_base, "intent_llm_skipped": "no_base_url"}

    llm = classify_intent_llm(text)
    if llm is None:
        return det_intent, det_conf, {**meta_base, "intent_llm_error": True}

    lintent, lconf, meta_llm = llm
    thresh = _override_conf()
    if det_intent != "unknown" and lconf < thresh:
        return det_intent, det_conf, meta_base

    return lintent, lconf, meta_llm
