import asyncio
import logging
import os
import time
import uuid

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from models.intents import IntentRequest, IntentResponse
from services.brain_lyra_sync import merge_brain_lyra_if_configured
from services.lyra_regulator import regulate_lyra_if_configured
from services import metrics as svc_metrics
from services.mmo_lyra_sync import merge_mmo_lyra_if_configured
from services.mmmorpg_commit import try_commit_dialogue
from services.orchestrator_client import OrchestratorClient, OrchestratorError

router = APIRouter()
LOG = logging.getLogger("pilot")


class _TokenBucket:
    __slots__ = ("rps", "burst", "tokens", "last_s")

    def __init__(self, *, rps: float, burst: int) -> None:
        self.rps = float(rps)
        self.burst = int(burst)
        self.tokens = float(burst)
        self.last_s = time.monotonic()


_internal_rl_buckets: dict[str, _TokenBucket] = {}


def _mmmorpg_player_id_from_pilot(payload: IntentRequest) -> str | None:
    """Identifiant joueur sur le serveur WS (UUID session), pour commits inventaire / quête côté joueur."""
    ctx = payload.context if isinstance(payload.context, dict) else {}
    for key in ("mmmorpg_player_id", "player_id"):
        v = ctx.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    aid = (payload.actor_id or "").strip()
    if aid.lower().startswith("player:"):
        rest = aid.split(":", 1)[-1].strip()
        if rest:
            return rest
    return None


def _internal_rate_limit_allow(*, key: str) -> bool:
    """
    Rate-limit best-effort pour l’endpoint interne (service→service).
    Activé si `LBG_PILOT_INTERNAL_RL_RPS` et `LBG_PILOT_INTERNAL_RL_BURST` > 0.
    """
    try:
        rps = float(os.environ.get("LBG_PILOT_INTERNAL_RL_RPS", "0") or "0")
        burst = int(os.environ.get("LBG_PILOT_INTERNAL_RL_BURST", "0") or "0")
    except Exception:
        rps, burst = 0.0, 0
    if rps <= 0.0 or burst <= 0:
        return True

    now = time.monotonic()
    b = _internal_rl_buckets.get(key)
    if b is None or b.rps != rps or b.burst != burst:
        b = _TokenBucket(rps=rps, burst=burst)
        _internal_rl_buckets[key] = b

    dt = max(0.0, now - b.last_s)
    b.tokens = min(float(b.burst), b.tokens + dt * b.rps)
    b.last_s = now
    if b.tokens >= 1.0:
        b.tokens -= 1.0
        return True
    return False


def _require_internal_token(got: str | None) -> None:
    expected = os.environ.get("LBG_PILOT_INTERNAL_TOKEN", "").strip()
    if not expected:
        return
    if not (isinstance(got, str) and got == expected):
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "hint": "missing/invalid X-LBG-Service-Token"},
        )


def _pilot_agent_dialogue_invoke_timeout_s() -> float:
    """HTTP backend → agent dialogue pour POST /invoke (LLM + marge ; doit dépasser le timeout côté agent)."""
    raw = os.environ.get("LBG_PILOT_AGENT_DIALOGUE_INVOKE_TIMEOUT", "300").strip()
    try:
        return max(45.0, float(raw))
    except ValueError:
        return 300.0


def _lbg_ia_backend_base_url() -> str | None:
    """URL racine du FastAPI orchestrateur projet LBG_IA (voir `GET /metrics`, `/monitor/agents`)."""
    raw = (os.environ.get("LBG_PILOT_LBGIA_BACKEND_URL", "").strip() or os.environ.get("LBG_IA_BACKEND_URL", "").strip()).rstrip(
        "/"
    )
    return raw or None


def _pilot_lbg_ia_http_timeout_s() -> float:
    raw = os.environ.get("LBG_PILOT_LBGIA_HTTP_TIMEOUT", "3").strip()
    try:
        return max(0.8, min(15.0, float(raw)))
    except ValueError:
        return 3.0


async def _pilot_route_impl(*, payload: IntentRequest, trace_id: str) -> dict[str, object]:
    t0 = time.perf_counter()
    svc_metrics.inc("pilot_route_requests_total")
    payload.context.setdefault("_trace_id", trace_id)
    await merge_mmo_lyra_if_configured(payload.context)
    await merge_brain_lyra_if_configured(payload.context)
    await regulate_lyra_if_configured(payload.context)
    lyra_after_merge = payload.context.get("lyra") if isinstance(payload.context, dict) else None
    try:
        client = OrchestratorClient.from_env()
        result: IntentResponse = await client.route_intent(payload)
    except OrchestratorError as e:
        svc_metrics.inc("pilot_route_orchestrator_errors_total")
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return {"ok": False, "trace_id": trace_id, "elapsed_ms": elapsed_ms, "error": str(e)}

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    svc_metrics.inc("pilot_route_success_total")
    out = {"ok": True, "trace_id": trace_id, "elapsed_ms": elapsed_ms, "result": result.model_dump()}
    if isinstance(lyra_after_merge, dict):
        meta = lyra_after_merge.get("meta")
        if isinstance(meta, dict) and meta:
            out["lyra_meta"] = meta

    # Phase 2 (réconciliation) : commit optionnel vers le serveur WS via HTTP interne.
    # Si l'agent propose un commit (`output.commit`), on tente de l'appliquer et on expose `commit_result`.
    try:
        commit = result.output.get("commit") if isinstance(result.output, dict) else None
        if isinstance(commit, dict):
            npc_id = commit.get("npc_id") or payload.context.get("world_npc_id")
            flags = commit.get("flags") if isinstance(commit.get("flags"), dict) else None
            if isinstance(npc_id, str) and npc_id.strip():
                commit_result = await try_commit_dialogue(
                    trace_id=trace_id,
                    npc_id=npc_id,
                    flags=flags,
                    player_id=_mmmorpg_player_id_from_pilot(payload),
                )
                if commit_result is not None:
                    out["commit_result"] = commit_result
    except Exception:
        # Best-effort : ne jamais casser /pilot/route
        pass

    return out


