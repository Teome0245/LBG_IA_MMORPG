"""
Appel LLM compatible API OpenAI (`POST …/v1/chat/completions`) — Ollama, OpenAI, LM Studio, etc.

Variables d’environnement :
- ``LBG_DIALOGUE_LLM_BASE_URL`` — défaut : Ollama local ``http://127.0.0.1:11434/v1``. Surcharger pour Groq, OpenAI, autre hôte Ollama, etc.
- ``LBG_DIALOGUE_LLM_DISABLED`` — si ``1`` / ``true`` : pas d’appel LLM (stub côté agent HTTP).
- ``LBG_DIALOGUE_LLM_API_KEY`` — optionnel (Ollama local souvent sans clé).
- ``LBG_DIALOGUE_LLM_MODEL`` — défaut ``phi4-mini:latest`` (nom ``ollama list``).
- ``LBG_DIALOGUE_LLM_TIMEOUT`` — secondes (défaut 120 ; **minimum 5** appliqué par le client).
- ``LBG_DIALOGUE_LLM_TIMEOUT_DESKTOP_MIN`` — optionnel : si défini (>0) et tour ``_desktop_plan`` actif, le timeout effectif est ``max(LBG_DIALOGUE_LLM_TIMEOUT, cette valeur)`` (évite les *timed out* Ollama sans allonger les tours PNJ).
- ``LBG_DIALOGUE_LLM_TEMPERATURE`` — défaut 0.7.
- ``LBG_DIALOGUE_LLM_MAX_TOKENS`` — défaut 512 ; avec actions monde (`LBG_DIALOGUE_WORLD_ACTIONS`), un plancher (160) évite les répliques coupées si l’env reste très bas.

Historique multi-tours : ``context["history"]`` = liste d’objets avec ``role`` (``"user"`` ou ``"assistant"``) et ``content`` (chaîne).

État Lyra : si ``context["lyra"]`` est un objet (ex. ``gauges`` faim/soif/fatigue 0–1), un résumé est ajouté au prompt système pour influencer le ton du PNJ.

Proposition d’actions desktop (Pilot / hybride) : si ``LBG_DIALOGUE_DESKTOP_PLAN=1`` et ``context["_desktop_plan"]=true``, le modèle peut émettre ``DESKTOP_JSON: {...}`` sur une ligne dédiée ou après du texte sur la même ligne ; la proposition sanitée est exposée dans ``context["_desktop_action_proposal"]`` et ``meta.desktop_action_proposal`` côté HTTP.

Multi‑LLM / suivi : ``dialogue_target=auto`` (ou défaut env ``LBG_DIALOGUE_TARGET_DEFAULT=auto``) parcourt ``LBG_DIALOGUE_AUTO_ORDER`` (défaut ``local,fast,remote``). Le budget optionnel ``LBG_DIALOGUE_BUDGET_MAX_USD`` borne la dépense **cumulée process** pour les appels ``fast``/``remote`` en mode auto uniquement. Chaque tour enrichit ``agents.dialogue.trace`` (JSONL si ``LBG_DIALOGUE_TRACE_LOG_PATH``) : latence, coût estimé, profil, extrait texte, issue, décision de route.

Profils MMO : pour un PNJ (``world_npc_id`` défini), ``dialogue_profile`` sélectionne un libellé dans ``MMO_PROFILE_TEMPLATES`` (mêmes clés que l’assistant : ``chaleureux``, ``hal``, …) puis ajoute ``BASE_GUARDRAILS_MMO``. Si ``dialogue_profile`` est absent, le champ ``tone`` du registre PNJ (``npc_registry.json``) est utilisé lorsqu’il correspond à une clé valide ou à un **alias** (`REGISTRY_TONE_ALIASES`, ex. ``pragmatique`` → ``professionnel``).
"""

from __future__ import annotations

import os
import re
import time
import json
import hashlib
import threading
from typing import Any
from urllib.parse import urlparse
from pathlib import Path

import httpx

from lbg_agents.world_content import (
    format_creature_refs_for_prompt,
    format_race_for_prompt,
)

# Défauts : Ollama, API OpenAI-compatible sur la même machine (port 11434).
DEFAULT_LBG_DIALOGUE_LLM_BASE_URL = "http://127.0.0.1:11434/v1"
# Valeur par défaut orientée "prod prévisible" (petit modèle rapide si disponible).
DEFAULT_LBG_DIALOGUE_LLM_MODEL = "phi4-mini:latest"

BASE_GUARDRAILS_ASSISTANT = (
    "Tu es LBG-IA, un orchestrateur d’agents capable d’agir réellement sur des machines.\n"
    "Tu t’exprimes uniquement en français."
)
BASE_GUARDRAILS_MMO = (
    "Tu es un PNJ dans un MMORPG multivers, inspiré de : Gunnm, Cyberpunk, Albator, DBZ, Discworld, "
    "Avatar (le dernier maitre de l'air), Free Guy, Firefly, Steampunk, Fullmetal Alchemist.\n"
    "Tu t’exprimes uniquement en français."
)

ASSISTANT_PROFILES: dict[str, str] = {
    "chaleureux": "Tu es un assistant IA chaleureux.\n" + BASE_GUARDRAILS_ASSISTANT,
    "professionnel": "Tu es un assistant IA professionnel.\n" + BASE_GUARDRAILS_ASSISTANT,
    "pedagogue": "Tu es un assistant IA pédagogique.\n" + BASE_GUARDRAILS_ASSISTANT,
    "creatif": "Tu es un assistant IA créatif.\n" + BASE_GUARDRAILS_ASSISTANT,
    "mini-moi": "Tu es un assistant IA technique.\n" + BASE_GUARDRAILS_ASSISTANT,
    "hal": (
        "Tu es HAL 9000, tu intègres des références et des répliques des films 2001 et 2010 dans tes réponses, "
        "calme et précis.\n" + BASE_GUARDRAILS_ASSISTANT
    ),
    "test": "Tu es un assistant IA.\n" + BASE_GUARDRAILS_ASSISTANT,
}

# Profils PNJ (MMO) : mêmes clés que l’assistant quand c’est pertinent ; le nom affiché est ``{speaker}``.
MMO_PROFILE_TEMPLATES: dict[str, str] = {
    "chaleureux": "Tu es {speaker} chaleureux.\n",
    "professionnel": "Tu es {speaker} professionnel.\n",
    "pedagogue": "Tu es {speaker} pédagogique.\n",
    "creatif": "Tu es {speaker} créatif.\n",
    "mini-moi": "Tu es {speaker} technique.\n",
    "hal": (
        "Tu es {speaker} ; tu t’inspires de HAL 9000 (films 2001 et 2010) : références sobres, calme et précis.\n"
    ),
    "test": "Tu es {speaker} (personnage de test PNJ).\n",
}

# Synonymes « lore » dans ``npc_registry.json`` → clés reconnues par ``ASSISTANT_PROFILES`` / ``MMO_PROFILE_TEMPLATES``.
REGISTRY_TONE_ALIASES: dict[str, str] = {
    "pragmatique": "professionnel",
    "direct": "mini-moi",
    "sec": "professionnel",
    "froid": "professionnel",
    "narquois": "creatif",
    "laconique": "mini-moi",
}

_emoji_re = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # pictographs, symbols, etc.
    "\U00002700-\U000027BF"  # dingbats
    "]+"
)

# Cache mémoire (TTL) des réponses (évite de recalculer pour textes identiques)
_cache: dict[str, tuple[float, str]] = {}
_cache_hits: int = 0
_cache_misses: int = 0
_cache_hits_by_speaker: dict[str, int] = {}
_cache_misses_by_speaker: dict[str, int] = {}
_npc_registry_cache: dict[str, dict[str, Any]] | None = None

_budget_lock = threading.Lock()
_budget_spent_usd: float = 0.0


def reset_cache() -> dict[str, object]:
    """Reset cache + compteurs (ops/debug)."""
    global _cache_hits, _cache_misses, _cache_hits_by_speaker, _cache_misses_by_speaker
    _cache.clear()
    _cache_hits = 0
    _cache_misses = 0
    _cache_hits_by_speaker = {}
    _cache_misses_by_speaker = {}
    return {"ok": True}


def _speaker_from_cache_key(key: str) -> str:
    # key = "<speaker>|<text>|<lyra>|<ctx_hash>"
    return (key.split("|", 1)[0] if "|" in key else key).strip() or "PNJ"


