#!/usr/bin/env python3
"""Sidecar pont IA → Core3 (file queue, snapshot joueur Phase B, PNJ pilotes Phase C)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

DEFAULT_QUEUE = Path("ia_bridge/pending.jsonl")
DEFAULT_SNAPSHOT = Path("ia_bridge/player_snapshot.json")
DEFAULT_PLAYER_SNAPSHOTS = Path("ia_bridge/player_snapshots.json")
DEFAULT_NPC_SNAPSHOTS = Path("ia_bridge/npc_snapshots.json")
DEFAULT_EVENTS = Path("ia_bridge/events.jsonl")
DEFAULT_QUEST_STATE = Path("ia_bridge/quest_state.jsonl")
DEFAULT_BIND = ("127.0.0.1", 8791)
ALLOWED_ACTIONS = frozenset({
    "say",
    "switch_zone",
    "move_to",
    "animate",
    "perform",
    "interact",
    "approach_player",
    "housing_enter",
    "vendor_buy",
    "vendor_sell",
    "craft_combine",
    "skill_forget",
    "noop",
    "npc_say",
    "npc_perform",
    "npc_path",
    "offer_quest",
})
_PILOT_REGISTRY_CACHE: dict[str, Any] | None = None
_NPC_THINK_COOLDOWN_SEC = 40.0
_NPC_SAY_MAX_LEN_DEFAULT = 180
_NPC_SAY_MAX_LEN_VENDOR = 140
_npc_think_last: dict[str, float] = {}


def invalidate_pilot_registry_cache() -> None:
    global _PILOT_REGISTRY_CACHE
    _PILOT_REGISTRY_CACHE = None


def ia_zone() -> str:
    """Planète cible (id zone Core3). Renommable via CORE3_IA_ZONE sans changer le code."""
    return os.environ.get("CORE3_IA_ZONE", "tatooine").strip() or "tatooine"


def bot_player_name() -> str:
    """Prénom du perso en ligne (nameMap Core3), pas le login compte."""
    char = os.environ.get("CORE3_IA_BOT_CHARACTER", "").strip()
    if char:
        return char
    return os.environ.get("CORE3_IA_BOT_NAME", "Bot_IA").strip() or "Bot_IA"


def queue_path() -> Path:
    raw = os.environ.get("CORE3_IA_BRIDGE_QUEUE", "").strip()
    return Path(raw) if raw else DEFAULT_QUEUE


def snapshot_path() -> Path:
    raw = os.environ.get("CORE3_IA_SNAPSHOT_PATH", "").strip()
    return Path(raw) if raw else DEFAULT_SNAPSHOT


def player_snapshots_path() -> Path:
    raw = os.environ.get("CORE3_IA_PLAYER_SNAPSHOTS_PATH", "").strip()
    return Path(raw) if raw else DEFAULT_PLAYER_SNAPSHOTS


def events_path() -> Path:
    raw = os.environ.get("CORE3_IA_EVENTS_PATH", "").strip()
    return Path(raw) if raw else DEFAULT_EVENTS


def quest_state_path() -> Path:
    raw = os.environ.get("CORE3_IA_QUEST_STATE_PATH", "").strip()
    return Path(raw) if raw else DEFAULT_QUEST_STATE


def load_quest_state() -> list[dict[str, Any]]:
    path = quest_state_path()
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    if isinstance(row, dict):
                        out.append(row)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return out


def online_players_log_path() -> Path:
    raw = os.environ.get("CORE3_IA_ONLINE_PLAYERS_LOG", "").strip()
    if raw:
        return Path(raw)
    snap = snapshot_path()
    if snap.parent.name == "ia_bridge":
        return snap.parent.parent / "log" / "online-players.log"
    return snap.parent / "log" / "online-players.log"


def _tail_text_line(path: Path, nbytes: int = 8192) -> str:
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            if size <= 0:
                return ""
            fh.seek(max(0, size - nbytes))
            chunk = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return ""
    lines = [ln for ln in chunk.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def player_in_online_log(first_name: str) -> bool | None:
    """True si le prénom figure dans la dernière ligne online-players.log."""
    path = online_players_log_path()
    if not path.is_file():
        return None
    line = _tail_text_line(path)
    if not line:
        return None
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return None
    if payload.get("isServerLoading") is True:
        return False
    want = first_name.strip().lower()
    for client in payload.get("clients") or []:
        if str(client.get("firstName", "")).strip().lower() == want:
            return True
    return False


def npc_snapshots_path() -> Path:
    raw = os.environ.get("CORE3_IA_NPC_SNAPSHOTS_PATH", "").strip()
    return Path(raw) if raw else DEFAULT_NPC_SNAPSHOTS


def load_social_events(
    *,
    player: str | None = None,
    after: str | None = None,
    limit: int = 50,
    include_actor: bool = False,
) -> list[dict[str, Any]]:
    path = events_path()
    if limit < 1:
        limit = 1
    if limit > 200:
        limit = 200
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    wanted = (player or "").strip().lower()
    after_marker = (after or "").strip()
    parsed: list[dict[str, Any]] = []
    for line in lines[-2000:]:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            parsed.append(event)
    start_idx = 0
    if after_marker:
        for idx, event in enumerate(parsed):
            if str(event.get("event_id") or "") == after_marker:
                start_idx = idx + 1
                break
        # Curseur obsolète (id absent du journal) : ne pas bloquer la perception.
    out: list[dict[str, Any]] = []
    for event in parsed[start_idx:]:
        if wanted:
            target = str(event.get("target") or "").strip().lower()
            actor = str(event.get("actor") or "").strip().lower()
            if target != wanted and not (include_actor and actor == wanted):
                continue
        out.append(event)
    return out[-limit:]


def npc_catalog_path() -> Path:
    raw = os.environ.get("CORE3_IA_NPC_CATALOG_JSON", "").strip()
    if raw:
        return Path(raw)
    here = Path(__file__).resolve().parent
    return here.parent.parent / "content" / "core3" / "core3_npc_catalog.json"


def npc_pilots_registry_path() -> Path:
    raw = os.environ.get("CORE3_IA_NPC_PILOTS_JSON", "").strip()
    if raw:
        return Path(raw)
    here = Path(__file__).resolve().parent
    for candidate in (
        here.parent.parent / "content" / "core3" / "core3_npc_pilots.json",
        here / "core3_npc_pilots.json",
    ):
        if candidate.is_file():
            return candidate
    return here.parent.parent / "content" / "core3" / "core3_npc_pilots.json"


def _index_pilot_rows(pilots: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_pilot: dict[str, dict[str, Any]] = {}
    by_lbg: dict[str, dict[str, Any]] = {}
    for row in pilots:
        if not isinstance(row, dict):
            continue
        pid = str(row.get("pilot_id", "")).strip()
        if not pid:
            continue
        by_pilot[pid] = row
        lbg = str(row.get("lbg_npc_id", "")).strip()
        if lbg:
            by_lbg[lbg] = row
    return by_pilot, by_lbg


def _slot_to_pilot_row(
    slot: dict[str, Any],
    profile: dict[str, Any],
    *,
    profile_id: str = "",
    roster_id: str = "",
) -> dict[str, Any]:
    binding = slot.get("binding") if isinstance(slot.get("binding"), dict) else {}
    spawn = binding.get("spawn") if isinstance(binding.get("spawn"), dict) else {}
    return {
        "pilot_id": str(slot.get("pilot_id", "")).strip(),
        "lbg_npc_id": str(slot.get("lbg_npc_id") or profile.get("lbg_npc_id", "")).strip(),
        "display_name": str(slot.get("display_name", "")).strip(),
        "profile_id": profile_id,
        "mobile_template": str(binding.get("mobile_template", "")).strip(),
        "spawn": spawn,
        "status": "active",
        "roster_id": roster_id,
        "_profile": profile,
    }


def _entry_to_pilot_row(entry: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    binding = entry.get("binding") if isinstance(entry.get("binding"), dict) else {}
    spawn = binding.get("spawn") if isinstance(binding.get("spawn"), dict) else {}
    return {
        "pilot_id": str(entry.get("pilot_id", "")).strip(),
        "lbg_npc_id": str(profile.get("lbg_npc_id", entry.get("lbg_npc_id", ""))).strip(),
        "display_name": str(entry.get("display_name", "")).strip(),
        "profile_id": str(entry.get("profile_id", "")).strip(),
        "mobile_template": str(binding.get("mobile_template", "")).strip(),
        "spawn": spawn,
        "status": str(entry.get("status", "")).strip(),
        "_profile": profile,
    }


def _load_pilots_from_catalog(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        cat = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(cat, dict) or int(cat.get("schema_version", 0)) < 2:
        return None
    profiles = cat.get("profiles")
    if not isinstance(profiles, dict):
        profiles = {}
    pilots: list[dict[str, Any]] = []
    for entry in cat.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("status", "")).strip().lower() != "active":
            continue
        pid = str(entry.get("pilot_id", "")).strip()
        prof_id = str(entry.get("profile_id", "")).strip()
        if not pid:
            continue
        profile = profiles.get(prof_id, {})
        if not isinstance(profile, dict):
            profile = {}
        pilots.append(_entry_to_pilot_row(entry, profile))
    seen_pilot_ids = {p["pilot_id"] for p in pilots}
    for roster in cat.get("rosters") or []:
        if not isinstance(roster, dict):
            continue
        if str(roster.get("status", "")).strip().lower() != "active":
            continue
        prof_id = str(roster.get("profile_id", "")).strip()
        profile = profiles.get(prof_id, {})
        if not isinstance(profile, dict):
            profile = {}
        roster_id = str(roster.get("roster_id", "")).strip()
        for slot in roster.get("slots") or []:
            if not isinstance(slot, dict):
                continue
            pid = str(slot.get("pilot_id", "")).strip()
            if not pid or pid in seen_pilot_ids:
                continue
            slot_prof_id = str(slot.get("profile_id") or prof_id).strip()
            slot_profile = profiles.get(slot_prof_id, profile)
            if not isinstance(slot_profile, dict):
                slot_profile = profile
            pilots.append(
                _slot_to_pilot_row(
                    slot,
                    slot_profile,
                    profile_id=slot_prof_id,
                    roster_id=roster_id,
                )
            )
            seen_pilot_ids.add(pid)
    by_pilot, by_lbg = _index_pilot_rows(pilots)
    return {
        "schema_version": 2,
        "zone": str(cat.get("zone", ia_zone())),
        "registry_source": "catalog",
        "catalog_path": str(path.resolve()),
        "profiles": profiles,
        "pilots": pilots,
        "_by_pilot_id": by_pilot,
        "_by_lbg_npc_id": by_lbg,
    }


def _load_pilots_legacy(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "schema_version": 1,
            "zone": ia_zone(),
            "registry_source": "legacy",
            "pilots": [],
            "_by_pilot_id": {},
            "_by_lbg_npc_id": {},
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        data = {"pilots": []}
    pilots = data.get("pilots")
    if not isinstance(pilots, list):
        pilots = []
    by_pilot, by_lbg = _index_pilot_rows(pilots)
    data["registry_source"] = "legacy"
    data["pilots"] = pilots
    data["_by_pilot_id"] = by_pilot
    data["_by_lbg_npc_id"] = by_lbg
    return data


def load_pilot_registry() -> dict[str, Any]:
    global _PILOT_REGISTRY_CACHE
    if _PILOT_REGISTRY_CACHE is not None:
        return _PILOT_REGISTRY_CACHE
    catalog = _load_pilots_from_catalog(npc_catalog_path())
    if catalog is not None and catalog.get("pilots"):
        _PILOT_REGISTRY_CACHE = catalog
        return catalog
    _PILOT_REGISTRY_CACHE = _load_pilots_legacy(npc_pilots_registry_path())
    return _PILOT_REGISTRY_CACHE


def pilot_row_public(row: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in row.items() if not str(k).startswith("_")}
    prof = row.get("_profile")
    if isinstance(prof, dict):
        llm = prof.get("llm")
        if isinstance(llm, dict) and llm.get("system_hint"):
            out["llm_system_hint"] = llm.get("system_hint")
    return out


def resolve_profile_for_row(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {}
    prof = row.get("_profile")
    if isinstance(prof, dict):
        return prof
    prof_id = str(row.get("profile_id", "")).strip()
    if prof_id:
        reg = load_pilot_registry()
        profiles = reg.get("profiles")
        if isinstance(profiles, dict):
            p = profiles.get(prof_id)
            if isinstance(p, dict):
                return p
    return {}


def resolve_pilot_row(npc_ref: str) -> dict[str, Any] | None:
    ref = (npc_ref or "").strip()
    if not ref:
        return None
    reg = load_pilot_registry()
    by_pilot = reg.get("_by_pilot_id", {})
    by_lbg = reg.get("_by_lbg_npc_id", {})
    if ref in by_pilot:
        return by_pilot[ref]
    if ref in by_lbg:
        return by_lbg[ref]
    return None


def pilot_id_from_row(row: dict[str, Any]) -> str:
    return str(row.get("pilot_id", "")).strip()


def load_npc_snapshots() -> dict[str, dict[str, Any]]:
    path = npc_snapshots_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key, val in data.items():
        if isinstance(val, dict):
            out[str(key)] = val
    return out


def load_npc_snapshot(npc_ref: str) -> dict[str, Any]:
    row = resolve_pilot_row(npc_ref)
    pilot_id = pilot_id_from_row(row) if row else (npc_ref or "").strip()
    snaps = load_npc_snapshots()
    snap = snaps.get(pilot_id, {})
    if not isinstance(snap, dict):
        snap = {}
    if row:
        snap.setdefault("pilot_id", pilot_id)
        snap.setdefault("lbg_npc_id", row.get("lbg_npc_id", ""))
        snap.setdefault("display_name", row.get("display_name", ""))
    if not snap:
        return {
            "online": False,
            "pilot_id": pilot_id,
            "reason": "npc_snapshot_missing",
            "path": str(npc_snapshots_path().resolve()),
        }
    ts = snap.get("ts")
    if isinstance(ts, (int, float)):
        age = time.time() - float(ts)
        snap["age_s"] = round(age, 2)
        if age > snapshot_max_age_s():
            snap["stale"] = True
    if "online" not in snap:
        snap["online"] = bool(
            snap.get("ts") is not None
            and snap.get("x") is not None
            and snap.get("y") is not None
        )
    return snap


def format_npc_observation(snap: dict[str, Any]) -> str:
    if not snap.get("online"):
        reason = snap.get("reason", "offline")
        return f"PNJ pilote hors ligne ({reason})."
    name = snap.get("name") or snap.get("display_name") or snap.get("pilot_id", "?")
    zone = snap.get("zone", "?")
    x, y, z = snap.get("x"), snap.get("y"), snap.get("z")
    parts = [
        f"PNJ {name} (pilot_id={snap.get('pilot_id')}, lbg={snap.get('lbg_npc_id')})",
        f"zone={zone} position=({x},{y},{z})",
    ]
    if snap.get("stale"):
        parts.append("(snapshot un peu ancien)")
    return ". ".join(parts) + "."


def snapshot_max_age_s() -> float:
    try:
        return float(os.environ.get("CORE3_IA_SNAPSHOT_MAX_AGE_S", "8"))
    except ValueError:
        return 8.0


def llm_base_url() -> str:
    return os.environ.get("LBG_DIALOGUE_LLM_BASE_URL", "http://192.168.0.110:11434/v1").rstrip("/")


def llm_model() -> str:
    return os.environ.get("LBG_DIALOGUE_LLM_MODEL", "phi4-mini:latest").strip() or "phi4-mini:latest"


def llm_api_key() -> str:
    for name in ("LBG_DIALOGUE_LLM_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY"):
        val = os.environ.get(name, "").strip()
        if val:
            return val
    return ""


def llm_timeout_s() -> float:
    try:
        return max(5.0, float(os.environ.get("LBG_DIALOGUE_LLM_TIMEOUT", "45")))
    except ValueError:
        return 45.0


def llm_timeout_for_route(route: dict[str, Any]) -> float:
    tier = str(route.get("target", "")).lower()
    if tier == "fast":
        raw = os.environ.get("CORE3_IA_LLM_TIMEOUT_FAST", os.environ.get("LBG_ORCHESTRATOR_INTENT_LLM_TIMEOUT_S", "25"))
        try:
            return max(5.0, float(raw))
        except ValueError:
            return 25.0
    if tier == "local":
        raw = os.environ.get("CORE3_IA_LLM_TIMEOUT_LOCAL", "20")
        try:
            return max(5.0, float(raw))
        except ValueError:
            return 20.0
    return llm_timeout_s()


def llm_max_tokens(override: int | None = None) -> int:
    if override is not None:
        try:
            return max(32, int(override))
        except (TypeError, ValueError):
            pass
    try:
        raw = os.environ.get("CORE3_IA_LLM_MAX_TOKENS", os.environ.get("LBG_DIALOGUE_LLM_MAX_TOKENS", "120"))
        return max(32, int(raw))
    except ValueError:
        return 120


def _strip_env_value(val: str) -> str:
    val = val.strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
        return val[1:-1].strip()
    return val


def _expand_env_refs(val: str) -> str:
    val = _strip_env_value(val)
    for _ in range(8):
        match = re.search(r"\$\{([^}]+)\}", val)
        if not match:
            break
        ref = os.environ.get(match.group(1), "").strip()
        val = val[: match.start()] + ref + val[match.end() :]
    return val.strip()


def load_env_files() -> None:
    """systemd ne développe pas ${VAR} dans EnvironmentFile — on réexpande depuis les fichiers."""
    for path in ("/etc/lbg-ia-mmo.env", "/etc/lbg-core3-ia.env"):
        p = Path(path)
        if not p.is_file():
            continue
        for raw_line in p.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if not key:
                continue
            os.environ[key] = _expand_env_refs(value)


def dialogue_target() -> str:
    raw = os.environ.get(
        "CORE3_IA_DIALOGUE_TARGET",
        os.environ.get("LBG_ORCHESTRATOR_DIALOGUE_TARGET_DEFAULT", "auto"),
    )
    return (raw or "auto").strip().lower()


def _is_truthy(val: str) -> bool:
    return val.strip().lower() in ("1", "true", "yes", "on")


def _resolve_secret_ref(raw: str) -> str:
    val = _expand_env_refs(raw)
    if val.startswith("${") and val.endswith("}"):
        return os.environ.get(val[2:-1], "").strip()
    return val


def _tier_route(tier: str) -> dict[str, Any] | None:
    """Même contrat env que lbg_agents.dialogue_llm._tier_route (sans dépendre du paquet sur 245)."""
    t = tier.strip().lower()
    if t == "local":
        base = os.environ.get("LBG_DIALOGUE_LLM_BASE_URL", "").strip().rstrip("/")
        if not base:
            return None
        return {
            "target": "local",
            "base_url": base,
            "model": os.environ.get("LBG_DIALOGUE_LLM_MODEL", "phi4-mini:latest").strip(),
            "api_key": _resolve_secret_ref(os.environ.get("LBG_DIALOGUE_LLM_API_KEY", "")),
        }
    if t == "fast":
        if not _is_truthy(os.environ.get("LBG_DIALOGUE_FAST_ENABLED", "0")):
            return None
        base = os.environ.get("LBG_DIALOGUE_FAST_BASE_URL", "").strip().rstrip("/")
        model = os.environ.get("LBG_DIALOGUE_FAST_MODEL", "").strip()
        key = _resolve_secret_ref(os.environ.get("LBG_DIALOGUE_FAST_API_KEY", ""))
        if not key:
            key = _resolve_secret_ref(os.environ.get("GROQ_API_KEY", ""))
        if not (base and model):
            return None
        return {"target": "fast", "base_url": base, "model": model, "api_key": key}
    if t == "remote":
        if not _is_truthy(os.environ.get("LBG_DIALOGUE_REMOTE_ENABLED", "0")):
            return None
        base = os.environ.get("LBG_DIALOGUE_REMOTE_BASE_URL", "").strip().rstrip("/")
        model = os.environ.get("LBG_DIALOGUE_REMOTE_MODEL", "").strip()
        key = _resolve_secret_ref(os.environ.get("LBG_DIALOGUE_REMOTE_API_KEY", ""))
        if not (base and model):
            return None
        return {"target": "remote", "base_url": base, "model": model, "api_key": key}
    if t == "glm":
        if not _is_truthy(os.environ.get("LBG_DIALOGUE_GLM_ENABLED", "0")):
            return None
        base = os.environ.get("LBG_DIALOGUE_GLM_BASE_URL", "").strip().rstrip("/")
        model = os.environ.get("LBG_DIALOGUE_GLM_MODEL", "z-ai/glm-5.2").strip()
        key = _resolve_secret_ref(os.environ.get("LBG_DIALOGUE_GLM_API_KEY", ""))
        thinking = os.environ.get("LBG_DIALOGUE_GLM_THINKING", "high").strip().lower()
        if thinking not in ("disabled", "high", "max"):
            thinking = "high"
        if not base:
            return None
        return {
            "target": "glm",
            "base_url": base,
            "model": model,
            "api_key": key,
            "thinking_effort": thinking,
        }
    return None


def resolve_llm_routes() -> list[dict[str, Any]]:
    """Paliers LLM alignés sur LBG_DIALOGUE_* / lbg-ia-mmo.env (comme agents + orchestrateur)."""
    target = dialogue_target()
    if target == "auto":
        routes: list[dict[str, Any]] = []
        order = os.environ.get("CORE3_IA_AUTO_ORDER", "fast")
        for part in order.split(","):
            route = _tier_route(part.strip().lower())
            if route:
                routes.append(route)
        if routes:
            return routes
        target = "local"

    if target in ("local", "fast", "remote", "glm"):
        route = _tier_route(target)
        if route:
            return [route]

    return [
        {
            "target": "env",
            "base_url": llm_base_url(),
            "model": llm_model(),
            "api_key": llm_api_key(),
        }
    ]


def _llm_http_complete(
    route: dict[str, Any],
    messages: list[dict[str, str]],
    *,
    max_tokens: int | None = None,
) -> str:
    base = str(route.get("base_url", "")).rstrip("/")
    if not base:
        raise RuntimeError("route LLM sans base_url")
    url = f"{base}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        # Groq renvoie 403 avec le User-Agent par défaut de urllib (Python-urllib/*).
        "User-Agent": os.environ.get(
            "LBG_DIALOGUE_LLM_USER_AGENT", "curl/8.5.0"
        ).strip()
        or "curl/8.5.0",
    }
    key = str(route.get("api_key", "")).strip() or llm_api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    if route.get("target") == "glm" and "openrouter.ai" in base:
        headers["HTTP-Referer"] = os.environ.get(
            "LBG_OPENROUTER_HTTP_REFERER", "https://github.com/lbg-ia-mmo"
        )
        headers["X-Title"] = os.environ.get("LBG_OPENROUTER_X_TITLE", "LBG-IA-MMO Agent")

    body: dict[str, Any] = {
        "model": str(route.get("model", llm_model())),
        "messages": messages,
        "temperature": float(os.environ.get("LBG_DIALOGUE_LLM_TEMPERATURE", "0.3")),
        "max_tokens": llm_max_tokens(max_tokens),
    }
    if route.get("target") == "glm":
        thinking_effort = str(route.get("thinking_effort", "high")).lower()
        if thinking_effort == "disabled":
            body["chat_template_kwargs"] = {"enable_thinking": False}
        else:
            body["reasoning_effort"] = thinking_effort
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=llm_timeout_for_route(route)) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return str(payload["choices"][0]["message"]["content"])


def enqueue_line(line: str) -> None:
    path = queue_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = line.strip().replace("\n", " ").replace("\r", "")
    if not clean:
        raise ValueError("ligne vide")
    with path.open("a", encoding="utf-8") as fh:
        fh.write(clean + "\n")


def game_text(value: str, *, max_chars: int = 140) -> str:
    """Texte sûr pour le client SWG : ASCII, court, sans séparateur de queue."""
    text = str(value or "")
    replacements = {
        "œ": "oe",
        "Œ": "Oe",
        "æ": "ae",
        "Æ": "Ae",
        "…": "...",
        "≤": "<=",
        "«": '"',
        "»": '"',
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.replace("|", "/")
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[: max_chars - 3].rstrip() + "..."
    return text


def format_command(action: str, player: str, zone: str = "", x: float = 0, y: float = 0, z: float = 0, message: str = "") -> str:
    clean_message = game_text(message)
    return "|".join(
        [
            action,
            player,
            zone,
            str(x),
            str(y),
            str(z),
            clean_message,
        ]
    )


def load_snapshot(requested_player: str | None = None) -> dict[str, Any]:
    player = (requested_player or bot_player_name()).strip()
    multi_path = player_snapshots_path()
    if multi_path.is_file():
        try:
            multi = json.loads(multi_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            multi = None
        if isinstance(multi, dict):
            snaps = multi.get("players") if isinstance(multi.get("players"), dict) else multi
            if isinstance(snaps, dict):
                for key, value in snaps.items():
                    if str(key).strip().lower() == player.lower() and isinstance(value, dict):
                        data = dict(value)
                        data.setdefault("player", player)
                        ts = data.get("ts")
                        if isinstance(ts, (int, float)):
                            data["age_s"] = round(time.time() - float(ts), 2)
                        listed = player_in_online_log(player)
                        if listed is True:
                            data["online"] = True
                            data.pop("reason", None)
                            data.pop("stale", None)
                        elif listed is False:
                            data["online"] = False
                            data["reason"] = "not_in_online_log"
                        return data

    path = snapshot_path()
    if not path.is_file():
        return {
            "online": False,
            "player": player,
            "reason": "snapshot_missing",
            "path": str(path.resolve()),
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "online": False,
            "player": player,
            "reason": "snapshot_invalid",
            "detail": str(exc),
            "path": str(path.resolve()),
        }
    if not isinstance(data, dict):
        return {"online": False, "player": player, "reason": "snapshot_invalid"}
    snap_player = str(data.get("player", "")).strip()
    if snap_player and player and snap_player.lower() != player.lower():
        listed = player_in_online_log(player)
        if listed is True:
            return {
                "online": True,
                "player": player,
                "requested_player": player,
                "snapshot_player": snap_player,
                "player_mismatch": True,
                "reason": "legacy_snapshot_for_other_player",
            }
        data["requested_player"] = player
        data["player_mismatch"] = True
    ts = data.get("ts")
    age = 0.0
    if isinstance(ts, (int, float)):
        age = time.time() - float(ts)
        data["age_s"] = round(age, 2)
    listed = player_in_online_log(player)
    if listed is True:
        data = dict(data)
        data["online"] = True
        data.pop("reason", None)
        data.pop("stale", None)
    elif listed is False:
        data = dict(data)
        data["online"] = False
        data["reason"] = "not_in_online_log"
    elif age > snapshot_max_age_s() and data.get("online"):
        data = dict(data)
        data["stale"] = True
        data["online"] = False
        data["reason"] = "snapshot_stale"
    return data


def lia_bot_systemd_unit() -> str:
    return os.environ.get("LBG_CORE3_LIA_BOT_SYSTEMD_UNIT", "lbg-core3-ia-bot-client.service").strip()


def lia_connect_script() -> str:
    return os.environ.get(
        "LBG_CORE3_LIA_CONNECT_SCRIPT",
        "/opt/LBG_IA_MMO/infra/scripts/run_core3_ia_bot_client_vm.sh",
    ).strip()


def lia_connect_mode() -> str:
    """systemd | script — systemd recommandé sur VM 245."""
    return os.environ.get("LBG_CORE3_LIA_CONNECT_MODE", "systemd").strip().lower() or "systemd"


def _systemctl(*args: str, timeout_s: float = 30.0) -> subprocess.CompletedProcess[str]:
    cmd = list(args)
    if cmd and cmd[0] == "systemctl":
        cmd = ["sudo", "-n", *cmd]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )


def _bot_systemd_unit(player_id: str) -> str:
    try:
        from lbg_agents.core3_players import get_ai_player

        return get_ai_player(player_id).systemd_unit
    except Exception:
        if player_id == "nix":
            return "lbg-core3-ia-bot-client-nix.service"
        return lia_bot_systemd_unit()


def _trigger_bot_connect(*, player_id: str, force_restart: bool) -> dict[str, Any]:
    unit = _bot_systemd_unit(player_id)
    if not unit:
        return {"ok": False, "error": "systemd_unit_missing", "player_id": player_id}
    if force_restart:
        cp = _systemctl("systemctl", "restart", unit)
        action = "restart"
    else:
        active = _systemctl("systemctl", "is-active", "--quiet", unit)
        if active.returncode == 0:
            return {
                "ok": True,
                "mode": "systemd",
                "unit": unit,
                "player_id": player_id,
                "action": "already_active",
            }
        cp = _systemctl("systemctl", "start", unit)
        action = "start"
    return {
        "ok": cp.returncode == 0,
        "mode": "systemd",
        "unit": unit,
        "player_id": player_id,
        "action": action,
        "returncode": cp.returncode,
        "stderr": (cp.stderr or "").strip()[:500],
    }


def _trigger_lia_connect(*, force_restart: bool) -> dict[str, Any]:
    mode = lia_connect_mode()
    if mode == "script":
        script = lia_connect_script()
        if not script or not os.path.isfile(script):
            return {"ok": False, "error": "connect_script_missing", "path": script}
        proc = subprocess.Popen(
            ["/bin/bash", script],
            cwd=os.path.dirname(script) or None,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return {"ok": True, "mode": "script", "pid": proc.pid, "script": script, "player_id": "lia"}

    return _trigger_bot_connect(player_id="lia", force_restart=force_restart)


def connect_ai_player(
    player_id: str,
    *,
    wait: bool = True,
    wait_s: int = 120,
    force_restart: bool = False,
) -> dict[str, Any]:
    """Lance core3client (systemd) et attend que le joueur soit visible cote serveur."""
    try:
        from lbg_agents.core3_players import get_ai_player

        player = get_ai_player(player_id)
        firstname = player.firstname
    except Exception as exc:
        return {"ok": False, "outcome": "unknown_player", "player_id": player_id, "error": str(exc)}

    snap = load_snapshot(firstname)
    if snap.get("online") and not force_restart:
        return {"ok": True, "outcome": "already_online", "player_id": player_id, "player": firstname, "snapshot": snap}

    reason = str(snap.get("reason") or "").strip().lower()
    if reason in {"not_in_online_log", "snapshot_stale", "player_offline"}:
        force_restart = True

    trigger = _trigger_bot_connect(player_id=player_id, force_restart=force_restart)
    out: dict[str, Any] = {
        "ok": bool(trigger.get("ok")),
        "outcome": "connect_started",
        "player_id": player_id,
        "player": firstname,
        "trigger": trigger,
    }
    if not trigger.get("ok"):
        out["outcome"] = "connect_trigger_failed"
        return out

    if not wait:
        out["outcome"] = "connect_started_no_wait"
        return out

    deadline = time.time() + max(15, min(int(wait_s), 600))
    last = snap
    while time.time() < deadline:
        time.sleep(3.0)
        last = load_snapshot(firstname)
        if last.get("online"):
            return {
                "ok": True,
                "outcome": "connected",
                "player_id": player_id,
                "player": firstname,
                "trigger": trigger,
                "snapshot": last,
            }

    out.update(
        {
            "ok": False,
            "outcome": "connect_timeout",
            "snapshot": last,
            "wait_s": int(wait_s),
        }
    )
    return out


def lia_connect_player(
    *,
    wait: bool = True,
    wait_s: int = 120,
    force_restart: bool = False,
) -> dict[str, Any]:
    """Lance core3client (systemd/script) et attend que Lia soit visible côté serveur."""
    return connect_ai_player("lia", wait=wait, wait_s=wait_s, force_restart=force_restart)


def format_observation(snap: dict[str, Any]) -> str:
    if not snap.get("online"):
        reason = snap.get("reason", "offline")
        return f"Joueur hors ligne ({reason})."
    zone = snap.get("zone", "?")
    x, y, z = snap.get("x"), snap.get("y"), snap.get("z")
    hp, action, mind = snap.get("hp"), snap.get("action"), snap.get("mind")
    name = snap.get("player", bot_player_name())
    parts = [
        f"{name} en ligne sur zone={zone}",
        f"position=({x},{y},{z})",
        f"HAM hp={hp} action={action} mind={mind}",
    ]
    if snap.get("stale"):
        parts.append("(snapshot un peu ancien)")
    return ". ".join(parts) + "."


def _player_system_prompt(incarnation: bool = False) -> str:
    if incarnation:
        try:
            from lbg_agents.lia_orchestrator import lia_system_prompt

            return lia_system_prompt()
        except Exception:
            pass
    return (
        f"Tu pilotes un bot joueur SWG (Serveur Prime, planète {ia_zone()}). "
        "Réponds UNIQUEMENT en JSON : "
        '{"action":"say|move_to|animate|perform|interact|approach_player|switch_zone|noop",'
        '"zone":"tatooine","x":0,"y":0,"z":0,"message":""}. '
        "Le champ message doit etre en ASCII sans accents, court (max 18 mots), naturel, sans jargon interne. "
        "say : bulle. move_to : coords. animate : nom anim brut. "
        "perform : message = id catalogue (dance, greet, search, forage, …). "
        "interact : message = kind:target (greet, offer_trade, invite_group, request_duel, examine, assist). "
        "approach_player : prénom IG. switch_zone : zone. noop : rien."
    )


def llm_chat(
    user_prompt: str,
    snapshot: dict[str, Any],
    *,
    incarnation: bool = False,
    orchestrator_brain: dict[str, Any] | None = None,
) -> str:
    obs = format_observation(snapshot)
    user_parts = [f"Observation serveur : {obs}", f"Consigne : {user_prompt}"]
    if incarnation:
        try:
            from lbg_agents.lia_orchestrator import relay_status_block

            relay_block = relay_status_block()
            if relay_block:
                user_parts.insert(1, relay_block)
        except Exception:
            pass
    if isinstance(orchestrator_brain, dict):
        try:
            from lbg_agents.lia_orchestrator import brain_context_block

            block = brain_context_block(orchestrator_brain)
            if block:
                user_parts.append(block)
        except Exception:
            pass
    messages = [
        {"role": "system", "content": _player_system_prompt(incarnation=incarnation)},
        {"role": "user", "content": "\n".join(user_parts)},
    ]
    return llm_chat_messages(messages)


def parse_action_json(text: str) -> dict[str, Any]:
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if not match:
        raise ValueError("pas de JSON dans la réponse LLM")
    return json.loads(match.group(0))


def llm_npc_chat(
    user_prompt: str,
    snap: dict[str, Any],
    pilot_row: dict[str, Any] | None = None,
) -> str:
    obs = format_npc_observation(snap)
    name = snap.get("name") or snap.get("display_name") or snap.get("pilot_id", "PNJ")
    profile = resolve_profile_for_row(pilot_row)
    llm_cfg = profile.get("llm") if isinstance(profile.get("llm"), dict) else {}
    hint = str(llm_cfg.get("system_hint", "")).strip()
    role = str(profile.get("role", "npc")).strip()
    hint_block = f" Rôle : {role}. {hint}" if hint else ""
    hooks = profile.get("quest_hooks")
    hook_block = ""
    if isinstance(hooks, list) and hooks:
        hook_block = f" Quêtes (stub) : {', '.join(str(h) for h in hooks[:5])}."
    allowed_raw = profile.get("actions_allowed")
    allowed = (
        {str(a).strip().lower() for a in allowed_raw}
        if isinstance(allowed_raw, list)
        else {"npc_say", "noop"}
    )
    if "offer_quest" in allowed:
        action_doc = (
            '{"action":"npc_say|npc_perform|npc_path|offer_quest|vendor_sell|noop","message":""}. '
            "offer_quest : proposer une mission locale (spatial chat + stub journal, pas de JSON quête). "
            "npc_perform : geste (wipe_brow, wave, dance). npc_path : message=post ou home, ou coords x/y dans le JSON. "
            "vendor_sell : message='Vendeur|0' pour rachat inventaire (MVP). "
        )
    elif {"npc_perform", "npc_path"} & allowed:
        action_doc = (
            '{"action":"npc_say|npc_perform|npc_path|noop","message":""}. '
            "npc_perform : geste au comptoir. npc_path : message=post pour ajuster position. "
        )
    else:
        action_doc = '{"action":"npc_say|noop","message":""}. '
    messages = [
        {
            "role": "system",
            "content": (
                f"Tu pilotes un PNJ SWG (Serveur Prime, {ia_zone()}), nom affiché : {name}.{hint_block}{hook_block} "
                f"Réponds UNIQUEMENT en JSON : {action_doc}"
                "npc_say : réplique courte FR (spatial chat, max ~200 caractères). "
                "noop : silence. Pas de markdown."
            ),
        },
        {
            "role": "user",
            "content": f"Observation serveur : {obs}\nConsigne : {user_prompt}",
        },
    ]
    max_tok = llm_cfg.get("max_tokens")
    try:
        max_tok_int = int(max_tok) if max_tok is not None else None
    except (TypeError, ValueError):
        max_tok_int = None
    return llm_chat_messages(messages, max_tokens=max_tok_int)


def llm_chat_messages(
    messages: list[dict[str, str]],
    *,
    max_tokens: int | None = None,
) -> str:
    routes = resolve_llm_routes()
    last_err: Exception | None = None
    for route in routes:
        tier = route.get("target", "?")
        try:
            return _llm_http_complete(route, messages, max_tokens=max_tokens)
        except urllib.error.HTTPError as exc:
            last_err = exc
            if exc.code in (401, 403, 429, 500, 502, 503, 504):
                sys.stderr.write(f"core3_ia_sidecar: palier {tier} HTTP {exc.code}, essai suivant\n")
                continue
            raise
        except urllib.error.URLError as exc:
            last_err = exc
            sys.stderr.write(f"core3_ia_sidecar: palier {tier} injoignable ({exc}), essai suivant\n")
            continue
    if last_err is not None:
        raise last_err
    raise RuntimeError("aucun palier LLM disponible (vérifier LBG_DIALOGUE_* / clés API)")


def npc_think_on_cooldown(pilot_id: str) -> bool:
    last = _npc_think_last.get(pilot_id, 0.0)
    return (time.time() - last) < _NPC_THINK_COOLDOWN_SEC


def mark_npc_think(pilot_id: str) -> None:
    _npc_think_last[pilot_id] = time.time()


def clamp_npc_say_message(msg: str, profile: dict[str, Any]) -> str:
    text = str(msg or "").strip()
    role = str(profile.get("role", "")).strip().lower()
    max_len = _NPC_SAY_MAX_LEN_VENDOR if role == "vendor" else _NPC_SAY_MAX_LEN_DEFAULT
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def normalize_npc_action(
    action: dict[str, Any],
    pilot_id: str,
    pilot_row: dict[str, Any] | None = None,
) -> tuple[str, str]:
    profile = resolve_profile_for_row(pilot_row)
    allowed_raw = profile.get("actions_allowed")
    allowed = (
        {str(a).strip().lower() for a in allowed_raw}
        if isinstance(allowed_raw, list)
        else {"npc_say", "noop"}
    )
    act = str(action.get("action", "npc_say")).strip().lower()
    if "|" in act:
        act = act.split("|", 1)[0].strip()
    if act not in allowed:
        act = "noop"
        msg = "Action non autorisee — attente."
    elif act == "npc_say":
        msg = clamp_npc_say_message(str(action.get("message", "")), profile)
    elif act in {"npc_perform", "npc_path"}:
        msg = str(action.get("message", "") or act)
    elif act == "vendor_sell":
        msg = str(action.get("message", "Vendeur|0"))
    else:
        msg = str(action.get("message", ""))
    snap = load_npc_snapshot(pilot_id)
    zone = str(snap.get("zone") or ia_zone())
    line = format_command(
        act,
        pilot_id,
        zone,
        float(snap.get("x", 0) or 0),
        float(snap.get("y", 0) or 0),
        float(snap.get("z", 0) or 0),
        msg,
    )
    return act, line


def normalize_action(action: dict[str, Any], player: str) -> tuple[str, str]:
    act = str(action.get("action", "say")).strip().lower()
    if act not in ALLOWED_ACTIONS:
        act = "say"
        msg = "Action non autorisée — attente."
    else:
        msg = str(action.get("message", ""))
    line = format_command(
        act,
        player,
        str(action.get("zone", "") or ia_zone()),
        float(action.get("x", 0)),
        float(action.get("y", 0)),
        float(action.get("z", 0)),
        msg,
    )
    return act, line


def _ascii_lower(text: str) -> str:
    return unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii").lower()


def direct_lia_hear_command(from_player: str, text: str) -> dict[str, Any] | None:
    msg = _ascii_lower(text)
    who = re.sub(r"[^A-Za-z0-9_-]+", "", from_player or "Gally") or "Gally"
    if any(word in msg for word in ("danse", "danser", "dance", "dancer")):
        line = format_command("perform", bot_player_name(), ia_zone(), 0, 0, 0, "dance")
        return {"action": "perform", "line": line, "reason": "hear_dance_request"}
    if any(word in msg for word in ("fouille", "fouiller", "cherche", "chercher", "scan", "inspect")):
        line = format_command("perform", bot_player_name(), ia_zone(), 0, 0, 0, "search")
        return {"action": "perform", "line": line, "reason": "hear_search_request"}
    if any(word in msg for word in ("viens", "approche", "rejoins", "follow", "come")):
        line = format_command("approach_player", bot_player_name(), ia_zone(), 0, 0, 0, who)
        return {"action": "approach_player", "line": line, "reason": "hear_approach_request"}
    return None


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, obj: dict[str, Any]) -> None:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.log_date_time_string(), fmt % args))

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path in ("/healthz", "/health"):
            self._json(
                200,
                {
                    "ok": True,
                    "phase": "C2",
                    "npc_catalog": str(npc_catalog_path().resolve()),
                    "registry_source": load_pilot_registry().get("registry_source", "?"),
                    "npc_pilots_registry": str(npc_pilots_registry_path().resolve()),
                    "npc_snapshots": str(npc_snapshots_path().resolve()),
                    "events": str(events_path().resolve()),
                    "npc_pilot_count": len(load_pilot_registry().get("pilots", [])),
                    "queue": str(queue_path().resolve()),
                    "snapshot": str(snapshot_path().resolve()),
                    "llm_routing": dialogue_target(),
                    "llm_routes": [
                        {
                            "target": r.get("target"),
                            "base_url": r.get("base_url"),
                            "model": r.get("model"),
                        }
                        for r in resolve_llm_routes()
                    ],
                    "llm_timeout_s": llm_timeout_s(),
                    "zone": ia_zone(),
                    "instance": "core3-clean",
                    "bot_account": os.environ.get("CORE3_IA_BOT_NAME", "Bot_IA"),
                    "bot_character": bot_player_name(),
                },
            )
            return

        if path == "/v1/player-snapshot":
            qs = urllib.parse.parse_qs(parsed.query)
            player = (qs.get("player") or [bot_player_name()])[0]
            snap = load_snapshot(player)
            code = 200 if snap.get("online") else 409
            self._json(code, {"ok": snap.get("online", False), "snapshot": snap})
            return

        if path == "/v1/events":
            qs = urllib.parse.parse_qs(parsed.query)
            player = (qs.get("player") or [""])[0]
            after = (qs.get("after") or [""])[0] or None
            include_actor_raw = (qs.get("include_actor") or ["0"])[0]
            try:
                limit = int((qs.get("limit") or ["50"])[0])
            except ValueError:
                limit = 50
            events = load_social_events(
                player=player,
                after=after,
                limit=limit,
                include_actor=str(include_actor_raw).strip().lower() in ("1", "true", "yes", "on"),
            )
            self._json(
                200,
                {
                    "ok": True,
                    "events": events,
                    "count": len(events),
                    "last_event_id": str(events[-1].get("event_id")) if events else after,
                    "path": str(events_path().resolve()),
                },
            )
            return

        if path == "/v1/npc-pilots":
            reg = load_pilot_registry()
            snaps = load_npc_snapshots()
            pilots_out = []
            for row in reg.get("pilots", []):
                if not isinstance(row, dict):
                    continue
                pid = pilot_id_from_row(row)
                merged = pilot_row_public(row)
                live = load_npc_snapshot(pid)
                merged["snapshot"] = live
                merged["online"] = bool(live.get("online"))
                pilots_out.append(merged)
            self._json(200, {"ok": True, "zone": reg.get("zone", ia_zone()), "pilots": pilots_out})
            return

        if path == "/v1/npc-snapshot":
            qs = urllib.parse.parse_qs(parsed.query)
            npc_ref = (qs.get("npc_id") or qs.get("pilot_id") or [""])[0]
            snap = load_npc_snapshot(npc_ref)
            code = 200 if snap.get("online") else 409
            self._json(code, {"ok": snap.get("online", False), "snapshot": snap})
            return

        if path == "/v1/quest-state":
            states = load_quest_state()
            self._json(
                200,
                {
                    "ok": True,
                    "quest_states": states,
                    "count": len(states),
                    "path": str(quest_state_path().resolve()),
                },
            )
            return

        self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        try:
            if self.path.rstrip("/") == "/v1/enqueue":
                data = self._read_json()
                line = str(data.get("line", "")).strip()
                if not line:
                    action = str(data.get("action", "say"))
                    if action not in ALLOWED_ACTIONS:
                        raise ValueError(f"action non autorisée : {action}")
                    player = str(data.get("player", bot_player_name()))
                    line = format_command(
                        action,
                        player,
                        str(data.get("zone", "") or ia_zone()),
                        float(data.get("x", 0)),
                        float(data.get("y", 0)),
                        float(data.get("z", 0)),
                        str(data.get("message", "")),
                    )
                enqueue_line(line)
                self._json(200, {"ok": True, "line": line})
                return

            if self.path.rstrip("/") == "/v1/npc-think":
                data = self._read_json()
                npc_ref = str(
                    data.get("npc_id")
                    or data.get("pilot_id")
                    or data.get("world_npc_id")
                    or ""
                ).strip()
                row = resolve_pilot_row(npc_ref)
                if row is None:
                    self._json(400, {"ok": False, "error": "unknown_pilot", "npc_id": npc_ref})
                    return
                pilot_id = pilot_id_from_row(row)
                snap = load_npc_snapshot(pilot_id)
                if not snap.get("online"):
                    self._json(
                        409,
                        {
                            "ok": False,
                            "reason": "npc_offline",
                            "snapshot": snap,
                            "observation": format_npc_observation(snap),
                        },
                    )
                    return
                if npc_think_on_cooldown(pilot_id):
                    self._json(
                        429,
                        {
                            "ok": False,
                            "reason": "npc_think_cooldown",
                            "pilot_id": pilot_id,
                            "cooldown_sec": _NPC_THINK_COOLDOWN_SEC,
                        },
                    )
                    return
                mark_npc_think(pilot_id)
                prompt = str(
                    data.get("prompt")
                    or data.get("text")
                    or "Une courte réplique d'accueil aux voyageurs proches."
                )
                observation = format_npc_observation(snap)
                profile = resolve_profile_for_row(row)
                raw = llm_npc_chat(prompt, snap, pilot_row=row)
                parsed = parse_action_json(raw)
                act, line = normalize_npc_action(parsed, pilot_id, pilot_row=row)
                enqueued = False
                if data.get("enqueue", True) and act != "noop":
                    enqueue_line(line)
                    enqueued = True
                self._json(
                    200,
                    {
                        "ok": True,
                        "line": line,
                        "action": act,
                        "pilot_id": pilot_id,
                        "profile_id": row.get("profile_id"),
                        "lbg_npc_id": row.get("lbg_npc_id"),
                        "enqueued": enqueued,
                        "observation": observation,
                        "snapshot": snap,
                        "llm_raw": raw,
                        "parsed": parsed,
                        "profile_role": profile.get("role"),
                    },
                )
                return

            if self.path.rstrip("/") == "/v1/think":
                data = self._read_json()
                player = str(data.get("player", bot_player_name()))
                snap = load_snapshot(player)
                if not snap.get("online"):
                    self._json(
                        409,
                        {
                            "ok": False,
                            "reason": "player_offline",
                            "snapshot": snap,
                            "observation": format_observation(snap),
                        },
                    )
                    return

                prompt = str(
                    data.get("prompt")
                    or data.get("observation")
                    or "Réagis brièvement à la situation (une phrase en jeu)."
                )
                observation = format_observation(snap)
                incarnation = bool(data.get("incarnation"))
                brain = data.get("orchestrator_brain")
                if not isinstance(brain, dict):
                    brain = None
                raw = llm_chat(
                    prompt,
                    snap,
                    incarnation=incarnation,
                    orchestrator_brain=brain,
                )
                parsed = parse_action_json(raw)
                act, line = normalize_action(parsed, player)
                retried = False
                if incarnation and act == "noop":
                    retry_prompt = (
                        f"{prompt}\n\n[Rappel] noop interdit sur ce tour. "
                        "Choisis obligatoirement say, interact, perform (dance/greet), approach_player, "
                        "animate ou move_to."
                    )
                    raw = llm_chat(
                        retry_prompt,
                        snap,
                        incarnation=True,
                        orchestrator_brain=brain,
                    )
                    parsed = parse_action_json(raw)
                    act, line = normalize_action(parsed, player)
                    retried = True
                enqueued = False
                if data.get("enqueue", True) and act != "noop":
                    enqueue_line(line)
                    enqueued = True
                self._json(
                    200,
                    {
                        "ok": True,
                        "line": line,
                        "action": act,
                        "enqueued": enqueued,
                        "observation": observation,
                        "snapshot": snap,
                        "llm_raw": raw,
                        "parsed": parsed,
                        "incarnation": incarnation,
                        "noop_retried": retried,
                    },
                )
                return

            if self.path.rstrip("/") in ("/v1/lia/connect", "/v1/player/connect"):
                data = self._read_json()
                wait = data.get("wait", True)
                if wait is False or str(wait).lower() in ("0", "false", "no"):
                    wait_b = False
                else:
                    wait_b = True
                raw_wait = data.get("wait_s", 120)
                try:
                    wait_s = int(raw_wait)
                except (TypeError, ValueError):
                    wait_s = 120
                force_restart = bool(data.get("force_restart"))
                player_id = str(data.get("player_id") or "lia").strip().lower() or "lia"
                out = connect_ai_player(
                    player_id,
                    wait=wait_b,
                    wait_s=wait_s,
                    force_restart=force_restart,
                )
                code = 200 if out.get("ok") else 504 if out.get("outcome") == "connect_timeout" else 502
                self._json(code, out)
                return

            if self.path.rstrip("/") == "/v1/lia/hear":
                data = self._read_json()
                from_player = str(data.get("from") or data.get("player") or "Gally").strip()
                text = str(data.get("text") or data.get("message") or "").strip()
                if not text:
                    self._json(400, {"ok": False, "error": "text_required"})
                    return
                direct = direct_lia_hear_command(from_player, text)
                if direct is not None:
                    enqueue_line(str(direct["line"]))
                    self._json(
                        200,
                        {
                            "ok": True,
                            "incarnation": True,
                            "mode": "deterministic_hear",
                            "from_player": from_player,
                            "heard": text,
                            **direct,
                        },
                    )
                    return
                try:
                    from lbg_agents.lia_orchestrator import build_hear_prompt, incarnate_player_think

                    prompt = build_hear_prompt(from_player=from_player, text=text)
                    out = incarnate_player_think(prompt=prompt)
                    self._json(200, {"ok": bool(out.get("ok")), "incarnation": True, **out})
                except ImportError as exc:
                    self._json(500, {"ok": False, "error": "lia_orchestrator_unavailable", "detail": str(exc)})
                return

            self._json(404, {"error": "not_found"})
        except urllib.error.URLError as exc:
            self._json(502, {"ok": False, "error": "llm_unreachable", "detail": str(exc)})
        except Exception as exc:
            self._json(400, {"ok": False, "error": str(exc)})


def main() -> None:
    load_env_files()
    host = os.environ.get("CORE3_IA_SIDECAR_HOST", DEFAULT_BIND[0])
    port = int(os.environ.get("CORE3_IA_SIDECAR_PORT", str(DEFAULT_BIND[1])))
    os.chdir(os.environ.get("CORE3_IA_BRIDGE_CWD", os.getcwd()))
    server = ThreadingHTTPServer((host, port), Handler)
    reg = load_pilot_registry()
    print(
        f"core3_ia_sidecar phase=C2 source={reg.get('registry_source')} "
        f"listening on http://{host}:{port} cwd={os.getcwd()}",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