@router.get("/status", tags=["pilot"])
async def pilot_aggregate_status() -> dict[str, object]:
    """
    Santé agrégée pour l’UI de pilotage : évite au navigateur d’appeler
    l’orchestrator en cross-origin (CORS).
    """
    orch_url = os.environ.get("LBG_ORCHESTRATOR_URL", "http://127.0.0.1:8010").rstrip("/")
    orch_state: str = "unknown"
    orch_detail: str | None = None
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{orch_url}/healthz")
        if r.status_code == 200:
            orch_state = "ok"
        else:
            orch_state = "error"
            orch_detail = f"HTTP {r.status_code}"
    except Exception as e:
        orch_state = "error"
        orch_detail = str(e)

    dialogue_url_raw = os.environ.get("LBG_AGENT_DIALOGUE_URL", "").strip()
    dialogue_state: str
    dialogue_detail: str | None = None
    dialogue_probe_url: str | None = None
    dialogue_info: dict[str, object] | None = None

    if not dialogue_url_raw:
        dialogue_state = "skipped"
        dialogue_detail = "LBG_AGENT_DIALOGUE_URL non défini (stub dialogue côté orchestrator)"
    else:
        dialogue_probe_url = dialogue_url_raw.rstrip("/") + "/healthz"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(dialogue_probe_url)
            if r.status_code == 200:
                dialogue_state = "ok"
                try:
                    raw = r.json()
                    if isinstance(raw, dict):
                        dialogue_info = raw
                    else:
                        dialogue_detail = "healthz: JSON attendu (objet), reçu autre type"
                except Exception:
                    dialogue_detail = "healthz: corps non JSON"
            else:
                dialogue_state = "error"
                dialogue_detail = f"HTTP {r.status_code}"
        except Exception as e:
            dialogue_state = "error"
            dialogue_detail = str(e)

    quests_url_raw = os.environ.get("LBG_AGENT_QUESTS_URL", "").strip()
    quests_state: str
    quests_detail: str | None = None
    quests_probe_url: str | None = None
    quests_info: dict[str, object] | None = None

    if not quests_url_raw:
        quests_state = "skipped"
        quests_detail = "LBG_AGENT_QUESTS_URL non défini (stub quests côté orchestrator)"
    else:
        quests_probe_url = quests_url_raw.rstrip("/") + "/healthz"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(quests_probe_url)
            if r.status_code == 200:
                quests_state = "ok"
                try:
                    raw = r.json()
                    if isinstance(raw, dict):
                        quests_info = raw
                    else:
                        quests_detail = "healthz: JSON attendu (objet), reçu autre type"
                except Exception:
                    quests_detail = "healthz: corps non JSON"
            else:
                quests_state = "error"
                quests_detail = f"HTTP {r.status_code}"
        except Exception as e:
            quests_state = "error"
            quests_detail = str(e)

    combat_url_raw = os.environ.get("LBG_AGENT_COMBAT_URL", "").strip()
    combat_state: str
    combat_detail: str | None = None
    combat_probe_url: str | None = None
    combat_info: dict[str, object] | None = None

    if not combat_url_raw:
        combat_state = "skipped"
        combat_detail = "LBG_AGENT_COMBAT_URL non défini (stub combat côté orchestrator)"
    else:
        combat_probe_url = combat_url_raw.rstrip("/") + "/healthz"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(combat_probe_url)
            if r.status_code == 200:
                combat_state = "ok"
                try:
                    raw = r.json()
                    if isinstance(raw, dict):
                        combat_info = raw
                    else:
                        combat_detail = "healthz: JSON attendu (objet), reçu autre type"
                except Exception:
                    combat_detail = "healthz: corps non JSON"
            else:
                combat_state = "error"
                combat_detail = f"HTTP {r.status_code}"
        except Exception as e:
            combat_state = "error"
            combat_detail = str(e)

    pm_url_raw = os.environ.get("LBG_AGENT_PM_URL", "").strip()
    pm_state: str
    pm_detail: str | None = None
    pm_probe_url: str | None = None
    pm_info: dict[str, object] | None = None

    if not pm_url_raw:
        pm_state = "skipped"
        pm_detail = "LBG_AGENT_PM_URL non défini (stub PM côté orchestrator)"
    else:
        pm_probe_url = pm_url_raw.rstrip("/") + "/healthz"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(pm_probe_url)
            if r.status_code == 200:
                pm_state = "ok"
                try:
                    raw = r.json()
                    if isinstance(raw, dict):
                        pm_info = raw
                    else:
                        pm_detail = "healthz: JSON attendu (objet), reçu autre type"
                except Exception:
                    pm_detail = "healthz: corps non JSON"
            else:
                pm_state = "error"
                pm_detail = f"HTTP {r.status_code}"
        except Exception as e:
            pm_state = "error"
            pm_detail = str(e)

    desktop_url_raw = os.environ.get("LBG_AGENT_DESKTOP_URL", "").strip()
    desktop_state: str
    desktop_detail: str | None = None
    desktop_probe_url: str | None = None
    desktop_info: dict[str, object] | None = None

    if not desktop_url_raw:
        desktop_state = "skipped"
        desktop_detail = "LBG_AGENT_DESKTOP_URL non défini (desktop_control indisponible)"
    else:
        desktop_probe_url = desktop_url_raw.rstrip("/") + "/healthz"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(desktop_probe_url)
            if r.status_code == 200:
                desktop_state = "ok"
                try:
                    raw = r.json()
                    if isinstance(raw, dict):
                        desktop_info = raw
                    else:
                        desktop_detail = "healthz: JSON attendu (objet), reçu autre type"
                except Exception:
                    desktop_detail = "healthz: corps non JSON"
            else:
                desktop_state = "error"
                desktop_detail = f"HTTP {r.status_code}"
        except Exception as e:
            desktop_state = "error"
            desktop_detail = str(e)

    mmo_url_raw = os.environ.get("LBG_MMO_SERVER_URL", "").strip()
    mmo_state: str
    mmo_detail: str | None = None
    mmo_probe_url: str | None = None

    if not mmo_url_raw:
        mmo_state = "skipped"
        mmo_detail = "LBG_MMO_SERVER_URL non défini (pas de sync Lyra monde)"
    else:
        mmo_probe_url = mmo_url_raw.rstrip("/") + "/healthz"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(mmo_probe_url)
            if r.status_code == 200:
                mmo_state = "ok"
            else:
                mmo_state = "error"
                mmo_detail = f"HTTP {r.status_code}"
        except Exception as e:
            mmo_state = "error"
            mmo_detail = str(e)

    return {
        "backend": "ok",
        "orchestrator": orch_state,
        "orchestrator_url": orch_url,
        "orchestrator_detail": orch_detail,
        "agent_dialogue": dialogue_state,
        "agent_dialogue_url": dialogue_url_raw or None,
        "agent_dialogue_health_url": dialogue_probe_url,
        "agent_dialogue_detail": dialogue_detail,
        "agent_dialogue_info": dialogue_info,
        "agent_quests": quests_state,
        "agent_quests_url": quests_url_raw or None,
        "agent_quests_health_url": quests_probe_url,
        "agent_quests_detail": quests_detail,
        "agent_quests_info": quests_info,
        "agent_combat": combat_state,
        "agent_combat_url": combat_url_raw or None,
        "agent_combat_health_url": combat_probe_url,
        "agent_combat_detail": combat_detail,
        "agent_combat_info": combat_info,
        "agent_pm": pm_state,
        "agent_pm_url": pm_url_raw or None,
        "agent_pm_health_url": pm_probe_url,
        "agent_pm_detail": pm_detail,
        "agent_pm_info": pm_info,
        "agent_desktop": desktop_state,
        "agent_desktop_url": desktop_url_raw or None,
        "agent_desktop_health_url": desktop_probe_url,
        "agent_desktop_detail": desktop_detail,
        "agent_desktop_info": desktop_info,
        "mmo_server": mmo_state,
        "mmo_server_url": mmo_url_raw or None,
        "mmo_server_health_url": mmo_probe_url,
        "mmo_server_detail": mmo_detail,
    }