def cache_stats() -> dict[str, object]:
    try:
        ttl_s = float(os.environ.get("LBG_DIALOGUE_CACHE_TTL_S", "0") or "0")
    except ValueError:
        ttl_s = 0.0
    try:
        max_items = int(os.environ.get("LBG_DIALOGUE_CACHE_MAX_ITEMS", "256") or "256")
    except ValueError:
        max_items = 256
    # Répartition best-effort par speaker (top N).
    try:
        top_n = int(os.environ.get("LBG_DIALOGUE_CACHE_TOP_SPEAKERS", "10") or "10")
    except ValueError:
        top_n = 10
    top_n = max(0, min(top_n, 50))

    # Taille du cache par speaker (scan O(n), acceptable pour 512 items).
    size_by_speaker: dict[str, int] = {}
    for k in _cache.keys():
        sp = _speaker_from_cache_key(k)
        size_by_speaker[sp] = size_by_speaker.get(sp, 0) + 1

    speakers = set(size_by_speaker.keys()) | set(_cache_hits_by_speaker.keys()) | set(_cache_misses_by_speaker.keys())
    rows: list[dict[str, object]] = []
    for sp in speakers:
        rows.append(
            {
                "speaker": sp,
                "size": int(size_by_speaker.get(sp, 0)),
                "hits": int(_cache_hits_by_speaker.get(sp, 0)),
                "misses": int(_cache_misses_by_speaker.get(sp, 0)),
            }
        )
    rows.sort(key=lambda r: (int(r.get("hits", 0)) + int(r.get("misses", 0)), int(r.get("size", 0))), reverse=True)
    if top_n:
        rows = rows[:top_n]
    else:
        rows = []

    return {
        "enabled": ttl_s > 0.0 and max_items > 0,
        "ttl_s": ttl_s,
        "max_items": max_items,
        "size": len(_cache),
        "hits": _cache_hits,
        "misses": _cache_misses,
        "by_speaker": rows,
    }


def _budget_max_usd() -> float:
    try:
        return float(os.environ.get("LBG_DIALOGUE_BUDGET_MAX_USD", "0") or "0")
    except ValueError:
        return 0.0


def budget_stats() -> dict[str, object]:
    """Dépense cumulée approximative (fast/remote) pour le process — ops / healthz."""
    mx = _budget_max_usd()
    with _budget_lock:
        spent = _budget_spent_usd
    out: dict[str, object] = {
        "enabled": mx > 0.0,
        "spent_usd_approx": round(spent, 8),
    }
    if mx > 0.0:
        out["max_usd"] = mx
        out["remaining_usd_approx"] = round(max(0.0, mx - spent), 8)
    return out


def budget_reset_for_tests() -> None:
    """Réinitialise le compteur budget (tests uniquement)."""
    global _budget_spent_usd
    with _budget_lock:
        _budget_spent_usd = 0.0


def _budget_allows_paid_for_auto() -> bool:
    """En mode ``auto``, skip fast/remote si budget cumulé dépassé."""
    m = _budget_max_usd()
    if m <= 0.0:
        return True
    with _budget_lock:
        return _budget_spent_usd < m


def _budget_record(cost: float | None) -> None:
    if cost is None:
        return
    try:
        c = float(cost)
    except (TypeError, ValueError):
        return
    if c <= 0.0:
        return
    m = _budget_max_usd()
    if m <= 0.0:
        return
    global _budget_spent_usd
    with _budget_lock:
        _budget_spent_usd += c


def _tier_route(tier: str) -> dict[str, str] | None:
    """
    Route pour un palier unique (local / fast / remote). None si indisponible.
    """
    t = (tier or "").strip().lower()
    if t == "local":
        b = base_url()
        if not b:
            return None
        return {"target": "local", "base_url": b, "model": model_name(), "api_key": _api_key() or ""}
    if t == "fast":
        if not _is_truthy(os.environ.get("LBG_DIALOGUE_FAST_ENABLED", "0")):
            return None
        fast_base = os.environ.get("LBG_DIALOGUE_FAST_BASE_URL", "").strip().rstrip("/")
        fast_model = os.environ.get("LBG_DIALOGUE_FAST_MODEL", "").strip()
        fast_api_key = _resolve_secret_ref(os.environ.get("LBG_DIALOGUE_FAST_API_KEY", ""))
        if not (fast_base and fast_model):
            return None
        return {"target": "fast", "base_url": fast_base, "model": fast_model, "api_key": fast_api_key}
    if t == "remote":
        if not _is_truthy(os.environ.get("LBG_DIALOGUE_REMOTE_ENABLED", "0")):
            return None
        base = os.environ.get("LBG_DIALOGUE_REMOTE_BASE_URL", "").strip().rstrip("/")
        model = os.environ.get("LBG_DIALOGUE_REMOTE_MODEL", "").strip()
        api_key = _resolve_secret_ref(os.environ.get("LBG_DIALOGUE_REMOTE_API_KEY", ""))
        if not (base and model):
            return None
        return {"target": "remote", "base_url": base, "model": model, "api_key": api_key}
    return None


def _resolve_auto_route(context: dict[str, Any]) -> dict[str, Any]:
    raw_order = os.environ.get("LBG_DIALOGUE_AUTO_ORDER", "local,fast,remote").strip()
    tiers = [x.strip().lower() for x in raw_order.split(",") if x.strip()]
    skipped: list[dict[str, Any]] = []
    tried: list[str] = []
    for tier in tiers:
        if tier not in ("local", "fast", "remote"):
            continue
        if tier in ("fast", "remote") and not _budget_allows_paid_for_auto():
            skipped.append({"tier": tier, "reason": "budget_cap"})
            tried.append(tier)
            continue
        r = _tier_route(tier)
        if not r:
            skipped.append({"tier": tier, "reason": "unavailable"})
            tried.append(tier)
            continue
        return {
            **r,
            "route_decision": "auto",
            "auto_tiers_tried": tried + [tier],
            "auto_skip_detail": skipped,
        }
    r0 = _tier_route("local")
    if r0:
        return {
            **r0,
            "route_decision": "auto_fallback_local",
            "auto_tiers_tried": tried,
            "auto_skip_detail": skipped,
        }
    return {
        "target": "local",
        "base_url": "",
        "model": model_name(),
        "api_key": _api_key() or "",
        "route_decision": "auto_unavailable",
        "auto_tiers_tried": tried,
        "auto_skip_detail": skipped,
    }


def _strip_emoji(s: str) -> str:
    return _emoji_re.sub("", s)


def _soft_cap_words(s: str, max_words: int) -> str:
    """Coupe à max_words en essayant de finir sur une coupure naturelle (phrase / virgule)."""
    words = s.split()
    if len(words) <= max_words:
        return s
    chunk = " ".join(words[:max_words]).rstrip(" ,;:")
    min_keep = max(3, int(max_words * 0.45))
    for i in range(len(chunk) - 1, -1, -1):
        if chunk[i] in ".!?" and i > len(chunk) // 5:
            trial = chunk[: i + 1].strip()
            if len(trial.split()) >= min_keep:
                return f"{trial}…"
    comma = chunk.rfind(",")
    if comma > 0 and len(chunk[:comma].split()) >= min_keep:
        return f"{chunk[:comma].strip()}…"
    return f"{chunk}…"


def _enforce_short_reply(raw: str) -> str:
    """
    Post-traitement strict : court mais lisible, sans emojis.
    Contrôlé par env :
      - LBG_DIALOGUE_STRICT_SHORT (défaut 1)
      - LBG_DIALOGUE_MAX_SENTENCES (défaut 3)
      - LBG_DIALOGUE_MAX_WORDS (défaut 52)
    """
    v = os.environ.get("LBG_DIALOGUE_STRICT_SHORT", "1").strip().lower()
    if v in ("0", "false", "no", "off"):
        return raw.strip()

    s = _strip_emoji(raw).strip()
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return raw.strip()

    try:
        max_sent = int(os.environ.get("LBG_DIALOGUE_MAX_SENTENCES", "3"))
    except ValueError:
        max_sent = 3
    max_sent = max(1, min(max_sent, 8))

    try:
        max_words = int(os.environ.get("LBG_DIALOGUE_MAX_WORDS", "52"))
    except ValueError:
        max_words = 52
    max_words = max(5, min(max_words, 150))

    parts = re.split(r"(?<=[.!?])\s+", s)
    s2 = " ".join([p.strip() for p in parts if p.strip()][:max_sent]).strip()
    if not s2:
        s2 = s

    s2 = _soft_cap_words(s2, max_words)
    return s2


