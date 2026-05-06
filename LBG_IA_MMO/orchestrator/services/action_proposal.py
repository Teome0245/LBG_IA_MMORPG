from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from shared_registry import capability_registry


ProposalSource = Literal["deterministic", "mmo_session_bridge"]


class ActionProposal(BaseModel):
    capability: str
    routed_to: str
    action_context_key: str
    action: dict[str, object]
    context_patch: dict[str, object] = Field(default_factory=dict)
    summary: str
    risk_level: str
    requires_review: bool = True
    confidence: float = Field(..., ge=0.0, le=1.0)
    source: ProposalSource = "deterministic"
    mmo_trace: dict[str, object] | None = None


class ActionProposalResult(BaseModel):
    proposal: ActionProposal | None = None
    reason: str | None = None


def propose_action_from_text(text: str, context: dict[str, object] | None = None) -> ActionProposalResult:
    ctx = context if isinstance(context, dict) else {}
    raw = text.strip()
    normalized = _normalize(raw)
    if not normalized:
        return ActionProposalResult(reason="Texte vide.")

    proposal = (
        _propose_notepad(raw, normalized, ctx)
        or _propose_web_search(raw, normalized)
        or _propose_mail_preview(raw, normalized)
        or _propose_infra_selfcheck(normalized)
        or _propose_mmo_dev_plan(raw, normalized, ctx)
    )
    if proposal is None:
        return ActionProposalResult(reason="Aucune action sûre reconnue ; rester en conversation ou demander une précision.")
    return ActionProposalResult(proposal=proposal)


def _propose_notepad(raw: str, normalized: str, context: dict[str, object]) -> ActionProposal | None:
    if not re.search(r"\b(notepad|bloc[- ]?notes?|bloc note|editeur|éditeur)\b", normalized):
        return None
    if not re.search(r"\b(ecris|écris|ecrire|écrire|note|ajoute|append|dicte|dictée|dictee)\b", normalized):
        return None
    content = _extract_after(
        raw,
        ("écris", "ecris", "écrire", "ecrire", "note", "ajoute", "append", "dicte", "dictée", "dictee"),
    )
    if not content:
        content = raw
    path = context.get("desktop_default_notepad_path")
    path_s = path.strip() if isinstance(path, str) and path.strip() else r"C:\Users\Public\lbg_desktop.txt"
    return _desktop_proposal(
        action={"kind": "notepad_append", "path": path_s, "text": content.rstrip() + "\n"},
        summary="Préparer une écriture bornée dans un fichier ouvert avec Notepad.",
        confidence=0.82,
    )


def _propose_web_search(raw: str, normalized: str) -> ActionProposal | None:
    if not re.search(r"\b(cherche|chercher|recherche|rechercher|trouve|internet|web|site)\b", normalized):
        return None
    if re.search(r"\b(mail|email|e-mail|courriel|imap)\b", normalized):
        return None
    query = _extract_after(raw, ("cherche sur internet", "recherche sur internet", "cherche", "recherche", "trouve"))
    query = re.sub(r"^\s*(le\s+)?site\s+(de|du|d'|des)?\s*", "", query, flags=re.IGNORECASE).strip()
    if not query:
        query = raw
    return _desktop_proposal(
        action={"kind": "search_web_open", "query": query[:220]},
        summary="Préparer une recherche web via le moteur allowlisté du worker desktop.",
        confidence=0.8,
    )


def _propose_mail_preview(raw: str, normalized: str) -> ActionProposal | None:
    if not re.search(r"\b(mail|email|e-mail|courriel|imap)\b", normalized):
        return None
    sender = _extract_mail_filter(raw)
    action: dict[str, object] = {"kind": "mail_imap_preview", "max_messages": 3, "max_body_chars": 800, "max_scan": 200}
    if sender:
        action["from_contains"] = sender[:80]
    else:
        action["subject_contains"] = raw[:120]
    return _desktop_proposal(
        action=action,
        summary="Préparer un aperçu IMAP INBOX en lecture seule, borné et filtré.",
        confidence=0.78 if sender else 0.62,
    )


def _mmo_session_bridge_active(context: dict[str, object]) -> bool:
    """Pont volontaire MMO : exige un résumé non vide et une trace explicite côté client."""
    raw_ss = context.get("session_summary")
    if not isinstance(raw_ss, dict) or not raw_ss:
        return False
    bridge = context.get("mmo_bridge")
    if not isinstance(bridge, dict):
        return False
    return str(bridge.get("source") or "").strip() == "mmo_session_summary"


def _session_summary_prompt_fragment(context: dict[str, object]) -> str:
    raw_ss = context.get("session_summary")
    if not isinstance(raw_ss, dict):
        return ""
    parts: list[str] = []
    for key in ("tracked_quest", "last_npc", "player_note", "session_mood", "quest_snapshot", "memory_hint"):
        val = raw_ss.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(f"{key}: {val.strip()[:400]}")
    out = "\n".join(parts)
    return out[:1200]