@router.get("/lbg-ia/status", tags=["pilot"])
async def pilot_lbg_ia_orchestrator_status() -> dict[str, object]:
    """
    Agrège `GET /metrics` + `GET /monitor/agents` du backend FastAPI **projet LBG_IA** (même réseau/VM).

    Définir `LBG_PILOT_LBGIA_BACKEND_URL` (ou `LBG_IA_BACKEND_URL`) sur ce backend ; le pilot web pilote alors
    le monitoring sans CORS depuis le navigateur.
    """
    base = _lbg_ia_backend_base_url()
    if not base:
        return {
            "ok": False,
            "disabled": True,
            "detail": "LBG_PILOT_LBGIA_BACKEND_URL / LBG_IA_BACKEND_URL non défini.",
        }

    timeout = _pilot_lbg_ia_http_timeout_s()
    metrics_error = ""
    agents_error = ""

    metrics_data: dict[str, object] | None = None
    agents_data: dict[str, object] | None = None
    metrics_status = 0
    agents_status = 0

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            m_resp, a_resp = await asyncio.gather(
                client.get(f"{base}/metrics"),
                client.get(f"{base}/monitor/agents"),
            )

        metrics_status = int(getattr(m_resp, "status_code", 0))
        agents_status = int(getattr(a_resp, "status_code", 0))

        if metrics_status != 200:
            metrics_error = (getattr(m_resp, "text", "") or "")[:500]

        try:
            if metrics_status == 200:
                raw_m = m_resp.json()
                metrics_data = raw_m if isinstance(raw_m, dict) else {"payload": raw_m}
        except Exception as e:
            metrics_error = str(e)

        if agents_status != 200:
            agents_error = (getattr(a_resp, "text", "") or "")[:500]

        try:
            if agents_status == 200:
                raw_a = a_resp.json()
                agents_data = raw_a if isinstance(raw_a, dict) else {"payload": raw_a}
        except Exception as e:
            agents_error = str(e)

    except Exception as e:
        LOG.warning("pilot.lbg_ia_orchestrator_status error base=%s err=%s", base, e)
        return {"ok": False, "upstream_base": base, "detail": str(e)}

    ok = metrics_status == 200 and agents_status == 200 and metrics_data is not None and agents_data is not None
    out: dict[str, object] = {
        "ok": ok,
        "upstream_base": base,
        "metrics": metrics_data,
        "agents_monitor": agents_data,
    }
    if not ok:
        out["upstream_errors"] = {
            "metrics_http": metrics_status,
            "metrics_detail": metrics_error or None,
            "agents_http": agents_status,
            "agents_detail": agents_error or None,
        }
    return out