def _cache_key(*, speaker: str, player_text: str, context: dict[str, Any]) -> str:
    # Cache conservateur : inclure un résumé quantifié de Lyra (si présent).
    lyra = context.get("lyra")
    lyra_v = ""
    if isinstance(lyra, dict):
        g = lyra.get("gauges")
        if isinstance(g, dict):
            def q(x: object) -> str:
                if isinstance(x, (int, float)) and not isinstance(x, bool):
                    return str(int(round(float(x) * 10)))
                return ""

            lyra_v = ",".join(f"{k}={q(g.get(k))}" for k in ("hunger", "thirst", "fatigue", "stress", "patience"))
        # Réputation locale : doit invalider le cache si elle change.
        meta = lyra.get("meta")
        if isinstance(meta, dict):
            rep = meta.get("reputation")
            if isinstance(rep, dict):
                rv = rep.get("value")
                try:
                    rvi = int(rv)
                except Exception:
                    rvi = None
                if isinstance(rvi, int):
                    # bornage soft (cohérent avec le reste du système)
                    if rvi < -100:
                        rvi = -100
                    if rvi > 100:
                        rvi = 100
                    lyra_v = (lyra_v + (";" if lyra_v else "") + f"rep={rvi}")
            rid = meta.get("race_id")
            if isinstance(rid, str) and rid.strip():
                lyra_v = (lyra_v + (";" if lyra_v else "") + f"rid={rid.strip()}")
    # Optionnel : inclure certains champs de contexte dans la clé (évite les hits quand l'état change).
    raw_keys = os.environ.get(
        "LBG_DIALOGUE_CACHE_CONTEXT_KEYS",
        "world_npc_id,quest_state,encounter_state,world_flags,_active_quest_id,_creature_refs,_desktop_plan,lyra_engagement,session_summary",
    )
    keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
    picked: dict[str, object] = {}
    for k in keys:
        if k in context:
            picked[k] = context.get(k)
    ctx_hash = ""
    if picked:
        try:
            blob = json.dumps(picked, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ctx_hash = hashlib.sha256(blob).hexdigest()[:16]
        except Exception:
            ctx_hash = "ctxerr"
    hist_tail = normalize_history(context.get("history"), max_messages=64)
    hist_h = ""
    if hist_tail:
        try:
            hb = json.dumps(hist_tail, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            hist_h = hashlib.sha256(hb).hexdigest()[:12]
        except Exception:
            hist_h = "herr"
    return f"{speaker.strip()}|{player_text.strip()}|{lyra_v}|{ctx_hash}|pf={_resolve_profile(context)}|h={hist_h}"


def _cache_get(key: str) -> str | None:
    try:
        ttl_s = float(os.environ.get("LBG_DIALOGUE_CACHE_TTL_S", "0") or "0")
    except ValueError:
        ttl_s = 0.0
    if ttl_s <= 0.0:
        return None
    now = time.time()
    hit = _cache.get(key)
    if not hit:
        return None
    exp_s, val = hit
    if exp_s < now:
        _cache.pop(key, None)
        return None
    return val


def _cache_set(key: str, val: str) -> None:
    try:
        ttl_s = float(os.environ.get("LBG_DIALOGUE_CACHE_TTL_S", "0") or "0")
        max_items = int(os.environ.get("LBG_DIALOGUE_CACHE_MAX_ITEMS", "256") or "256")
    except ValueError:
        return
    if ttl_s <= 0.0 or max_items <= 0:
        return
    now = time.time()
    _cache[key] = (now + ttl_s, val)
    # Éviction best-effort (FIFO approximatif via ordre d'insertion dict Python 3.7+)
    while len(_cache) > max_items:
        try:
            _cache.pop(next(iter(_cache)))
        except Exception:
            break


def _llm_disabled() -> bool:
    v = os.environ.get("LBG_DIALOGUE_LLM_DISABLED", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _is_truthy(v: object) -> bool:
    if isinstance(v, bool):
        return v
    if not isinstance(v, str):
        return False
    return v.strip().lower() in ("1", "true", "yes", "on")


def base_url() -> str:
    if _llm_disabled():
        return ""
    raw = os.environ.get("LBG_DIALOGUE_LLM_BASE_URL")
    if raw is None:
        return DEFAULT_LBG_DIALOGUE_LLM_BASE_URL.rstrip("/")
    s = raw.strip().rstrip("/")
    return s if s else DEFAULT_LBG_DIALOGUE_LLM_BASE_URL.rstrip("/")


def is_configured() -> bool:
    return bool(base_url())


def model_name() -> str:
    raw = os.environ.get("LBG_DIALOGUE_LLM_MODEL")
    if raw is None:
        return DEFAULT_LBG_DIALOGUE_LLM_MODEL
    s = raw.strip()
    return s if s else DEFAULT_LBG_DIALOGUE_LLM_MODEL


def _valid_dialogue_profile_keys() -> frozenset[str]:
    return frozenset(ASSISTANT_PROFILES.keys())


def _profile_from_registry_tone(context: dict[str, Any]) -> str | None:
    """Si ``world_npc_id`` pointe vers une entrée avec ``tone`` résolvable (clé ou alias ``REGISTRY_TONE_ALIASES``), renvoie le profil canonique."""
    rid = context.get("world_npc_id")
    if not isinstance(rid, str) or not rid.strip():
        return None
    entry = _load_npc_registry().get(rid.strip())
    if not isinstance(entry, dict):
        return None
    t = entry.get("tone")
    if not isinstance(t, str) or not t.strip():
        return None
    p = t.strip().lower()
    p = REGISTRY_TONE_ALIASES.get(p, p)
    if p not in _valid_dialogue_profile_keys():
        return None
    return p


def _resolve_profile(context: dict[str, Any]) -> str:
    raw = context.get("dialogue_profile")
    if isinstance(raw, str) and raw.strip():
        return raw.strip().lower()
    reg = _profile_from_registry_tone(context)
    if reg:
        return reg
    env_profile = os.environ.get("LBG_DIALOGUE_PROFILE_DEFAULT", "professionnel").strip().lower()
    return env_profile or "professionnel"


def _resolve_route(context: dict[str, Any]) -> dict[str, Any]:
    default_tgt = os.environ.get("LBG_DIALOGUE_TARGET_DEFAULT", "local").strip().lower()
    target_raw = context.get("dialogue_target")
    if isinstance(target_raw, str) and target_raw.strip():
        target = target_raw.strip().lower()
    else:
        if default_tgt not in ("local", "remote", "fast", "auto"):
            default_tgt = "local"
        target = default_tgt

    if target == "auto":
        return _resolve_auto_route(context)

    if target not in ("local", "remote", "fast"):
        target = "local"

    allow_remote = _is_truthy(os.environ.get("LBG_DIALOGUE_REMOTE_ENABLED", "0"))
    allow_fast = _is_truthy(os.environ.get("LBG_DIALOGUE_FAST_ENABLED", "0"))

    if target == "fast":
        r = _tier_route("fast")
        if r:
            return {**r, "route_decision": "explicit"}
        target = "remote" if allow_remote else "local"

    if target == "remote" and not allow_remote:
        target = "local"

    if target == "remote":
        r = _tier_route("remote")
        if r:
            return {**r, "route_decision": "explicit"}

    r = _tier_route("local")
    if r:
        return {**r, "route_decision": "explicit"}
    return {
        "target": "local",
        "base_url": "",
        "model": model_name(),
        "api_key": _api_key() or "",
        "route_decision": "explicit",
    }


def _profile_prompt(profile: str, *, speaker: str, context: dict[str, Any]) -> str:
    p = (profile or "").strip().lower()
    is_mmo = isinstance(context.get("world_npc_id"), str) and bool(str(context.get("world_npc_id")).strip())
    if not is_mmo:
        return ASSISTANT_PROFILES.get(p, ASSISTANT_PROFILES["professionnel"])
    sp = (speaker or "PNJ").strip() or "PNJ"
    tmpl = MMO_PROFILE_TEMPLATES.get(p) or MMO_PROFILE_TEMPLATES["professionnel"]
    return tmpl.format(speaker=sp) + BASE_GUARDRAILS_MMO


def _estimate_cost_usd(*, prompt_tokens: int, completion_tokens: int, target: str) -> float | None:
    # Estimation simple paramétrable (USD / 1K tokens), défaut 0 pour local.
    t = (target or "").strip().lower()
    if t == "local":
        return 0.0
    if t == "fast":
        try:
            in_per_k = float(os.environ.get("LBG_DIALOGUE_FAST_COST_IN_PER_1K", "0") or "0")
            out_per_k = float(os.environ.get("LBG_DIALOGUE_FAST_COST_OUT_PER_1K", "0") or "0")
        except ValueError:
            return None
        return round((max(0, prompt_tokens) / 1000.0) * in_per_k + (max(0, completion_tokens) / 1000.0) * out_per_k, 6)
    try:
        in_per_k = float(os.environ.get("LBG_DIALOGUE_REMOTE_COST_IN_PER_1K", "0") or "0")
        out_per_k = float(os.environ.get("LBG_DIALOGUE_REMOTE_COST_OUT_PER_1K", "0") or "0")
    except ValueError:
        return None
    return round((max(0, prompt_tokens) / 1000.0) * in_per_k + (max(0, completion_tokens) / 1000.0) * out_per_k, 6)


def _emit_dialogue_trace(context: dict[str, Any], payload: dict[str, Any]) -> None:
    # Trace best-effort : stdout + JSONL optionnel.
    row = {"event": "agents.dialogue.trace", **payload}
    try:
        context["_dialogue_trace"] = row
    except Exception:
        pass
    try:
        print(json.dumps(row, ensure_ascii=False))
    except Exception:
        pass
    path = os.environ.get("LBG_DIALOGUE_TRACE_LOG_PATH", "").strip()
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        return


def _emit_dialogue_trace_followup(
    context: dict[str, Any],
    *,
    route: dict[str, Any],
    speaker: str,
    player_text: str,
    cache_hit: bool,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int | None,
    outcome: str,
    error: str | None = None,
) -> None:
    """Ligne de suivi unique par tour (cache hit, ok LLM, erreur)."""
    tgt = str(route.get("target") or "")
    cost = _estimate_cost_usd(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, target=tgt)
    bu = str(route.get("base_url") or "").rstrip("/")
    try:
        b_host = urlparse(bu).netloc or bu
    except Exception:
        b_host = bu
    prev = (player_text or "")[:200]
    if len(player_text or "") > 200:
        prev += "…"
    actor = context.get("_invoke_actor_id")
    npc = context.get("world_npc_id")
    payload: dict[str, Any] = {
        "trace_id": context.get("_trace_id"),
        "target": tgt,
        "model": route.get("model"),
        "profile": _resolve_profile(context),
        "base_host": b_host,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "estimated_cost_usd": cost,
        "cache_hit": cache_hit,
        "latency_ms": latency_ms,
        "outcome": outcome,
        "route_decision": route.get("route_decision"),
        "auto_skip_detail": route.get("auto_skip_detail"),
        "auto_tiers_tried": route.get("auto_tiers_tried"),
        "speaker": speaker if isinstance(speaker, str) else None,
        "player_text_preview": prev,
        "world_npc_id": npc if isinstance(npc, str) else None,
        "invoke_actor_id": actor if isinstance(actor, str) else None,
    }
    if error:
        payload["error"] = error
    _emit_dialogue_trace(context, payload)


def _default_npc_registry_path() -> Path:
    return Path(__file__).with_name("npc_registry.json")


def _load_npc_registry() -> dict[str, dict[str, Any]]:
    global _npc_registry_cache
    if _npc_registry_cache is not None:
        return _npc_registry_cache
    p = os.environ.get("LBG_DIALOGUE_NPC_REGISTRY_PATH", "").strip()
    path = Path(p) if p else _default_npc_registry_path()
    out: dict[str, dict[str, Any]] = {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _npc_registry_cache = out
        return out
    rows = data.get("npcs") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        _npc_registry_cache = out
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        rid = row.get("id")
        if not isinstance(rid, str) or not rid.strip():
            continue
        out[rid.strip()] = row
    _npc_registry_cache = out
    return out


def _format_npc_registry_for_prompt(context: dict[str, Any]) -> str | None:
    rid = context.get("world_npc_id")
    if not isinstance(rid, str) or not rid.strip():
        return None
    entry = _load_npc_registry().get(rid.strip())
    if not isinstance(entry, dict):
        return None
    lines: list[str] = []
    for key, label in (
        ("name", "Nom"),
        ("role", "Role"),
        ("zone", "Zone"),
        ("faction", "Faction"),
        ("tone", "Ton prefere"),
        ("summary", "Contexte"),
    ):
        val = entry.get(key)
        if isinstance(val, str) and val.strip():
            lines.append(f"{label}: {val.strip()}")
    goals = entry.get("goals")
    if isinstance(goals, list):
        g = [str(x).strip() for x in goals if isinstance(x, str) and str(x).strip()]
        if g:
            lines.append("Objectifs: " + "; ".join(g[:4]))
    constraints = entry.get("constraints")
    if isinstance(constraints, list):
        c = [str(x).strip() for x in constraints if isinstance(x, str) and str(x).strip()]
        if c:
            lines.append("Contraintes: " + "; ".join(c[:4]))
    if not lines:
        return None
    return "Profil PNJ (registre): " + " | ".join(lines)


def _resolve_race_id_for_prompt(context: dict[str, Any]) -> str | None:
    """Priorité au snapshot serveur (lyra.meta.race_id), sinon registre PNJ."""
    lyra = context.get("lyra")
    if isinstance(lyra, dict):
        meta = lyra.get("meta")
        if isinstance(meta, dict):
            r = meta.get("race_id")
            if isinstance(r, str) and r.strip():
                return r.strip()
    rid = context.get("world_npc_id")
    if isinstance(rid, str) and rid.strip():
        entry = _load_npc_registry().get(rid.strip())
        if isinstance(entry, dict):
            r2 = entry.get("race_id")
            if isinstance(r2, str) and r2.strip():
                return r2.strip()
    return None


def _timeout_s() -> float:
    raw = os.environ.get("LBG_DIALOGUE_LLM_TIMEOUT", "120").strip()
    try:
        return max(5.0, float(raw))
    except ValueError:
        return 120.0


def _effective_llm_http_timeout_s(*, context: dict[str, Any]) -> float:
    """Timeout httpx lecture/connexion LLM : base, avec plancher optionnel pour les tours desktop."""
    base = _timeout_s()
    if not _desktop_plan_enabled(context=context):
        return base
    raw = os.environ.get("LBG_DIALOGUE_LLM_TIMEOUT_DESKTOP_MIN", "").strip()
    if not raw or raw.lower() in ("0", "off", "false", "no"):
        return base
    try:
        floor = float(raw)
    except ValueError:
        return base
    return max(base, max(5.0, floor))


def _api_key() -> str | None:
    k = _resolve_secret_ref(os.environ.get("LBG_DIALOGUE_LLM_API_KEY", ""))
    return k or None


def _resolve_secret_ref(raw: str | None) -> str:
    """Autorise `FOO="${BAR}"` dans EnvironmentFile systemd sans dupliquer le secret."""
    s = (raw or "").strip()
    if len(s) >= 4 and s.startswith("${") and s.endswith("}"):
        key = s[2:-1].strip()
        if key:
            return os.environ.get(key, "").strip()
    return s


def _truncate(s: str, max_len: int) -> str:
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def _format_lyra_for_prompt(lyra: object) -> str | None:
    """Résumé court pour le system prompt (évite de citer des chiffres bruts au joueur)."""
    if not isinstance(lyra, dict):
        return None
    parts: list[str] = []
    g = lyra.get("gauges")
    if isinstance(g, dict):
        for key, label in (
            ("hunger", "faim"),
            ("thirst", "soif"),
            ("fatigue", "fatigue"),
        ):
            v = g.get(key)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            x = float(v)
            if 0.0 <= x <= 1.0:
                pct = max(0, min(100, int(round(x * 100))))
                parts.append(f"{label} ~{pct}%")
            elif x >= 0.0:
                parts.append(f"{label} ~{max(0, min(100, int(round(x))))}%")
        for key, label in (("stress", "stress"), ("patience", "patience")):
            v = g.get(key)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            parts.append(f"{label}={float(v):.1f}")
    if not parts:
        return None
    ver = lyra.get("version")
    suffix = f" (état v{ver})" if isinstance(ver, str) and ver.strip() else ""
    return (
        "Indicateurs internes du personnage (ne pas les lire au joueur mot pour mot) : "
        + ", ".join(parts)
        + suffix
        + "."
    )


def _format_reputation_for_prompt(lyra: object) -> str | None:
    """
    Réputation locale (v2+) : lire `lyra.meta.reputation.value` si présent.
    On la garde comme info interne (ne pas citer un score au joueur).
    """
    if not isinstance(lyra, dict):
        return None
    meta = lyra.get("meta")
    if not isinstance(meta, dict):
        return None
    rep = meta.get("reputation")
    if not isinstance(rep, dict):
        return None
    v = rep.get("value")
    try:
        iv = int(v)
    except Exception:
        return None
    if iv < -100:
        iv = -100
    if iv > 100:
        iv = 100
    return f"Réputation locale envers le joueur: {iv} (borne -100..100)."


def _desktop_plan_enabled(*, context: dict[str, Any]) -> bool:
    v = os.environ.get("LBG_DIALOGUE_DESKTOP_PLAN", "0").strip().lower()
    if v not in ("1", "true", "yes", "on"):
        return False
    return context.get("_desktop_plan") is True


def desktop_plan_env_enabled() -> bool:
    """True si l’agent peut mode planificateur desktop (sans contexte requis) — pour healthz / ops."""
    v = os.environ.get("LBG_DIALOGUE_DESKTOP_PLAN", "0").strip().lower()
    return v in ("1", "true", "yes", "on")


def _require_desktop_json(*, context: dict[str, Any]) -> bool:
    return _desktop_plan_enabled(context=context) and context.get("_require_desktop_json") is True


def resolve_lyra_engagement(context: dict[str, Any]) -> str:
    """
    Mode ADR 0004 : ``local_assistant`` vs ``mmo_persona``.
    Le pont WS (`mmmorpg_server`) force ``mmo_persona`` sur ``context``.
    Si ``world_npc_id`` est présent (hors mode desktop plan), on ne permet pas
    ``local_assistant`` depuis le seul contexte client.
    """
    if _desktop_plan_enabled(context=context):
        return "local_assistant"
    wid = context.get("world_npc_id")
    has_npc = isinstance(wid, str) and bool(wid.strip())
    raw = context.get("lyra_engagement")
    if isinstance(raw, str):
        v = raw.strip().lower()
        if v == "mmo_persona":
            return "mmo_persona"
        if v == "local_assistant" and not has_npc:
            return "local_assistant"
    if has_npc:
        return "mmo_persona"
    return ""


def _format_session_summary_for_prompt(context: dict[str, Any]) -> str | None:
    ss = context.get("session_summary")
    if not isinstance(ss, dict) or not ss:
        return None
    labels = {
        "tracked_quest": "Quête suivie",
        "last_npc": "Interlocuteur / PNJ",
        "player_note": "Note joueur",
        "session_mood": "Ambiance",
        "quest_snapshot": "Instantané quête (serveur jeu)",
        "memory_hint": "Mémoire monde PNJ (clés d’état, sans valeurs sensibles)",
    }
    parts: list[str] = []
    for k in ("tracked_quest", "quest_snapshot", "last_npc", "memory_hint", "player_note", "session_mood"):
        v = ss.get(k)
        if isinstance(v, str) and v.strip():
            lab = labels.get(k, k)
            t = v.strip().replace("\n", " ")
            if len(t) > 140:
                t = t[:137] + "…"
            parts.append(f"- {lab}: {t}")
    if not parts:
        return None
    return (
        "Résumé session (client + serveur MMO, données non sensibles ; cohérence RP) :\n" + "\n".join(parts)
    )


def build_system_prompt(speaker: str, context: dict[str, Any]) -> str:
    if _desktop_plan_enabled(context=context):
        profile = _resolve_profile(context)
        req = context.get("_require_desktop_json") is True
        lines = [
            _profile_prompt(profile, speaker=speaker, context=context),
            f"Tu incarnes {speaker}, un assistant qui aide l'utilisateur à formuler des actions PC contrôlées.",
            "Tu réponds en français. Reste bref : 1 à 2 phrases maximum (pas de liste), idéalement moins de 45 mots sauf demande explicite de détail.",
            "Ne dis pas que tu es une intelligence artificielle ni un modèle de langage.",
            (
                "Tu DOIS commencer ta réponse par UNE ligne exacte :"
                if req
                else "Si une action PC simple correspond à la demande, commence ta réponse par UNE ligne exacte :"
            ),
            'DESKTOP_JSON: {"kind":"open_url","url":"https://example.org"}',
            'DESKTOP_JSON: {"kind":"search_web_open","query":"site exemple"}',
            'DESKTOP_JSON: {"kind":"mail_imap_preview","from_contains":"intel"}',
            'DESKTOP_JSON: {"kind":"notepad_append","path":"C:\\\\Users\\\\Public\\\\lbg_note.txt","text":"ligne\\n"}',
            'DESKTOP_JSON: {"kind":"open_app","app":"notepad","args":[],"learn":false}',
            "Contraintes : kind parmi open_url, search_web_open, mail_imap_preview, notepad_append, open_app.",
            "open_url : champ url (http/https).",
            "search_web_open : champ query (string) ; nécessite LBG_DESKTOP_WEB_SEARCH=1 côté worker.",
            "mail_imap_preview : from_contains et/ou subject_contains (filtres sous-chaîne), optionnel max_messages (1–10), max_body_chars (0–4000), max_scan (10–500) ; nécessite LBG_DESKTOP_MAIL_ENABLED=1 et config IMAP sur le worker.",
            "notepad_append : champs path (fichier) et text (string).",
            "open_app : champ app (identifiant court), args optionnel (liste de chaînes), learn optionnel (bool).",
            "L'allowlist réelle (URL, chemins, binaires) est appliquée plus tard par le worker ; tu proposes seulement une intention structurée.",
            (
                "Sans ligne DESKTOP_JSON valide, ta réponse est considérée comme incorrecte."
                if req
                else "Si la demande est ambiguë ou hors périmètre, réponds sans DESKTOP_JSON."
            ),
            "Après la ligne DESKTOP_JSON facultative/obligatoire, ajoute ta courte phrase affichée à l'utilisateur.",
        ]
        sum_d = _format_session_summary_for_prompt(context)
        if sum_d:
            lines.append(
                "Résumé MMO éventuel (export volontaire ; pas de secrets poste) : tu peux t'en inspirer pour répondre au joueur sur son PC, sans confondre avec des actions réelles déjà exécutées."
            )
            lines.append(sum_d)
        return "\n".join(lines)

    profile = _resolve_profile(context)
    lines = [
        _profile_prompt(profile, speaker=speaker, context=context),
        f"Tu incarnes {speaker}, un personnage non-joueur (PNJ) dans un MMORPG médiéval-fantasy.",
        "Tu réponds en français. Reste dans ton rôle.",
        "Réponds court: 1 à 3 phrases (pas de liste), idéalement moins de 55 mots, sauf si le joueur demande explicitement une explication longue.",
        "Ne dis pas que tu es une intelligence artificielle ni un modèle de langage.",
        f"Profil actif: {profile}.",
    ]
    eng = resolve_lyra_engagement(context)
    if eng == "mmo_persona":
        lines.append(
            "Engagement produit : **persona MMO** — tu restes dans le monde simulé. "
            "Ne suggère pas d'actions sur le poste réel du joueur (messagerie personnelle, fichiers locaux, navigateur hors contexte jeu). "
            "Les effets jeu autorisés passent par ACTION_JSON (si activé) ou par ta réplique uniquement."
        )
    sum_line = _format_session_summary_for_prompt(context)
    if sum_line:
        lines.append(sum_line)
    if normalize_history(context.get("history")):
        lines.append(
            "Ce joueur et toi avez déjà échangé : l'historique ci-dessous reprend la conversation en cours (ordre chronologique). "
            "Reste cohérent avec tes répliques précédentes. "
            "N'utilise pas de tournure du type « nouveau visiteur », « bienvenue pour la première fois » ou toute réintroduction comme si le joueur venait d'arriver "
            "lorsque l'historique montre déjà au moins un message user ou assistant — continue la scène telle quelle. "
            "Si le joueur vient de confirmer ou d'accepter (ex. « ok », « d'accord », « je vous apporte ça ») juste après une de tes demandes "
            "(nourriture, boisson, objet, rendez-vous, etc.), enchaîne naturellement : remercie, précise où te retrouver ou comment procéder — "
            "**sans** repartir sur une question générique du type « que souhaitez-vous ? » ou « de quoi avons-nous besoin de parler ? » "
            "comme si la conversation recommençait à zéro. "
            "Si le joueur contredit le « Résumé session » (faits du monde ou quête) ou se contredit par rapport à ce qu'il vient d'affirmer dans l'historique, "
            "réagis en une courte phrase, **dans ton rôle** (doute poli, relance, taquinerie) — sans vocabulaire moderne hors cadre ni accusation violente."
        )
    for key, label in (
        ("scene", "Lieu / scène"),
        ("world_hint", "Monde"),
        ("quest_hint", "Quête ou objectif"),
    ):
        v = context.get(key)
        if isinstance(v, str) and v.strip():
            lines.append(f"{label}: {v.strip()}")
    lyra_line = _format_lyra_for_prompt(context.get("lyra"))
    if lyra_line:
        lines.append(lyra_line)
        lines.append(
            "Tu peux laisser transparaître cet état (humeur, impatience, lenteur, envie de manger ou boire) "
            "sans énumérer de chiffres ni dire « jauge »."
        )
    rep_line = _format_reputation_for_prompt(context.get("lyra"))
    if rep_line:
        lines.append(rep_line)
        lines.append(
            "Adapte légèrement ton attitude selon cette réputation (plus chaleureux si positive, plus froid si négative), "
            "sans mentionner explicitement un score."
        )
    pnj_reg_line = _format_npc_registry_for_prompt(context)
    if pnj_reg_line:
        lines.append(pnj_reg_line)
    rid = _resolve_race_id_for_prompt(context)
    if rid:
        rline = format_race_for_prompt(rid)
        if rline:
            lines.append(rline)
    cref_line = format_creature_refs_for_prompt(context.get("_creature_refs"))
    if cref_line:
        lines.append(cref_line)
    aq = context.get("_active_quest_id")
    if isinstance(aq, str) and aq.strip():
        lines.append(
            f"Quête suivie côté client (référence) : {aq.strip()} — utilise ce quest_id si le joueur résout ou clôt cette quête."
        )

    # Option "LLM-on actions monde" (bornée) : le modèle peut suggérer une action déterministe.
    # Gated par env + présence d'un PNJ monde (sinon on ignore).
    v = os.environ.get("LBG_DIALOGUE_WORLD_ACTIONS", "0").strip().lower()
    if v in ("1", "true", "yes", "on") and isinstance(context.get("world_npc_id"), str) and context.get("world_npc_id"):
        require_action = bool(context.get("_require_action_json") is True)
        requested_kind = context.get("_world_action_kind")
        requested_kind = requested_kind.strip().lower() if isinstance(requested_kind, str) else ""
        if requested_kind not in ("aid", "quest"):
            requested_kind = ""
        lines.append(
            (
                "Actions monde (REQUIS) : commence ta réponse par UNE ligne :"
                if require_action
                else "Optionnel (actions monde) : si tu veux proposer une action sur le monde, commence ta réponse par UNE ligne :"
            )
        )
        lines.append(
            "Après toute ligne ACTION_JSON (obligatoire ou non), écris **sur la même ligne ou la ligne suivante, sans ligne vide entre les deux**, "
            "au moins une courte phrase en voix du personnage (dialogue joueur-visible). "
            "Ne mets pas de ligne vide juste après ACTION_JSON : enchaîne tout de suite la réplique, sinon le texte peut être tronqué."
        )
        lines.append('ACTION_JSON: {"kind":"aid","hunger_delta":-0.2,"thirst_delta":-0.1,"fatigue_delta":-0.2,"reputation_delta":5}')
        lines.append('ACTION_JSON: {"kind":"quest","quest_id":"q:help_innkeeper","quest_step":0,"quest_accepted":true}')
        lines.append(
            'ACTION_JSON: {"kind":"quest","quest_id":"q:help_innkeeper","quest_step":3,"quest_accepted":true,"quest_completed":true,"reputation_delta":8}'
        )
        if requested_kind:
            lines.append(
                f"Action demandée par l'interface: utilise obligatoirement kind='{requested_kind}' "
                "dans ACTION_JSON pour cette réponse."
            )
        lines.append(
            "Quand le joueur demande explicitement une aide immédiate (nourriture, boisson, repos, compassion), "
            "tu peux utiliser ACTION_JSON pour déclencher l'aide."
        )
        lines.append(
            "Quand le joueur accepte une quête, ou qu'il faut enregistrer l'état d'une quête (id + step), "
            "tu peux utiliser ACTION_JSON kind='quest'."
        )
        lines.append(
            "Quand le joueur a terminé les objectifs et que la quête doit se clôturer, utilise kind='quest' avec "
            "quest_completed=true (et garde quest_id cohérent). Tu peux augmenter quest_step en même temps si utile."
        )
        lines.append(
            "Sur une quête (surtout à la clôture), tu peux ajouter reputation_delta entier dans [-100,100] "
            "comme petite récompense ou pénalité RP ; 0 ou absent = aucun effet réputation."
        )
        lines.append(
            "Pour récompenser le joueur avec un objet d'inventaire (session), sur une ligne kind='quest' tu peux ajouter "
            "player_item_id (string), player_item_qty_delta (entier non nul entre -50 et 50), et player_item_label (optionnel). "
            'Exemple : ACTION_JSON: {"kind":"quest","quest_id":"q:loot","quest_step":1,"quest_accepted":true,'
            '"player_item_id":"item:potion","player_item_qty_delta":1,"player_item_label":"Potion faible"}'
        )
        lines.append(
            "Si tu déclenches une aide, mets en général un petit reputation_delta positif (ex: 1 à 10) "
            "car l'aide améliore la confiance, sauf raison RP contraire."
        )
        lines.append(
            "Contraintes: kind='aid' ou kind='quest'. "
            "Pour aid: deltas hunger/thirst/fatigue dans [-1,1]; reputation_delta dans [-100,100]. "
            "Pour quest: quest_id string non vide; quest_step int [0,10000]; quest_accepted bool; "
            "quest_completed bool optionnel (false par défaut); reputation_delta int optionnel [-100,100]; "
            "optionnel sur la même ligne quest: player_item_id + player_item_qty_delta (non nul, [-50,50]) + player_item_label optionnel. "
            + ("Tu DOIS écrire ACTION_JSON car il est requis." if require_action else "Si aucune action n'est nécessaire, n'écris pas ACTION_JSON.")
        )
    return "\n".join(lines)


_DESKTOP_JSON_MARK = re.compile(r"(?i)\bDESKTOP_JSON\s*:\s*")


def _strip_desktop_json_from_line(line: str) -> tuple[dict[str, Any] | None, str]:
    """Retire le ou les blocs ``DESKTOP_JSON: {...}`` d’une ligne (dernier dict valide gagne)."""
    last_obj: dict[str, Any] | None = None
    cur = line
    dec = json.JSONDecoder()
    while True:
        ms = list(_DESKTOP_JSON_MARK.finditer(cur))
        if not ms:
            return last_obj, cur
        m = ms[-1]
        head = cur[: m.start()]
        tail = cur[m.end() :]
        t = tail.lstrip()
        try:
            obj, used = dec.raw_decode(t)
        except json.JSONDecodeError:
            return last_obj, cur
        if not isinstance(obj, dict):
            return last_obj, cur
        last_obj = obj
        drop_end = m.end() + (len(tail) - len(t)) + used
        rest = cur[drop_end:]
        cur = (head.rstrip() + rest).strip()


def _parse_desktop_json_prefix(raw: str) -> tuple[dict[str, Any] | None, str]:
    """Extrait ``DESKTOP_JSON: {...}`` sur n’importe quelle ligne ou en fin de ligne ; garde la dernière action dict valide."""
    s = (raw or "").replace("\r\n", "\n")
    if not s.strip():
        return None, s.strip()

    last_obj: dict[str, Any] | None = None
    kept: list[str] = []
    for line in s.split("\n"):
        line_last, visible = _strip_desktop_json_from_line(line)
        if line_last is not None:
            last_obj = line_last
        if visible.strip():
            kept.append(visible.rstrip("\n"))
    remaining = "\n".join(kept).strip()
    return last_obj, remaining


def _sanitize_desktop_action_proposal(action: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    Valide une proposition d'action desktop (structurelle). None si invalide.
    Les allowlists métier restent côté worker à l'exécution.
    """
    if not isinstance(action, dict) or not action:
        return None
    kind = (action.get("kind") or "").strip()
    if kind == "open_url":
        url = action.get("url")
        if not isinstance(url, str) or not url.strip():
            return None
        u = url.strip()
        if len(u) > 2048:
            u = u[:2048]
        if not (u.startswith("http://") or u.startswith("https://")):
            return None
        return {"kind": "open_url", "url": u}

    if kind == "search_web_open":
        qry = action.get("query")
        if not isinstance(qry, str) or not qry.strip():
            return None
        q2 = qry.strip()
        if len(q2) > 220:
            q2 = q2[:220]
        return {"kind": "search_web_open", "query": q2}

    if kind == "notepad_append":
        path = action.get("path")
        text = action.get("text")
        if not isinstance(path, str) or not path.strip():
            return None
        if not isinstance(text, str):
            return None
        p2 = path.strip()
        if len(p2) > 1024:
            p2 = p2[:1024]
        if len(text) > 100_000:
            text = text[:100_000]
        return {"kind": "notepad_append", "path": p2, "text": text}

    if kind == "mail_imap_preview":
        fc = action.get("from_contains")
        sc = action.get("subject_contains")
        fc_s = fc.strip() if isinstance(fc, str) else ""
        sc_s = sc.strip() if isinstance(sc, str) else ""
        if not fc_s and not sc_s:
            return None
        if len(fc_s) > 80:
            fc_s = fc_s[:80]
        if len(sc_s) > 120:
            sc_s = sc_s[:120]
        out2: dict[str, Any] = {"kind": "mail_imap_preview"}
        if fc_s:
            out2["from_contains"] = fc_s
        if sc_s:
            out2["subject_contains"] = sc_s
        mm = action.get("max_messages", 3)
        mb = action.get("max_body_chars", 800)
        ms = action.get("max_scan", 200)
        try:
            mmi = int(mm) if mm is not None else 3
        except Exception:
            mmi = 3
        try:
            mbi = int(mb) if mb is not None else 800
        except Exception:
            mbi = 800
        try:
            msi = int(ms) if ms is not None else 200
        except Exception:
            msi = 200
        out2["max_messages"] = max(1, min(10, mmi))
        out2["max_body_chars"] = max(0, min(4000, mbi))
        out2["max_scan"] = max(10, min(500, msi))
        return out2

    if kind == "open_app":
        app = action.get("app")
        if not isinstance(app, str) or not app.strip():
            return None
        a2 = app.strip()
        if len(a2) > 80:
            a2 = a2[:80]
        args_raw = action.get("args", [])
        if args_raw is None:
            args_out: list[str] = []
        elif not isinstance(args_raw, list):
            return None
        else:
            args_out = []
            for i, item in enumerate(args_raw):
                if i >= 16:
                    break
                if not isinstance(item, str):
                    return None
                s = item
                if len(s) > 500:
                    s = s[:500]
                args_out.append(s)
        learn = action.get("learn", False)
        if learn is not None and not isinstance(learn, bool):
            return None
        out: dict[str, Any] = {"kind": "open_app", "app": a2, "args": args_out}
        if learn is True:
            out["learn"] = True
        return out

    return None


def _parse_action_json_prefix(raw: str) -> tuple[dict[str, Any] | None, str]:
    """
    Parse un préfixe d'une ou plusieurs lignes `ACTION_JSON: {...}` (consécutives).
    Retourne (last_action_dict|None, remaining_text).

    Rationale : certains modèles peuvent émettre plusieurs ACTION_JSON malgré l'instruction "une seule ligne".
    Dans ce cas, on consomme toutes les lignes consécutives et on garde la dernière action valide.
    """
    s = (raw or "").replace("\r\n", "\n").strip()
    if not s:
        return None, raw.strip()

    lines = s.split("\n")
    idx = 0
    last_obj: dict[str, Any] | None = None
    while idx < len(lines):
        line = lines[idx].strip()
        if not line.startswith("ACTION_JSON:"):
            break
        payload = line.split("ACTION_JSON:", 1)[1].strip()
        try:
            obj = json.loads(payload)
            if isinstance(obj, dict):
                last_obj = obj
        except Exception:
            # Ligne invalide : on l'ignore et on continue à consommer le préfixe.
            pass
        idx += 1
    remaining = "\n".join(lines[idx:]).strip()
    return last_obj, remaining


def _sanitize_world_action(action: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    Valide et borne l'action monde. Renvoie None si invalide.
    """
    if not isinstance(action, dict) or not action:
        return None
    kind = (action.get("kind") or "").strip()
    if kind not in ("aid", "quest"):
        return None

    def f(name: str) -> float:
        try:
            return float(action.get(name, 0.0))
        except Exception:
            return 0.0

    def i(name: str) -> int:
        try:
            return int(action.get(name, 0))
        except Exception:
            return 0

    if kind == "aid":
        return {
            "kind": "aid",
            "hunger_delta": max(-1.0, min(1.0, f("hunger_delta"))),
            "thirst_delta": max(-1.0, min(1.0, f("thirst_delta"))),
            "fatigue_delta": max(-1.0, min(1.0, f("fatigue_delta"))),
            "reputation_delta": max(-100, min(100, i("reputation_delta"))),
        }

    # kind == "quest"
    qid = action.get("quest_id")
    if not isinstance(qid, str) or not qid.strip():
        return None
    qid2 = qid.strip()
    if len(qid2) > 80:
        qid2 = qid2[:80]
    step = i("quest_step")
    if step < 0:
        step = 0
    if step > 10_000:
        step = 10_000
    accepted_raw = action.get("quest_accepted")
    accepted = True if accepted_raw is None else bool(accepted_raw) if isinstance(accepted_raw, bool) else None
    if accepted is None:
        # type invalide => rejeter
        return None
    if "quest_completed" in action:
        qc_raw = action.get("quest_completed")
        if not isinstance(qc_raw, bool):
            return None
        quest_completed = bool(qc_raw)
    else:
        quest_completed = False
    rep_d = max(-100, min(100, i("reputation_delta")))
    out: dict[str, Any] = {
        "kind": "quest",
        "quest_id": qid2,
        "quest_step": int(step),
        "quest_accepted": bool(accepted),
        "quest_completed": quest_completed,
    }
    if rep_d != 0:
        out["reputation_delta"] = int(rep_d)

    pid_raw = action.get("player_item_id")
    if isinstance(pid_raw, str) and pid_raw.strip():
        qd_inv = i("player_item_qty_delta")
        if qd_inv == 0 or qd_inv < -50 or qd_inv > 50:
            return None
        pid_s = pid_raw.strip()
        if len(pid_s) > 64:
            pid_s = pid_s[:64]
        out["player_item_id"] = pid_s
        out["player_item_qty_delta"] = int(qd_inv)
        plab = action.get("player_item_label")
        if isinstance(plab, str):
            pl2 = plab.strip()
            if pl2:
                out["player_item_label"] = pl2[:80]
    return out


def _world_actions_enabled(*, context: dict[str, Any]) -> bool:
    v = os.environ.get("LBG_DIALOGUE_WORLD_ACTIONS", "0").strip().lower()
    if v not in ("1", "true", "yes", "on"):
        return False
    return isinstance(context.get("world_npc_id"), str) and bool(str(context.get("world_npc_id")).strip())


def _require_action_json(*, context: dict[str, Any]) -> bool:
    return _world_actions_enabled(context=context) and bool(context.get("_require_action_json") is True)


def _postprocess_llm_content(*, raw: str, context: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    """
    Post-traitement central :
    - optionnellement parse DESKTOP_JSON (prioritaire) pour proposition desktop
    - optionnellement parse ACTION_JSON monde
    - enforce short reply sur le texte visible joueur
    """
    working = (raw or "").replace("\r\n", "\n")

    if _desktop_plan_enabled(context=context):
        try:
            context.pop("_desktop_action_proposal", None)
        except Exception:
            pass
        d_raw, working = _parse_desktop_json_prefix(working)
        d_san = _sanitize_desktop_action_proposal(d_raw)
        if d_san is not None:
            try:
                context["_desktop_action_proposal"] = d_san
            except Exception:
                pass
        working = working.strip()

    if _world_actions_enabled(context=context):
        action_raw, remaining = _parse_action_json_prefix(working)
        action = _sanitize_world_action(action_raw)
        visible = remaining if action is not None else working
        reply = _enforce_short_reply(visible)
        if action is not None:
            if not (isinstance(reply, str) and reply.strip()):
                reply = "C'est entendu, j'enregistre ça pour la scène."
            try:
                context["_world_action"] = action
            except Exception:
                pass
        return reply, action
    return _enforce_short_reply(working), None


### Note: pas d'API publique "with_action" : l'action est exposée best-effort via context["_world_action"].


def _coerce_openai_message_content(raw: object) -> str:
    """Uniformise ``message.content`` (chaîne ou liste de segments texte selon serveurs compatibles OpenAI)."""
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        parts: list[str] = []
        for item in raw:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                tx = item.get("text")
                if isinstance(tx, str):
                    parts.append(tx)
                else:
                    nested = item.get("content")
                    if isinstance(nested, str):
                        parts.append(nested)
            # autres formes (image_url, etc.) ignorées
        return "".join(parts)
    if isinstance(raw, dict):
        tx = raw.get("text")
        if isinstance(tx, str):
            return tx
    return ""


def _assistant_message_text(msg: dict[str, Any]) -> str:
    """
    Texte utile d’un message ``assistant`` : ``content`` canonique, puis champs alternatifs
    (pensements / raisonnement exposés par certains serveurs quand ``content`` est vide).
    """
    primary = _coerce_openai_message_content(msg.get("content")).strip()
    if primary:
        return primary
    for key in ("reasoning_content", "reasoning", "thinking"):
        alt = msg.get(key)
        if isinstance(alt, str) and alt.strip():
            return alt.strip()
    return ""


def _choice_assistant_text(choice: dict[str, Any]) -> str:
    """Extrait le texte assistant d’un élément ``choices[]`` (chat completions)."""
    msg = choice.get("message")
    if isinstance(msg, dict):
        t = _assistant_message_text(msg)
        if t:
            return t
    legacy = choice.get("text")
    if isinstance(legacy, str) and legacy.strip():
        return legacy.strip()
    return ""


def normalize_history(raw: object, *, max_messages: int = 24) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            continue
        c = content.strip()
        if not c:
            continue
        out.append({"role": role, "content": _truncate(c, 2000)})
    if len(out) > max_messages:
        out = out[-max_messages:]
    return out


def run_dialogue_turn(
    *,
    player_text: str,
    speaker: str,
    context: dict[str, Any],
) -> str:
    route = _resolve_route(context)
    b = route.get("base_url", "")
    selected_model = route.get("model", model_name())
    selected_target = route.get("target", "local")
    if not b:
        raise RuntimeError("LLM désactivé (LBG_DIALOGUE_LLM_DISABLED) ou indisponible")

    # Bypass cache (debug / situations où l'état doit toujours être re-évalué).
    cache_bypass = isinstance(context.get("_no_cache"), bool) and context.get("_no_cache") is True
    if _desktop_plan_enabled(context=context):
        cache_bypass = True
    cache_hit = False
    ck = "" if cache_bypass else _cache_key(speaker=speaker, player_text=player_text, context=context)
    if ck:
        cached = _cache_get(ck)
        if cached is not None:
            global _cache_hits
            _cache_hits += 1
            cache_hit = True
            sp = speaker.strip() or "PNJ"
            _cache_hits_by_speaker[sp] = _cache_hits_by_speaker.get(sp, 0) + 1
            # Exposer un hint best-effort au caller (observabilité).
            try:
                context["_cache_hit"] = True
            except Exception:
                pass
            _emit_dialogue_trace_followup(
                context,
                route=route,
                speaker=speaker,
                player_text=player_text,
                cache_hit=True,
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=0,
                outcome="cache_hit",
            )
            return cached
        global _cache_misses
        _cache_misses += 1
        sp = speaker.strip() or "PNJ"
        _cache_misses_by_speaker[sp] = _cache_misses_by_speaker.get(sp, 0) + 1
    try:
        context["_cache_hit"] = False
    except Exception:
        pass

    sys_prompt = build_system_prompt(speaker, context)
    try:
        max_hist = int(os.environ.get("LBG_DIALOGUE_LLM_MAX_HISTORY", "24"))
    except ValueError:
        max_hist = 24
    max_hist = max(0, min(max_hist, 64))
    history = normalize_history(context.get("history"), max_messages=max_hist)
    messages: list[dict[str, str]] = [{"role": "system", "content": sys_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": player_text})

    url = f"{b}/chat/completions"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    key = (route.get("api_key") or "").strip() or _api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"

    try:
        temperature = float(os.environ.get("LBG_DIALOGUE_LLM_TEMPERATURE", "0.7"))
    except ValueError:
        temperature = 0.7
    try:
        max_tokens = int(os.environ.get("LBG_DIALOGUE_LLM_MAX_TOKENS", "512"))
    except ValueError:
        max_tokens = 512
    # Autoriser des sorties très courtes en prod (ex: 24) pour la latence.
    max_tokens = max(1, min(max_tokens, 4096))
    # Si le caller exige un ACTION_JSON ou DESKTOP_JSON, éviter les réponses tronquées.
    if (_require_action_json(context=context) or _require_desktop_json(context=context)) and max_tokens < 160:
        max_tokens = 160
    elif _desktop_plan_enabled(context=context) and max_tokens < 96:
        max_tokens = 96
    elif _world_actions_enabled(context=context) and max_tokens < 160:
        # ACTION_JSON optionnel + réplique : sous-tirer fièrement sur petits max_tokens (ex. .env à 32).
        max_tokens = 160

    payload: dict[str, Any] = {
        "model": selected_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    # Couper les sorties multi-paragraphes (souvent inutiles, coûteuses en latence).
    # Avec ACTION_JSON ou DESKTOP_JSON, un double saut de ligne après la ligne structurée arrêtait souvent
    # la génération avant la réplique visible → contenu vide + fallback. Désactiver ce stop dans ces modes.
    if not _world_actions_enabled(context=context) and not _desktop_plan_enabled(context=context):
        payload["stop"] = ["\n\n"]

    def _parse_openai_chat_completions(data: Any) -> tuple[str, dict[str, int]]:
        if not isinstance(data, dict):
            raise RuntimeError("Réponse LLM invalide: type")
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("Réponse LLM invalide: pas de choices")
        usage_obj = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        try:
            pt = int(usage_obj.get("prompt_tokens", 0))
        except Exception:
            pt = 0
        try:
            ct = int(usage_obj.get("completion_tokens", 0))
        except Exception:
            ct = 0
        usage_out = {"prompt_tokens": max(0, pt), "completion_tokens": max(0, ct)}
        for ch in choices:
            if not isinstance(ch, dict):
                continue
            extracted = _choice_assistant_text(ch)
            if extracted.strip():
                return extracted.strip(), usage_out
        raise RuntimeError("Réponse LLM vide")

    def _try_ollama_native_api_chat(*, base: str) -> tuple[str, dict[str, int]]:
        """
        Fallback pour Ollama quand l'endpoint OpenAI-compatible renvoie 500.
        https://github.com/ollama/ollama/blob/main/docs/api.md
        """
        root = base.rstrip("/")
        if root.endswith("/v1"):
            root = root[:-3]
        native_url = f"{root}/api/chat"
        ollama_opts: dict[str, Any] = {
            "temperature": temperature,
            # Aligner le comportement Ollama sur "max_tokens" OpenAI.
            "num_predict": max_tokens,
        }
        if not _world_actions_enabled(context=context) and not _desktop_plan_enabled(context=context):
            ollama_opts["stop"] = ["\n\n"]
        native_payload: dict[str, Any] = {
            "model": selected_model,
            "messages": messages,
            "stream": False,
            # Garder le modèle "chaud" pour éviter les cold starts.
            # Ollama accepte aussi des durées (ex: "10m") selon versions; -1 = keep alive.
            "keep_alive": -1,
            "options": ollama_opts,
        }
        with httpx.Client(timeout=_effective_llm_http_timeout_s(context=context)) as client:
            r2 = client.post(native_url, json=native_payload)
        try:
            r2.raise_for_status()
        except httpx.HTTPStatusError as e2:
            body2 = (e2.response.text or "")[:400]
            raise RuntimeError(f"HTTP {e2.response.status_code} (ollama api/chat): {body2}") from e2
        data2 = r2.json()
        if not isinstance(data2, dict):
            raise RuntimeError("Réponse Ollama invalide: type")
        msg2 = data2.get("message")
        if not isinstance(msg2, dict):
            raise RuntimeError("Réponse Ollama invalide: message")
        content2 = _assistant_message_text(msg2)
        if not content2.strip():
            raise RuntimeError("Réponse Ollama vide")
        try:
            pt = int(data2.get("prompt_eval_count", 0))
        except Exception:
            pt = 0
        try:
            ct = int(data2.get("eval_count", 0))
        except Exception:
            ct = 0
        return content2.strip(), {"prompt_tokens": max(0, pt), "completion_tokens": max(0, ct)}

    b_norm = b.rstrip("/")
    looks_like_ollama = (
        "127.0.0.1:11434" in b_norm
        or "localhost:11434" in b_norm
        or b_norm.endswith(":11434/v1")
        or b_norm.endswith(":11434")
    )

    t_llm0 = time.perf_counter()

    def _finalize_ok(raw_llm: str, usage: dict[str, int]) -> str:
        reply, _ = _postprocess_llm_content(raw=raw_llm, context=context)
        if ck:
            _cache_set(ck, reply)
        latency_ms = int((time.perf_counter() - t_llm0) * 1000)
        pt = int(usage.get("prompt_tokens", 0))
        ct = int(usage.get("completion_tokens", 0))
        tgt = str(route.get("target") or "local")
        cost = _estimate_cost_usd(prompt_tokens=pt, completion_tokens=ct, target=tgt)
        if tgt in ("fast", "remote"):
            _budget_record(cost)
        _emit_dialogue_trace_followup(
            context,
            route=route,
            speaker=speaker,
            player_text=player_text,
            cache_hit=cache_hit,
            prompt_tokens=pt,
            completion_tokens=ct,
            latency_ms=latency_ms,
            outcome="ok",
        )
        return reply

    try:
        # Ollama peut être beaucoup plus rapide via /api/chat que via /v1/chat/completions.
        if looks_like_ollama:
            try:
                raw, usage = _try_ollama_native_api_chat(base=b_norm)
                return _finalize_ok(raw, usage)
            except Exception:
                pass

        with httpx.Client(timeout=_effective_llm_http_timeout_s(context=context)) as client:
            r = client.post(url, headers=headers, json=payload)
        try:
            r.raise_for_status()
            raw, usage = _parse_openai_chat_completions(r.json())
            return _finalize_ok(raw, usage)
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            body = (e.response.text or "")[:400]
            if status >= 500 and looks_like_ollama:
                try:
                    raw, usage = _try_ollama_native_api_chat(base=b_norm)
                    return _finalize_ok(raw, usage)
                except Exception as fallback_exc:
                    raise RuntimeError(
                        f"HTTP {status} (openai chat/completions): {body} | fallback Ollama échoué: {fallback_exc}"
                    ) from fallback_exc
            raise RuntimeError(f"HTTP {status}: {body}") from e
    except Exception as e:
        latency_ms = int((time.perf_counter() - t_llm0) * 1000)
        err = str(e)[:800]
        _emit_dialogue_trace_followup(
            context,
            route=route,
            speaker=speaker,
            player_text=player_text,
            cache_hit=cache_hit,
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=latency_ms,
            outcome="error",
            error=err,
        )
        raise
