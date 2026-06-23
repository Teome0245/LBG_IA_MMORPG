from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from shared_registry import capability_registry

from lbg_agents.desktop_apps import enrich_open_app_action, extract_exe_path_from_goal
from lbg_agents.desktop_targets import infer_desktop_target_from_text

from services.lia_jobs import (
    LIA_ACTOR_ID,
    lia_core3_context_patch,
    lia_core3_plan_action,
    lia_tick_prompt_from_objective,
    objective_mentions_lia_mmo,
)


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
        or _propose_mail_preview(raw, normalized)
        or _propose_core3_lia(raw, normalized)
        or _propose_capabilities_inventory(normalized)
        or _propose_network_inventory(normalized)
        or _propose_infra_selfcheck(normalized)
        or _propose_dialogue_consult(normalized, raw)
        or _propose_project_pm_consult(normalized)
        or _propose_web_search(raw, normalized)
        or _propose_job_synthesis(normalized)
        or _propose_vm_memory_probe(normalized)
        or _propose_proxmox_status(normalized)
        or _propose_open_app(raw, normalized)
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
        text=raw,
    )


def _propose_project_pm_consult(normalized: str) -> ActionProposal | None:
    """Questions projet / chemins doc — agent PM (jalons, docs/, plan de route)."""
    if not re.search(
        r"\b(chef de projet|jalon|roadmap|plan de route|vision produit|état d'avancement|"
        r"statut du projet|docs/|documentation)\b",
        normalized,
    ):
        if not (
            re.search(r"\b(chemin|fichier|fichiers|path|repo|modifier|éditer|editer)\b", normalized)
            and re.search(r"\b(donne|indique|montre|quel|quelle|où|ou)\b", normalized)
        ):
            return None
    cap = capability_registry.get("project_pm")
    assert cap is not None
    return ActionProposal(
        capability=cap.name,
        routed_to=cap.routed_to,
        action_context_key=cap.action_context_key or "project_pm",
        action={},
        context_patch={"pm_focus": True},
        summary="Consulter le chef de projet (jalons, docs, chemins de fichiers documentés).",
        risk_level=cap.risk_level,
        confidence=0.78,
    )


def _propose_core3_lia(raw: str, normalized: str) -> ActionProposal | None:
    """Pilotage Lia en MMO via sidecar Core3 (player_think + incarnation)."""
    if not objective_mentions_lia_mmo(normalized):
        return None
    cap = capability_registry.get("core3_bot_action")
    assert cap is not None
    prompt = lia_tick_prompt_from_objective(raw)
    patch = lia_core3_context_patch(prompt=prompt)
    patch["_lia_job_actor"] = LIA_ACTOR_ID
    return ActionProposal(
        capability=cap.name,
        routed_to=cap.routed_to,
        action_context_key=cap.action_context_key or "core3_action",
        action=lia_core3_plan_action(prompt=prompt),
        context_patch=patch,
        summary="Faire jouer Lia en MMO (incarnation orchestrateur, action enqueue via sidecar).",
        risk_level=cap.risk_level,
        confidence=0.84,
    )


def _propose_capabilities_inventory(normalized: str) -> ActionProposal | None:
    """Liste / inventaire des agents (handlers) et capabilities du registry orchestrateur."""
    has_agents = re.search(r"\b(agents?|handlers?|services?)\b", normalized)
    has_caps = re.search(r"\b(capabilit[eé]s?|capabilities|fonctionnalit[eé]s?)\b", normalized)
    list_intent = re.search(
        r"\b(liste|lister|[eé]tablir|[eé]tablie|[eé]tablis|inventaire|disponible|disponibles|"
        r"registry|registre|quels?|quelles?|[eé]num[eè]re|affiche|montre)\b",
        normalized,
    )
    if not ((has_agents and has_caps) or (list_intent and (has_agents or has_caps))):
        return None
    cap = capability_registry.get("npc_dialogue")
    assert cap is not None
    return ActionProposal(
        capability=cap.name,
        routed_to=cap.routed_to,
        action_context_key=cap.action_context_key or "",
        action={},
        context_patch={"_capabilities_inventory": True},
        summary="Inventaire direct du registry (agents routed_to + capabilities), sans LLM.",
        risk_level=cap.risk_level,
        confidence=0.82,
    )


def _propose_network_inventory(normalized: str) -> ActionProposal | None:
    """Cartographie LAN / appareils — sondes read-only sur hôtes connus."""
    has_scope = re.search(
        r"\b(réseau|reseau|réseaux|reseaux|infra|infrastructure|appareil|appareils|"
        r"lan|vm|machines?|topologie|hôtes?|hotes?)\b",
        normalized,
    )
    has_intent = re.search(
        r"\b(inventaire|cartographie|cartograph|sond|découvr|decouvr|recens|"
        r"présents?|presents?|établir|établie|établis|analys|audit|carte)\b",
        normalized,
    )
    if not (has_scope and has_intent):
        return None
    cap = capability_registry.get("network_inventory")
    assert cap is not None
    return ActionProposal(
        capability=cap.name,
        routed_to=cap.routed_to,
        action_context_key=cap.action_context_key or "",
        action={},
        context_patch={},
        summary="Inventaire réseau LAN (sondes HTTP/TCP read-only sur core/front/mmo/desktop).",
        risk_level=cap.risk_level,
        confidence=0.8,
    )