def _propose_mmo_dev_plan(raw: str, normalized: str, context: dict[str, object]) -> ActionProposal | None:
    """
    Proposition de forge OpenGame en dry-run, motivée par une session MMO importée volontairement.
    Pas d'exécution réelle ni merge : le contexte force opengame_dry_run jusqu'au choix utilisateur.
    """
    if not _mmo_session_bridge_active(context):
        return None
    if not re.search(
        r"\b(forge|forger|prototype|opengame|sandbox|évolution|evolution|patch)\b"
        r'|\bplan\b.*\b(mmo|monde|jeu)\b|\b(idée|idee)\b.*\bmmo\b',
        normalized,
    ):
        return None
    cap = capability_registry.get("prototype_game")
    assert cap is not None
    prompt = (
        "Prototype sandbox (hors tronc MMO canon), à planifier sans merge automatique.\n\n"
        f"{_session_summary_prompt_fragment(context)}\n\n"
        f"Demande utilisateur : {raw.strip()[:700]}"
    )
    action: dict[str, object] = {
        "kind": "generate_prototype",
        "project_name": "mmo_bridge_idea",
        "prompt": prompt,
    }
    bridge = context.get("mmo_bridge") if isinstance(context.get("mmo_bridge"), dict) else {}
    trace = {
        "origin": "session_summary",
        "bridge_source": "mmo_session_summary",
        "imported_at": bridge.get("imported_at"),
        "session_summary_keys": sorted(
            k for k in (context.get("session_summary") or {}).keys() if isinstance(k, str)
        ),
    }
    return ActionProposal(
        capability=cap.name,
        routed_to=cap.routed_to,
        action_context_key=cap.action_context_key or "opengame_action",
        action=action,
        context_patch={
            "opengame_action": action,
            "opengame_dry_run": True,
        },
        summary="Préparer une génération OpenGame en sandbox (dry-run), à partir d'un résumé MMO importé volontairement — pas de merge automatique.",
        risk_level=cap.risk_level,
        confidence=0.71,
        source="mmo_session_bridge",
        mmo_trace=trace,
    )


def _propose_infra_selfcheck(normalized: str) -> ActionProposal | None:
    if not re.search(r"\b(selfcheck|devops|infra|healthz|santé|sante|état|etat|status|statut|backend|orchestrateur)\b", normalized):
        return None
    if not re.search(r"\b(vérifie|verifie|check|sonde|diagnostic|état|etat|status|statut|santé|sante|healthz|selfcheck)\b", normalized):
        return None
    cap = capability_registry.get("devops_probe")
    assert cap is not None
    return ActionProposal(
        capability=cap.name,
        routed_to=cap.routed_to,
        action_context_key=cap.action_context_key or "devops_action",
        action={"kind": "selfcheck"},
        context_patch={"devops_action": {"kind": "selfcheck"}},
        summary="Préparer un selfcheck DevOps read-only sur les sondes allowlistées.",
        risk_level=cap.risk_level,
        confidence=0.76,
    )


def _desktop_proposal(*, action: dict[str, object], summary: str, confidence: float) -> ActionProposal:
    cap = capability_registry.get("desktop_control")
    assert cap is not None
    return ActionProposal(
        capability=cap.name,
        routed_to=cap.routed_to,
        action_context_key=cap.action_context_key or "desktop_action",
        action=action,
        context_patch={"desktop_action": action, "desktop_dry_run": True},
        summary=summary,
        risk_level=cap.risk_level,
        confidence=confidence,
    )


def _normalize(value: str) -> str:
    return value.strip().lower()


def _extract_after(raw: str, markers: tuple[str, ...]) -> str:
    lower = raw.lower()
    best: tuple[int, int, str] | None = None
    for marker in sorted(markers, key=len, reverse=True):
        idx = lower.find(marker.lower())
        if idx < 0:
            continue
        end = idx + len(marker)
        if best is None or idx < best[0] or (idx == best[0] and end > best[1]):
            best = (idx, end, marker)
    if best is None:
        return ""
    return raw[best[1] :].strip(" :,-\"'")


def _extract_mail_filter(raw: str) -> str:
    patterns = (
        r"\b(?:de|from)\s+[\"']?([^\"',.;!?]+)",
        r"\b(?:mail|email|e-mail|courriel)\s+(?:de|from)\s+[\"']?([^\"',.;!?]+)",
    )
    for pattern in patterns:
        m = re.search(pattern, raw, flags=re.IGNORECASE)
        if m:
            value = m.group(1).strip()
            value = re.sub(r"\b(et|qui|avec|contenant|sujet)\b.*$", "", value, flags=re.IGNORECASE).strip()
            if value:
                return value
    quoted = re.search(r"[\"']([^\"']{2,80})[\"']", raw)
    if quoted:
        return quoted.group(1).strip()
    return ""
