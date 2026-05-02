"""
Appel LLM compatible API OpenAI (`POST …/v1/chat/completions`) — Ollama, OpenAI, LM Studio, etc.

Variables d’environnement :
- ``LBG_DIALOGUE_LLM_BASE_URL`` — défaut : Ollama local ``http://127.0.0.1:11434/v1``. Surcharger pour Groq, OpenAI, autre hôte Ollama, etc.
- ``LBG_DIALOGUE_LLM_DISABLED`` — si ``1`` / ``true`` : pas d’appel LLM (stub côté agent HTTP).
- ``LBG_DIALOGUE_LLM_API_KEY`` — optionnel (Ollama local souvent sans clé).
- ``LBG_DIALOGUE_LLM_MODEL`` — défaut ``phi4-mini:latest`` (nom ``ollama list``).
- ``LBG_DIALOGUE_LLM_TIMEOUT`` — secondes (défaut 120).
- ``LBG_DIALOGUE_LLM_TEMPERATURE`` — défaut 0.7.
- ``LBG_DIALOGUE_LLM_MAX_TOKENS`` — défaut 512.

Historique multi-tours : ``context["history"]`` = liste d’objets avec ``role`` (``"user"`` ou ``"assistant"``) et ``content`` (chaîne).

État Lyra : si ``context["lyra"]`` est un objet (ex. ``gauges`` faim/soif/fatigue 0–1), un résumé est ajouté au prompt système pour influencer le ton du PNJ.
"""

from __future__ import annotations

import os
import re
import time
import json
import hashlib
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


def _strip_emoji(s: str) -> str:
    return _emoji_re.sub("", s)


def _enforce_short_reply(raw: str) -> str:
    """
    Post-traitement strict : 1-2 phrases, limite de mots, sans emojis.
    Contrôlé par env :
      - LBG_DIALOGUE_STRICT_SHORT (défaut 1)
      - LBG_DIALOGUE_MAX_SENTENCES (défaut 2)
      - LBG_DIALOGUE_MAX_WORDS (défaut 25)
    """
    v = os.environ.get("LBG_DIALOGUE_STRICT_SHORT", "1").strip().lower()
    if v in ("0", "false", "no", "off"):
        return raw.strip()

    s = _strip_emoji(raw).strip()
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return raw.strip()

    try:
        max_sent = int(os.environ.get("LBG_DIALOGUE_MAX_SENTENCES", "2"))
    except ValueError:
        max_sent = 2
    max_sent = max(1, min(max_sent, 6))

    try:
        max_words = int(os.environ.get("LBG_DIALOGUE_MAX_WORDS", "25"))
    except ValueError:
        max_words = 25
    max_words = max(5, min(max_words, 80))

    parts = re.split(r"(?<=[.!?])\s+", s)
    s2 = " ".join([p.strip() for p in parts if p.strip()][:max_sent]).strip()
    if not s2:
        s2 = s

    words = s2.split()
    if len(words) > max_words:
        s2 = " ".join(words[:max_words]).rstrip(" ,;:") + "…"

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
        "world_npc_id,quest_state,encounter_state,world_flags,_active_quest_id,_creature_refs",
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
    return f"{speaker.strip()}|{player_text.strip()}|{lyra_v}|{ctx_hash}"


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


def _resolve_profile(context: dict[str, Any]) -> str:
    raw = context.get("dialogue_profile")
    if isinstance(raw, str) and raw.strip():
        return raw.strip().lower()
    env_profile = os.environ.get("LBG_DIALOGUE_PROFILE_DEFAULT", "professionnel").strip().lower()
    return env_profile or "professionnel"


def _resolve_route(context: dict[str, Any]) -> dict[str, str]:
    target_raw = context.get("dialogue_target")
    target = str(target_raw).strip().lower() if isinstance(target_raw, str) else "local"
    if target not in ("local", "remote", "fast"):
        target = "local"

    allow_remote = _is_truthy(os.environ.get("LBG_DIALOGUE_REMOTE_ENABLED", "0"))
    allow_fast = _is_truthy(os.environ.get("LBG_DIALOGUE_FAST_ENABLED", "0"))
    if target == "fast":
        fast_base = os.environ.get("LBG_DIALOGUE_FAST_BASE_URL", "").strip().rstrip("/")
        fast_model = os.environ.get("LBG_DIALOGUE_FAST_MODEL", "").strip()
        fast_api_key = _resolve_secret_ref(os.environ.get("LBG_DIALOGUE_FAST_API_KEY", ""))
        if allow_fast and fast_base and fast_model:
            return {"target": "fast", "base_url": fast_base, "model": fast_model, "api_key": fast_api_key}
        # Fallback coût/latence contrôlé : si le remote standard est activé, il peut servir de voie rapide.
        target = "remote" if allow_remote else "local"

    if target == "remote" and not allow_remote:
        target = "local"

    if target == "remote":
        base = os.environ.get("LBG_DIALOGUE_REMOTE_BASE_URL", "").strip().rstrip("/")
        model = os.environ.get("LBG_DIALOGUE_REMOTE_MODEL", "").strip()
        api_key = _resolve_secret_ref(os.environ.get("LBG_DIALOGUE_REMOTE_API_KEY", ""))
        if base and model:
            return {"target": "remote", "base_url": base, "model": model, "api_key": api_key}
        # fallback sûr vers local si remote partiellement configuré
    return {"target": "local", "base_url": base_url(), "model": model_name(), "api_key": (_api_key() or "")}