def _propose_dialogue_consult(normalized: str, raw: str) -> ActionProposal | None:
    """Conseil / plan / explication sans action desktop ou devops destructive."""
    if re.search(
        r"\b(internet|recherche web|sur le web|ouvre|lance|sonde|selfcheck|healthz|notepad|vghd|"
        r"systemctl|ssh|desktop)\b",
        normalized,
    ):
        return None
    logs_intent = re.search(r"\b(logs?|journal|journalisation|logging|audit)\b", normalized) and re.search(
        r"\b(ajoute|ajouter|mettre|implémente|implemente|créer|creer|système|systeme|"
        r"débogage|debug|rétention|retention|facilit)\b",
        normalized,
    )
    advice_intent = re.search(
        r"\b(conseil|recommand|explique|décris|decris|propose|plan)\b.*\b(comment|quoi|où|ou)\b",
        normalized,
    ) or re.search(r"\b(comment|pourquoi)\b", normalized)
    if not (logs_intent or advice_intent):
        return None
    cap = capability_registry.get("npc_dialogue")
    assert cap is not None
    summary = (
        "Proposer un plan de journalisation (fichiers, format, rétention)."
        if logs_intent
        else "Répondre en langage naturel (conseil / orientation repo)."
    )
    return ActionProposal(
        capability=cap.name,
        routed_to=cap.routed_to,
        action_context_key=cap.action_context_key or "",
        action={},
        context_patch={"_dialogue_consult": True},
        summary=summary,
        risk_level=cap.risk_level,
        confidence=0.75,
    )


def _propose_web_search(raw: str, normalized: str) -> ActionProposal | None:
    if not re.search(r"\b(cherche|chercher|recherche|rechercher|trouve|internet|web|site)\b", normalized):
        return None
    # « chemin du fichier à modifier » n'est pas une recherche web.
    if re.search(r"\b(chemin|fichier|fichiers|path)\b", normalized) and not re.search(
        r"\b(internet|recherche web|sur le web|site web|google|duckduckgo)\b", normalized
    ):
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


_OPEN_APP_VERB_RE = re.compile(
    r"\b(?:ouvrir|ouvre|ouvrez|lancer|lance|lancez|demarrer|démarrer|demarrez|démarrez|start|launch|open)\b",
    re.IGNORECASE,
)

_OPEN_APP_STOP_TOKENS = frozenset(
    {
        "le",
        "la",
        "les",
        "un",
        "une",
        "the",
        "a",
        "an",
        "mon",
        "ma",
        "mes",
        "ton",
        "ta",
        "tes",
        "son",
        "sa",
        "ses",
        "my",
        "your",
        "ce",
        "cette",
        "cet",
        "sur",
        "avec",
        "pour",
        "dans",
        "application",
        "appli",
        "app",
        "programme",
        "exe",
        "pc",
        "ordinateur",
    },
)


def _sanitize_open_app_slug(raw_tail: str) -> str | None:
    """Nom court sans chemin / URL ; aligné sur la validation dialogue ``open_app``."""
    t = raw_tail.strip().strip("\"'«»")
    if not t or re.search(r"https?://", t):
        return None
    if "\\" in t or "/" in t or ".." in t:
        return None
    first = re.split(r"\s+", t, maxsplit=1)[0].strip("\"'«»")
    if not first:
        return None
    if len(first) > 80:
        first = first[:80]
    if not re.match(r"^[A-Za-z0-9_.\-]+$", first):
        return None
    if first.lower() in _OPEN_APP_STOP_TOKENS:
        return None
    return first


def _propose_open_app(raw: str, normalized: str) -> ActionProposal | None:
    """
    Ouverture / lancement d'une application locale (``kind``: ``open_app`` côté worker).
    """
    if not _OPEN_APP_VERB_RE.search(normalized):
        return None
    matches = list(_OPEN_APP_VERB_RE.finditer(raw))
    if not matches:
        return None
    last_match = matches[-1]
    tail = raw[last_match.end() :].strip()
    if not tail:
        return None
    tail = re.sub(
        r"^\s*(?:l['′'])?\s*(?:application|appli|prog|programme)\s+",
        "",
        tail,
        flags=re.IGNORECASE,
    ).strip()
    tail_chunk = re.split(r"\s+(?:sur|on|avec|pour|dans)\s+", tail, maxsplit=1)[0].strip()
    slug = _sanitize_open_app_slug(tail_chunk)
    if not slug:
        return None
    # Enrichissement rapatrié de P03 : alias (notepad→notepadpp, swg→swgemu…),
    # chemin .exe fourni dans l'objectif, et learn:true par défaut (allowlist auto sur le worker).
    action: dict[str, object] = {"kind": "open_app", "app": slug, "args": []}
    exe = extract_exe_path_from_goal(raw)
    if exe:
        action["command"] = exe
    action = enrich_open_app_action(action)
    app_label = action.get("app", slug)
    target = infer_desktop_target_from_text(raw)
    summary = f"Préparer l'ouverture de « {app_label} » via desktop_control (dry-run jusqu'à exécution)."
    if target == "ad":
        summary = f"Préparer l'ouverture de « {app_label} » sur le serveur AD (desktop_control, dry-run)."
    return _desktop_proposal(
        action=action,
        summary=summary,
        confidence=0.84,
        text=raw,
    )