@router.get("/agent-dialogue/healthz", tags=["pilot"])
async def pilot_proxy_agent_dialogue_healthz() -> dict[str, object]:
    """
    Proxy same-origin vers l’agent dialogue : évite d’exposer 8020 au navigateur (CORS / firewall).
    """
    base = os.environ.get("LBG_AGENT_DIALOGUE_URL", "").strip().rstrip("/")
    if not base:
        return {"ok": False, "skipped": True, "detail": "LBG_AGENT_DIALOGUE_URL non défini"}
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{base}/healthz")
        if r.status_code != 200:
            return {"ok": False, "error": f"HTTP {r.status_code}", "body": r.text[:500]}
        try:
            data = r.json()
        except ValueError:
            return {"ok": False, "error": "corps non JSON", "body": r.text[:500]}
        return {"ok": True, **data} if isinstance(data, dict) else {"ok": True, "payload": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/agent-dialogue/npc-registry", tags=["pilot"])
async def pilot_proxy_agent_dialogue_npc_registry(npc_id: str | None = None) -> dict[str, object]:
    """
    Proxy same-origin vers `GET agent-dialogue /npc-registry`.
    Option : `?npc_id=npc:...` pour filtrer une entrée.
    """
    base = os.environ.get("LBG_AGENT_DIALOGUE_URL", "").strip().rstrip("/")
    if not base:
        return {"ok": False, "skipped": True, "detail": "LBG_AGENT_DIALOGUE_URL non défini"}
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{base}/npc-registry", params={"npc_id": npc_id} if npc_id else None)
        if r.status_code != 200:
            return {"ok": False, "error": f"HTTP {r.status_code}", "body": r.text[:800]}
        try:
            data = r.json()
        except ValueError:
            return {"ok": False, "error": "corps non JSON", "body": r.text[:800]}
        return {"ok": True, **data} if isinstance(data, dict) else {"ok": True, "payload": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/agent-dialogue/world-content", tags=["pilot"])
async def pilot_proxy_agent_dialogue_world_content() -> dict[str, object]:
    """
    Proxy same-origin vers `GET agent-dialogue /world-content` (inventaire races + bestiaire).
    """
    base = os.environ.get("LBG_AGENT_DIALOGUE_URL", "").strip().rstrip("/")
    if not base:
        return {"ok": False, "skipped": True, "detail": "LBG_AGENT_DIALOGUE_URL non défini"}
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{base}/world-content")
        if r.status_code != 200:
            return {"ok": False, "error": f"HTTP {r.status_code}", "body": r.text[:800]}
        try:
            data = r.json()
        except ValueError:
            return {"ok": False, "error": "corps non JSON", "body": r.text[:800]}
        return {"ok": True, **data} if isinstance(data, dict) else {"ok": True, "payload": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


class AgentDialogueInvokeBody(BaseModel):
    """Corps pour `POST agent-dialogue /invoke` (même forme que l’agent HTTP dialogue)."""

    actor_id: str
    text: str
    context: dict[str, object] = Field(default_factory=dict)


class ActionProposalBody(BaseModel):
    """Corps pour `POST orchestrator /v1/action-proposal`."""

    actor_id: str
    text: str = Field(..., min_length=1)
    context: dict[str, object] = Field(default_factory=dict)


@router.post("/agent-dialogue/invoke", tags=["pilot"])
async def pilot_proxy_agent_dialogue_invoke(body: AgentDialogueInvokeBody) -> dict[str, object]:
    """
    Proxy same-origin vers `POST {LBG_AGENT_DIALOGUE_URL}/invoke` (LLM dialogue + meta).

    Utile pour le Pilot (ex. proposition `DESKTOP_JSON` → édition humaine → `/v1/pilot/route`).
    """
    base = os.environ.get("LBG_AGENT_DIALOGUE_URL", "").strip().rstrip("/")
    if not base:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "hint": "LBG_AGENT_DIALOGUE_URL non défini"},
        )
    url = f"{base}/invoke"
    payload = {"actor_id": body.actor_id, "text": body.text, "context": body.context}
    try:
        async with httpx.AsyncClient(timeout=_pilot_agent_dialogue_invoke_timeout_s()) as client:
            r = await client.post(url, json=payload)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={"error": "upstream_unreachable", "detail": str(e)},
        ) from e
    try:
        data = r.json()
    except ValueError:
        raise HTTPException(
            status_code=502,
            detail={"error": "upstream_non_json", "body": r.text[:800]},
        )
    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=data if isinstance(data, dict) else {"body": r.text[:800]})
    return data if isinstance(data, dict) else {"payload": data}


