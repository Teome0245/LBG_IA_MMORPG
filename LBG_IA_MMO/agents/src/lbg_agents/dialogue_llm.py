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

import httpx

# Défauts : Ollama, API OpenAI-compatible sur la même machine (port 11434).
DEFAULT_LBG_DIALOGUE_LLM_BASE_URL = "http://127.0.0.1:11434/v1"
# Valeur par défaut orientée "prod prévisible" (petit modèle rapide si disponible).
DEFAULT_LBG_DIALOGUE_LLM_MODEL = "phi4-mini:latest"

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
    # Optionnel : inclure certains champs de contexte dans la clé (évite les hits quand l'état change).
    raw_keys = os.environ.get(
        "LBG_DIALOGUE_CACHE_CONTEXT_KEYS",
        "world_npc_id,quest_state,encounter_state,world_flags",
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


def _timeout_s() -> float:
    raw = os.environ.get("LBG_DIALOGUE_LLM_TIMEOUT", "120").strip()
    try:
        return max(5.0, float(raw))
    except ValueError:
        return 120.0


def _api_key() -> str | None:
    k = os.environ.get("LBG_DIALOGUE_LLM_API_KEY", "").strip()
    return k or None


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
    lines = [
        f"Tu incarnes {speaker}, un personnage non-joueur (PNJ) dans un MMORPG médiéval-fantasy.",
        "Tu réponds en français. Reste dans ton rôle.",
        "Réponds très court: 1 à 2 phrases maximum (pas de liste), idéalement < 25 mots, sauf si le joueur demande explicitement une explication longue.",
        "Ne dis pas que tu es une intelligence artificielle ni un modèle de langage.",
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
    return "\n".join(lines)


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
    b = base_url()
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
            sp = speaker.strip() or "PNJ"
            _cache_hits_by_speaker[sp] = _cache_hits_by_speaker.get(sp, 0) + 1
            # Exposer un hint best-effort au caller (observabilité).
            try:
                context["_cache_hit"] = True
            except Exception:
                pass
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
    key = _api_key()
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

    payload: dict[str, Any] = {
        "model": model_name(),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    # Couper les sorties multi-paragraphes (souvent inutiles, coûteuses en latence).
    # Compatible OpenAI / la plupart des serveurs OpenAI-like. Ollama a aussi son propre stop dans /api/chat.
    payload["stop"] = ["\n\n"]

    def _parse_openai_chat_completions(data: Any) -> str:
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
        return content.strip()

    def _try_ollama_native_api_chat(*, base: str) -> str:
        """
        Fallback pour Ollama quand l'endpoint OpenAI-compatible renvoie 500.
        https://github.com/ollama/ollama/blob/main/docs/api.md
        """
        root = base.rstrip("/")
        if root.endswith("/v1"):
            root = root[:-3]
        native_url = f"{root}/api/chat"
        native_payload: dict[str, Any] = {
            "model": model_name(),
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
        return content2.strip()

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
            raw = _try_ollama_native_api_chat(base=b_norm)
            reply = _enforce_short_reply(raw)
            if ck:
                _cache_set(ck, reply)
            return reply
        except Exception:
            # Fallback OpenAI-compatible pour compat (et cas où /api/chat n'est pas dispo).
            pass

    with httpx.Client(timeout=_timeout_s()) as client:
        r = client.post(url, headers=headers, json=payload)
    try:
        r.raise_for_status()
        raw = _parse_openai_chat_completions(r.json())
        reply = _enforce_short_reply(raw)
        if ck:
            _cache_set(ck, reply)
        return reply
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        body = (e.response.text or "")[:400]
        # Si l'OpenAI-compatible casse (5xx), tenter aussi le natif Ollama si applicable.
        if status >= 500 and looks_like_ollama:
            try:
                raw = _try_ollama_native_api_chat(base=b_norm)
                reply = _enforce_short_reply(raw)
                if ck:
                    _cache_set(ck, reply)
                return reply
            except Exception as fallback_exc:
                raise RuntimeError(
                    f"HTTP {status} (openai chat/completions): {body} | fallback Ollama échoué: {fallback_exc}"
                ) from fallback_exc
        raise RuntimeError(f"HTTP {status}: {body}") from e