def _propose_job_synthesis(normalized: str) -> ActionProposal | None:
    """Synthèse NL après une étape technique (ex. selfcheck) — le job injecte les résultats précédents."""
    if not re.search(
        r"\b(dis[- ]?moi|dire|explique|résume|resume|synthèse|synthese|amélior|amelior|recommand|liste|présente|presente)\b",
        normalized,
    ):
        return None
    if not re.search(
        r"\b(ce\s+qui|quoi|comment|pistes|suggestions|résultat|resultat|checkup|selfcheck|étapes?|infra|devops|"
        r"état|etat|l['\u2019]état|l['\u2019]etat)\b",
        normalized,
    ):
        return None
    cap = capability_registry.get("npc_dialogue")
    assert cap is not None
    return ActionProposal(
        capability=cap.name,
        routed_to=cap.routed_to,
        action_context_key=cap.action_context_key or "",
        action={},
        context_patch={"_job_synthesis": True},
        summary="Synthèse en français à partir des résultats des étapes précédentes du job.",
        risk_level=cap.risk_level,
        confidence=0.8,
    )


def _propose_vm_memory_probe(normalized: str) -> ActionProposal | None:
    if not re.search(r"\b(mémoire|memoire|memory|ram|swap|consommation)\b", normalized):
        return None
    if not re.search(
        r"\b(supervis|surveill|contrôl|control|sond|analys|audit|compare|état|etat|"
        r"fuites?|libér|liber|charge|chargement)\b",
        normalized,
    ):
        return None
    cap = capability_registry.get("devops_probe")
    assert cap is not None
    return ActionProposal(
        capability=cap.name,
        routed_to=cap.routed_to,
        action_context_key=cap.action_context_key or "devops_action",
        action={"kind": "vm_memory_probe"},
        context_patch={"devops_action": {"kind": "vm_memory_probe"}},
        summary="Sonde mémoire read-only (SSH) sur Prime 246, PreCU 245, front 110, core 140.",
        risk_level=cap.risk_level,
        confidence=0.84,
    )


def _propose_proxmox_status(normalized: str) -> ActionProposal | None:
    if not re.search(r"\b(proxmox|hyperviseur|hypervisor|pve)\b", normalized):
        return None
    if not re.search(
        r"\b(état|etat|status|supervis|surveill|vm|cluster|ressources?|charge)\b",
        normalized,
    ):
        return None
    cap = capability_registry.get("devops_probe")
    assert cap is not None
    return ActionProposal(
        capability=cap.name,
        routed_to=cap.routed_to,
        action_context_key=cap.action_context_key or "devops_action",
        action={"kind": "proxmox_status"},
        context_patch={"devops_action": {"kind": "proxmox_status"}},
        summary="Sonde Proxmox read-only (cluster, VMs LAN core/front/precu/prime).",
        risk_level=cap.risk_level,
        confidence=0.83,
    )


def _propose_infra_selfcheck(normalized: str) -> ActionProposal | None:
    # « résume l'état » etc. → synthèse dialogue, pas un second selfcheck.
    if re.search(r"\b(résume|resume|synthèse|synthese|explique|dis[- ]?moi)\b", normalized):
        return None
    # Formulations courantes « auto checkup / bilan » (sans mot « devops » explicite).
    if re.search(
        r"\b(auto[-\s]?check[-\s]?up|check[-\s]?up|checkup|bilan\s+(?:de\s+)?santé|bilan\s+sante)\b",
        normalized,
    ):
        cap = capability_registry.get("devops_probe")
        assert cap is not None
        return ActionProposal(
            capability=cap.name,
            routed_to=cap.routed_to,
            action_context_key=cap.action_context_key or "devops_action",
            action={"kind": "selfcheck"},
            context_patch={"devops_action": {"kind": "selfcheck"}},
            summary="Préparer un selfcheck DevOps read-only (formulation checkup/bilan).",
            risk_level=cap.risk_level,
            confidence=0.82,
        )
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


def _desktop_proposal(
    *,
    action: dict[str, object],
    summary: str,
    confidence: float,
    text: str = "",
) -> ActionProposal:
    cap = capability_registry.get("desktop_control")
    assert cap is not None
    patch: dict[str, object] = {"desktop_action": action, "desktop_dry_run": True}
    target = infer_desktop_target_from_text(text)
    if target:
        patch["desktop_target"] = target
    return ActionProposal(
        capability=cap.name,
        routed_to=cap.routed_to,
        action_context_key=cap.action_context_key or "desktop_action",
        action=action,
        context_patch=patch,
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