@router.get("/agent-quests/healthz", tags=["pilot"])
async def pilot_proxy_agent_quests_healthz() -> dict[str, object]:
    """Proxy same-origin vers l’agent quests (port 8030 typiquement)."""
    base = os.environ.get("LBG_AGENT_QUESTS_URL", "").strip().rstrip("/")
    if not base:
        return {"ok": False, "skipped": True, "detail": "LBG_AGENT_QUESTS_URL non défini"}
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{base}/healthz")
        if r.status_code != 200:
            return {"ok": False, "error": f"HTTP {r.status_code}", "body": r.text[:500]}
        try:
            data = r.json()
        except ValueError:
            return {"ok": False, "error": "corps non JSON", "body": r.text[:500]}
        return {"ok": True, **data} if isinstance(data, dict) else {"ok": True, "payload": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/agent-pm/healthz", tags=["pilot"])
async def pilot_proxy_agent_pm_healthz() -> dict[str, object]:
    """Proxy same-origin vers l’agent chef de projet (port 8055 typiquement)."""
    base = os.environ.get("LBG_AGENT_PM_URL", "").strip().rstrip("/")
    if not base:
        return {"ok": False, "skipped": True, "detail": "LBG_AGENT_PM_URL non défini"}
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{base}/healthz")
        if r.status_code != 200:
            return {"ok": False, "error": f"HTTP {r.status_code}", "body": r.text[:500]}
        try:
            data = r.json()
        except ValueError:
            return {"ok": False, "error": "corps non JSON", "body": r.text[:500]}
        return {"ok": True, **data} if isinstance(data, dict) else {"ok": True, "payload": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/agent-desktop/healthz", tags=["pilot"])
async def pilot_proxy_agent_desktop_healthz() -> dict[str, object]:
    """Proxy same-origin vers l’agent desktop Windows (hybride)."""
    base = os.environ.get("LBG_AGENT_DESKTOP_URL", "").strip().rstrip("/")
    if not base:
        return {"ok": False, "skipped": True, "detail": "LBG_AGENT_DESKTOP_URL non défini"}
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{base}/healthz")
        if r.status_code != 200:
            return {"ok": False, "error": f"HTTP {r.status_code}", "body": r.text[:500]}
        try:
            data = r.json()
        except ValueError:
            return {"ok": False, "error": "corps non JSON", "body": r.text[:500]}
        return {"ok": True, **data} if isinstance(data, dict) else {"ok": True, "payload": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/mmo-server/healthz", tags=["pilot"])
async def pilot_proxy_mmo_server_healthz() -> dict[str, object]:
    """Proxy same-origin vers le serveur MMO HTTP (tick monde + /v1/world/lyra)."""
    base = os.environ.get("LBG_MMO_SERVER_URL", "").strip().rstrip("/")
    if not base:
        return {"ok": False, "skipped": True, "detail": "LBG_MMO_SERVER_URL non défini"}
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{base}/healthz")
        if r.status_code != 200:
            return {"ok": False, "error": f"HTTP {r.status_code}", "body": r.text[:500]}
        try:
            data = r.json()
        except ValueError:
            return {"ok": False, "error": "corps non JSON", "body": r.text[:500]}
        return {"ok": True, **data} if isinstance(data, dict) else {"ok": True, "payload": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/mmo-server/world-lyra", tags=["pilot"])
async def pilot_proxy_mmo_server_world_lyra(npc_id: str) -> dict[str, object]:
    """Proxy same-origin vers `GET /v1/world/lyra` sur `mmo_server`."""
    base = os.environ.get("LBG_MMO_SERVER_URL", "").strip().rstrip("/")
    if not base:
        raise HTTPException(status_code=400, detail={"error": "bad_request", "hint": "LBG_MMO_SERVER_URL non défini"})
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{base}/v1/world/lyra", params={"npc_id": npc_id})
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail={"error": "upstream_error", "body": r.text[:500]})
        try:
            data = r.json()
        except ValueError:
            raise HTTPException(status_code=502, detail={"error": "upstream_non_json", "body": r.text[:500]})
        return data if isinstance(data, dict) else {"payload": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail={"error": "upstream_unreachable", "detail": str(e)})


class AidRequest(BaseModel):
    npc_id: str
    hunger_delta: float = 0.0
    thirst_delta: float = 0.0
    fatigue_delta: float = 0.0
    reputation_delta: int = 0


@router.get("/agent-combat/healthz", tags=["pilot"])
async def pilot_proxy_agent_combat_healthz() -> dict[str, object]:
    """Proxy same-origin vers l’agent combat (port 8040 typiquement)."""
    base = os.environ.get("LBG_AGENT_COMBAT_URL", "").strip().rstrip("/")
    if not base:
        return {"ok": False, "skipped": True, "detail": "LBG_AGENT_COMBAT_URL non défini"}
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{base}/healthz")
        if r.status_code != 200:
            return {"ok": False, "error": f"HTTP {r.status_code}", "body": r.text[:500]}
        try:
            data = r.json()
        except ValueError:
            return {"ok": False, "error": "corps non JSON", "body": r.text[:500]}
        return {"ok": True, **data} if isinstance(data, dict) else {"ok": True, "payload": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/capabilities", tags=["pilot"])
async def pilot_capabilities() -> dict[str, object]:
    """Proxy vers l’orchestrator : liste des capabilities (même origine que /pilot/)."""
    orch_url = os.environ.get("LBG_ORCHESTRATOR_URL", "http://127.0.0.1:8010").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{orch_url}/v1/capabilities")
        if r.status_code != 200:
            return {
                "ok": False,
                "error": f"orchestrator HTTP {r.status_code}",
                "body": r.text[:500],
            }
        return {"ok": True, **r.json()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/action-proposal", tags=["pilot"])
async def pilot_action_proposal(payload: ActionProposalBody) -> dict[str, object]:
    """Proxy same-origin vers l’orchestrator : proposition d'action sans exécution."""
    orch_url = os.environ.get("LBG_ORCHESTRATOR_URL", "http://127.0.0.1:8010").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(f"{orch_url}/v1/action-proposal", json=payload.model_dump())
        if r.status_code != 200:
            return {"ok": False, "error": f"orchestrator HTTP {r.status_code}", "body": r.text[:500]}
        data = r.json()
        return {"ok": True, **data} if isinstance(data, dict) else {"ok": True, "payload": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/orchestrator/brain/status", tags=["pilot"])
async def pilot_proxy_orchestrator_brain_status() -> dict[str, object]:
    """Proxy same-origin vers `GET orchestrator /v1/brain/status` (évite CORS)."""
    orch_url = os.environ.get("LBG_ORCHESTRATOR_URL", "http://127.0.0.1:8010").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{orch_url}/v1/brain/status")
        if r.status_code != 200:
            return {"ok": False, "error": f"orchestrator HTTP {r.status_code}", "body": r.text[:500]}
        data = r.json()
        return {"ok": True, **data} if isinstance(data, dict) else {"ok": True, "payload": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/orchestrator/brain/toggle", tags=["pilot"])
async def pilot_proxy_orchestrator_brain_toggle(payload: dict[str, object]) -> dict[str, object]:
    """Proxy same-origin vers `POST orchestrator /v1/brain/toggle`."""
    orch_url = os.environ.get("LBG_ORCHESTRATOR_URL", "http://127.0.0.1:8010").rstrip("/")
    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        raise HTTPException(status_code=400, detail={"error": "bad_request", "hint": "body: {enabled: boolean}"})
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(f"{orch_url}/v1/brain/toggle", json={"enabled": enabled})
        if r.status_code != 200:
            return {"ok": False, "error": f"orchestrator HTTP {r.status_code}", "body": r.text[:500]}
        data = r.json()
        return {"ok": True, **data} if isinstance(data, dict) else {"ok": True, "payload": data}
    except HTTPException:
        raise
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/orchestrator/brain/approve", tags=["pilot"])
async def pilot_proxy_orchestrator_brain_approve(payload: dict[str, object]) -> dict[str, object]:
    """Proxy same-origin vers `POST orchestrator /v1/brain/approve`."""
    orch_url = os.environ.get("LBG_ORCHESTRATOR_URL", "http://127.0.0.1:8010").rstrip("/")
    rid = payload.get("request_id")
    if not isinstance(rid, str) or not rid.strip():
        raise HTTPException(status_code=400, detail={"error": "bad_request", "hint": "body: {request_id: string}"})
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(f"{orch_url}/v1/brain/approve", json={"request_id": rid.strip()})
        if r.status_code != 200:
            return {"ok": False, "error": f"orchestrator HTTP {r.status_code}", "body": r.text[:500]}
        data = r.json()
        return {"ok": True, **data} if isinstance(data, dict) else {"ok": True, "payload": data}
    except HTTPException:
        raise
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/route", tags=["pilot"])
async def pilot_route_intent_timed(payload: IntentRequest) -> dict[str, object]:
    """
    Route une intention via l’orchestrator et renvoie aussi une mesure simple de latence.

    But : instrumenter l’UI `/pilot/` sans changer le contrat public `/v1/intents/route`.
    """
    trace_id = uuid.uuid4().hex
    return await _pilot_route_impl(payload=payload, trace_id=trace_id)


@router.post("/internal/route", tags=["pilot"])
async def pilot_route_internal_service(
    request: Request,
    payload: IntentRequest,
    x_lbg_service_token: str | None = Header(default=None, alias="X-LBG-Service-Token"),
    x_lbg_trace_id: str | None = Header(default=None, alias="X-LBG-Trace-Id"),
) -> dict[str, object]:
    """
    Endpoint service→service pour le pont `mmmorpg_server` → backend.
    Protégé par token optionnel + rate-limit best-effort.
    """
    _require_internal_token(x_lbg_service_token)
    remote = (request.client.host if request.client else "unknown") or "unknown"
    if not _internal_rate_limit_allow(key=str(remote)):
        LOG.warning("pilot.internal_route rate_limited (remote=%s)", remote)
        raise HTTPException(status_code=429, detail={"error": "rate_limited", "hint": "slow down"})

    trace_id = (x_lbg_trace_id or "").strip() or uuid.uuid4().hex
    world_npc_id = payload.context.get("world_npc_id") if isinstance(payload.context, dict) else None
    actor_id = getattr(payload, "actor_id", None)
    LOG.info(
        "pilot.internal_route start (trace_id=%s remote=%s actor_id=%s world_npc_id=%s)",
        trace_id,
        remote,
        actor_id,
        world_npc_id,
    )
    out = await _pilot_route_impl(payload=payload, trace_id=trace_id)
    ok = bool(out.get("ok")) if isinstance(out, dict) else False
    elapsed_ms = out.get("elapsed_ms") if isinstance(out, dict) else None
    if ok:
        LOG.info("pilot.internal_route ok (trace_id=%s elapsed_ms=%s)", trace_id, elapsed_ms)
    else:
        LOG.warning("pilot.internal_route error (trace_id=%s elapsed_ms=%s)", trace_id, elapsed_ms)
    return out


@router.post("/reputation", tags=["pilot"])
async def pilot_commit_reputation(
    payload: dict[str, object],
    x_lbg_service_token: str | None = Header(default=None, alias="X-LBG-Service-Token"),
) -> dict[str, object]:
    """
    Applique un `reputation_delta` via le serveur WS (HTTP interne), sans passer par le LLM.

    Body (JSON) :
      - npc_id: str (ex. "npc:merchant")
      - delta: int (borné [-100, 100])
    """
    npc_id = (payload.get("npc_id") if isinstance(payload, dict) else None)  # type: ignore[truthy-bool]
    delta = (payload.get("delta") if isinstance(payload, dict) else None)  # type: ignore[truthy-bool]
    if not isinstance(npc_id, str) or not npc_id.strip():
        raise HTTPException(status_code=400, detail={"error": "bad_request", "hint": "npc_id requis"})
    try:
        d = int(delta)  # accepte "11"
    except Exception:
        raise HTTPException(status_code=400, detail={"error": "bad_request", "hint": "delta int requis"})
    if d < -100 or d > 100:
        raise HTTPException(status_code=400, detail={"error": "bad_request", "hint": "delta hors bornes [-100,100]"})

    # Même protection optionnelle que `/v1/pilot/internal/route` (utile si on expose `/pilot/` sur le LAN).
    # Important : après validation du body pour que les erreurs 400 restent observables même si un token est requis.
    _require_internal_token(x_lbg_service_token)

    trace_id = uuid.uuid4().hex
    # Réutiliser le canal commit existant (HTTP interne mmmorpg_server) + filtrage backend.
    commit_result = await try_commit_dialogue(trace_id=trace_id, npc_id=npc_id.strip(), flags={"reputation_delta": d})
    if commit_result is None:
        return {"ok": False, "trace_id": trace_id, "attempted": False, "error": "commit_disabled"}

    # Best-effort : garder le fallback `mmo_world` cohérent (si activé).
    mmo_base = os.environ.get("LBG_MMO_SERVER_URL", "").strip().rstrip("/")
    if mmo_base:
        mmo_token = os.environ.get("LBG_MMO_INTERNAL_TOKEN", "").strip()
        headers = {"X-LBG-Service-Token": mmo_token} if mmo_token else None
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                await client.post(
                    f"{mmo_base}/internal/v1/npc/{npc_id.strip()}/reputation",
                    json={"delta": d, "trace_id": trace_id},
                    headers=headers,
                )
        except Exception:
            # Ne jamais casser la route pilote si le monde HTTP est indispo.
            pass

    return {"ok": True, "trace_id": trace_id, "commit_result": commit_result}


@router.post("/player-inventory", tags=["pilot"])
async def pilot_commit_player_inventory(
    payload: dict[str, object],
    x_lbg_service_token: str | None = Header(default=None, alias="X-LBG-Service-Token"),
) -> dict[str, object]:
    """
    Applique ``player_item_id`` + ``player_item_qty_delta`` (+ ``player_item_label`` optionnel)
    via le HTTP interne du serveur WS, **sans** LLM.

    Body (JSON) :
      - ``npc_id`` : PNJ « contexte » du commit (même mécanisme que les autres commits dialogue).
      - ``player_id`` : UUID joueur session WS (``welcome.player_id``).
      - ``item_id`` : id d’objet (≤ 64 car. côté serveur jeu).
      - ``qty_delta`` : entier non nul, borné **[-50, 50]** (aligné ``mmmorpg_server``).
      - ``label`` : optionnel (≤ 80 car.), utile quand une nouvelle pile est créée.
    """
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail={"error": "bad_request", "hint": "JSON objet requis"})

    npc_id = payload.get("npc_id")
    player_id = payload.get("player_id")
    item_id = payload.get("item_id")
    qty_raw = payload.get("qty_delta")
    label_raw = payload.get("label")

    if not isinstance(npc_id, str) or not npc_id.strip():
        raise HTTPException(status_code=400, detail={"error": "bad_request", "hint": "npc_id requis"})
    if not isinstance(player_id, str) or not player_id.strip():
        raise HTTPException(status_code=400, detail={"error": "bad_request", "hint": "player_id requis (UUID WS)"})
    if not isinstance(item_id, str) or not item_id.strip():
        raise HTTPException(status_code=400, detail={"error": "bad_request", "hint": "item_id requis"})
    try:
        qd = int(qty_raw)  # type: ignore[arg-type]
    except Exception:
        raise HTTPException(status_code=400, detail={"error": "bad_request", "hint": "qty_delta entier requis"})
    if qd == 0:
        raise HTTPException(status_code=400, detail={"error": "bad_request", "hint": "qty_delta non nul"})
    if qd < -50 or qd > 50:
        raise HTTPException(status_code=400, detail={"error": "bad_request", "hint": "qty_delta hors [-50,50]"})

    iid = item_id.strip()
    if len(iid) > 64:
        raise HTTPException(status_code=400, detail={"error": "bad_request", "hint": "item_id trop long"})

    flags: dict[str, object] = {"player_item_id": iid, "player_item_qty_delta": qd}
    if label_raw is not None and isinstance(label_raw, str):
        lab = label_raw.strip()
        if lab:
            if len(lab) > 80:
                raise HTTPException(status_code=400, detail={"error": "bad_request", "hint": "label trop long"})
            flags["player_item_label"] = lab

    _require_internal_token(x_lbg_service_token)

    trace_id = uuid.uuid4().hex
    commit_result = await try_commit_dialogue(
        trace_id=trace_id,
        npc_id=npc_id.strip(),
        flags=flags,
        player_id=player_id.strip(),
    )
    if commit_result is None:
        return {"ok": False, "trace_id": trace_id, "attempted": False, "error": "commit_disabled"}

    return {"ok": True, "trace_id": trace_id, "commit_result": commit_result}


@router.post("/aid", tags=["pilot"])
async def pilot_apply_aid_to_world(
    payload: AidRequest,
    x_lbg_service_token: str | None = Header(default=None, alias="X-LBG-Service-Token"),
) -> dict[str, object]:
    """
    Gameplay v1 (monde) : applique des deltas sur un PNJ via `mmo_server` (LAN).
    Protégé par le même token optionnel que `/v1/pilot/internal/route` (LBG_PILOT_INTERNAL_TOKEN).
    """
    npc_id = (payload.npc_id or "").strip()
    if not npc_id:
        raise HTTPException(status_code=400, detail={"error": "bad_request", "hint": "npc_id requis"})

    # Validation d'inputs avant le gate token pour garder des 400 utiles.
    if payload.reputation_delta < -100 or payload.reputation_delta > 100:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "hint": "reputation_delta hors bornes [-100,100]"},
        )
    for name in ("hunger_delta", "thirst_delta", "fatigue_delta"):
        v = float(getattr(payload, name))
        if v < -1.0 or v > 1.0:
            raise HTTPException(status_code=400, detail={"error": "bad_request", "hint": f"{name} hors bornes [-1,1]"})

    _require_internal_token(x_lbg_service_token)

    base = os.environ.get("LBG_MMO_SERVER_URL", "").strip().rstrip("/")
    if not base:
        raise HTTPException(status_code=400, detail={"error": "bad_request", "hint": "LBG_MMO_SERVER_URL non défini"})

    trace_id = uuid.uuid4().hex
    mmo_token = os.environ.get("LBG_MMO_INTERNAL_TOKEN", "").strip()
    headers = {"X-LBG-Service-Token": mmo_token} if mmo_token else None
    body = {
        "hunger_delta": float(payload.hunger_delta),
        "thirst_delta": float(payload.thirst_delta),
        "fatigue_delta": float(payload.fatigue_delta),
        "reputation_delta": int(payload.reputation_delta),
        "trace_id": trace_id,
    }
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            r = await client.post(
                f"{base}/internal/v1/npc/{npc_id}/aid",
                json=body,
                headers=headers,
            )
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail={"error": "upstream_error", "body": r.text[:500]})
        try:
            data = r.json()
        except ValueError:
            raise HTTPException(status_code=502, detail={"error": "upstream_non_json", "body": r.text[:500]})
        return {"ok": True, "trace_id": trace_id, "world_result": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail={"error": "upstream_unreachable", "detail": str(e)})