def _profile_prompt(profile: str, *, speaker: str, context: dict[str, Any]) -> str:
    p = (profile or "").strip().lower()
    is_mmo = isinstance(context.get("world_npc_id"), str) and bool(str(context.get("world_npc_id")).strip())
    if not is_mmo:
        return ASSISTANT_PROFILES.get(p, ASSISTANT_PROFILES["professionnel"])
    mmo_templates: dict[str, str] = {
        "chaleureux": f"Tu es {speaker} chaleureux.\n",
        "professionnel": f"Tu es {speaker} professionnel.\n",
        "pedagogue": f"Tu es {speaker} pédagogique.\n",
        "creatif": f"Tu es {speaker} créatif.\n",
        "mini-moi": f"Tu es {speaker} technique.\n",
    }
    return mmo_templates.get(p, mmo_templates["professionnel"]) + BASE_GUARDRAILS_MMO


def _estimate_cost_usd(*, prompt_tokens: int, completion_tokens: int, target: str) -> float | None:
    # Estimation simple paramétrable (USD / 1K tokens), défaut 0 pour local.
    if target == "local":
        return 0.0
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


def build_system_prompt(speaker: str, context: dict[str, Any]) -> str:
    profile = _resolve_profile(context)
    lines = [
        _profile_prompt(profile, speaker=speaker, context=context),
        f"Tu incarnes {speaker}, un personnage non-joueur (PNJ) dans un MMORPG médiéval-fantasy.",
        "Tu réponds en français. Reste dans ton rôle.",
        "Réponds très court: 1 à 2 phrases maximum (pas de liste), idéalement < 25 mots, sauf si le joueur demande explicitement une explication longue.",
        "Ne dis pas que tu es une intelligence artificielle ni un modèle de langage.",
        f"Profil actif: {profile}.",
    ]
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
            "Si tu déclenches une aide, mets en général un petit reputation_delta positif (ex: 1 à 10) "
            "car l'aide améliore la confiance, sauf raison RP contraire."
        )
        lines.append(
            "Contraintes: kind='aid' ou kind='quest'. "
            "Pour aid: deltas hunger/thirst/fatigue dans [-1,1]; reputation_delta dans [-100,100]. "
            "Pour quest: quest_id string non vide; quest_step int [0,10000]; quest_accepted bool; "
            "quest_completed bool optionnel (false par défaut); reputation_delta int optionnel [-100,100]. "
            + ("Tu DOIS écrire ACTION_JSON car il est requis." if require_action else "Si aucune action n'est nécessaire, n'écris pas ACTION_JSON.")
        )
    return "\n".join(lines)


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
    - optionnellement parse ACTION_JSON (avant normalisation whitespace)
    - enforce short reply sur le texte visible joueur
    """
    if _world_actions_enabled(context=context):
        action_raw, remaining = _parse_action_json_prefix(raw)
        action = _sanitize_world_action(action_raw)
        visible = remaining if action is not None else raw
        reply = _enforce_short_reply(visible)
        if action is not None:
            if not (isinstance(reply, str) and reply.strip()):
                reply = "D'accord."
            try:
                context["_world_action"] = action
            except Exception:
                pass
        return reply, action
    return _enforce_short_reply(raw), None


### Note: pas d'API publique "with_action" : l'action est exposée best-effort via context["_world_action"].


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
            _emit_dialogue_trace(
                context,
                {
                    "trace_id": context.get("_trace_id"),
                    "target": selected_target,
                    "model": selected_model,
                    "profile": _resolve_profile(context),
                    "base_host": (urlparse(b.rstrip("/")).netloc or b.rstrip("/")),
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "estimated_cost_usd": 0.0 if selected_target == "local" else None,
                    "cache_hit": True,
                },
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
    # Si le caller exige un ACTION_JSON, éviter les réponses tronquées.
    if _require_action_json(context=context) and max_tokens < 96:
        max_tokens = 96

    payload: dict[str, Any] = {
        "model": selected_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    # Couper les sorties multi-paragraphes (souvent inutiles, coûteuses en latence).
    # Compatible OpenAI / la plupart des serveurs OpenAI-like. Ollama a aussi son propre stop dans /api/chat.
    payload["stop"] = ["\n\n"]

    def _parse_openai_chat_completions(data: Any) -> tuple[str, dict[str, int]]:
        if not isinstance(data, dict):
            raise RuntimeError("Réponse LLM invalide: type")
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("Réponse LLM invalide: pas de choices")
        msg = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(msg, dict):
            raise RuntimeError("Réponse LLM invalide: message")
        content = msg.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Réponse LLM vide")
        usage_obj = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        try:
            pt = int(usage_obj.get("prompt_tokens", 0))
        except Exception:
            pt = 0
        try:
            ct = int(usage_obj.get("completion_tokens", 0))
        except Exception:
            ct = 0
        return content.strip(), {"prompt_tokens": max(0, pt), "completion_tokens": max(0, ct)}

    def _try_ollama_native_api_chat(*, base: str) -> tuple[str, dict[str, int]]:
        """
        Fallback pour Ollama quand l'endpoint OpenAI-compatible renvoie 500.
        https://github.com/ollama/ollama/blob/main/docs/api.md
        """
        root = base.rstrip("/")
        if root.endswith("/v1"):
            root = root[:-3]
        native_url = f"{root}/api/chat"
        native_payload: dict[str, Any] = {
            "model": selected_model,
            "messages": messages,
            "stream": False,
            # Garder le modèle "chaud" pour éviter les cold starts.
            # Ollama accepte aussi des durées (ex: "10m") selon versions; -1 = keep alive.
            "keep_alive": -1,
            "options": {
                "temperature": temperature,
                # Aligner le comportement Ollama sur "max_tokens" OpenAI.
                # (num_predict = nombre max de tokens générés)
                "num_predict": max_tokens,
                # Couper les réponses multi-paragraphes (souvent inutiles et coûteuses).
                "stop": ["\n\n"],
            },
        }
        with httpx.Client(timeout=_timeout_s()) as client:
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
        content2 = msg2.get("content")
        if not isinstance(content2, str) or not content2.strip():
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

    # Ollama peut être beaucoup plus rapide via /api/chat que via /v1/chat/completions.
    # Donc si on est sur Ollama, on tente le natif en premier.
    if looks_like_ollama:
        try:
            raw, usage = _try_ollama_native_api_chat(base=b_norm)
            reply, _ = _postprocess_llm_content(raw=raw, context=context)
            if ck:
                _cache_set(ck, reply)
            cost = _estimate_cost_usd(
                prompt_tokens=int(usage.get("prompt_tokens", 0)),
                completion_tokens=int(usage.get("completion_tokens", 0)),
                target=selected_target,
            )
            _emit_dialogue_trace(
                context,
                {
                    "trace_id": context.get("_trace_id"),
                    "target": selected_target,
                    "model": selected_model,
                    "profile": _resolve_profile(context),
                    "base_host": (urlparse(b_norm).netloc or b_norm),
                    "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                    "completion_tokens": int(usage.get("completion_tokens", 0)),
                    "estimated_cost_usd": cost,
                    "cache_hit": cache_hit,
                },
            )
            return reply
        except Exception:
            # Fallback OpenAI-compatible pour compat (et cas où /api/chat n'est pas dispo).
            pass

    with httpx.Client(timeout=_timeout_s()) as client:
        r = client.post(url, headers=headers, json=payload)
    try:
        r.raise_for_status()
        raw, usage = _parse_openai_chat_completions(r.json())
        reply, _ = _postprocess_llm_content(raw=raw, context=context)
        if ck:
            _cache_set(ck, reply)
        cost = _estimate_cost_usd(
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            target=selected_target,
        )
        _emit_dialogue_trace(
            context,
            {
                "trace_id": context.get("_trace_id"),
                "target": selected_target,
                "model": selected_model,
                "profile": _resolve_profile(context),
                "base_host": (urlparse(b_norm).netloc or b_norm),
                "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                "completion_tokens": int(usage.get("completion_tokens", 0)),
                "estimated_cost_usd": cost,
                "cache_hit": cache_hit,
            },
        )
        return reply
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        body = (e.response.text or "")[:400]
        # Si l'OpenAI-compatible casse (5xx), tenter aussi le natif Ollama si applicable.
        if status >= 500 and looks_like_ollama:
            try:
                raw, usage = _try_ollama_native_api_chat(base=b_norm)
                reply, _ = _postprocess_llm_content(raw=raw, context=context)
                if ck:
                    _cache_set(ck, reply)
                cost = _estimate_cost_usd(
                    prompt_tokens=int(usage.get("prompt_tokens", 0)),
                    completion_tokens=int(usage.get("completion_tokens", 0)),
                    target=selected_target,
                )
                _emit_dialogue_trace(
                    context,
                    {
                        "trace_id": context.get("_trace_id"),
                        "target": selected_target,
                        "model": selected_model,
                        "profile": _resolve_profile(context),
                        "base_host": (urlparse(b_norm).netloc or b_norm),
                        "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                        "completion_tokens": int(usage.get("completion_tokens", 0)),
                        "estimated_cost_usd": cost,
                        "cache_hit": cache_hit,
                    },
                )
                return reply
            except Exception as fallback_exc:
                raise RuntimeError(
                    f"HTTP {status} (openai chat/completions): {body} | fallback Ollama échoué: {fallback_exc}"
                ) from fallback_exc
        raise RuntimeError(f"HTTP {status}: {body}") from e
