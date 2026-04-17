"""
API HTTP minimale sur l’état du monde : jauges Lyra des PNJ mises à jour par le tick.

Le thread de simulation tourne en arrière-plan ; les endpoints ne font que lire `WorldState`.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel

from entities.npc import Npc
from simulation.loop import SimulationLoop
from world.persistence import load_world_state, save_world_state
from world.state import WorldState

logger = logging.getLogger(__name__)


def _lyra_context_for_npc(npc: Npc, world_now_s: float) -> dict[str, Any]:
    g = npc.gauges
    return {
        "version": "lyra-context-1",
        "dt_s": 0.0,
        "gauges": {
            "hunger": g.hunger,
            "thirst": g.thirst,
            "fatigue": g.fatigue,
        },
        "meta": {
            "source": "mmo_world",
            "world_now_s": world_now_s,
            "npc_id": npc.id,
            "npc_name": npc.name,
            "reputation": {"value": int(getattr(npc, "reputation_value", 0))},
        },
    }


def _persist_disabled() -> bool:
    return os.environ.get("LBG_MMO_DISABLE_PERSIST", "").strip() in ("1", "true", "yes")


def _state_path() -> Path:
    raw = os.environ.get("LBG_MMO_STATE_PATH", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path(__file__).resolve().parent / "data" / "world_state.json"


def _save_interval_s() -> float:
    try:
        return max(5.0, float(os.environ.get("LBG_MMO_SAVE_INTERVAL_S", "30")))
    except (TypeError, ValueError):
        return 30.0


@asynccontextmanager
async def _lifespan(app: FastAPI):
    stop = threading.Event()
    world_lock = threading.Lock()
    state_path = _state_path()
    persist = not _persist_disabled()

    if persist:
        loaded = load_world_state(state_path)
        world = loaded if loaded is not None else WorldState.bootstrap_default()
        if loaded is not None:
            logger.info("état monde chargé depuis %s", state_path)
    else:
        world = WorldState.bootstrap_default()

    loop = SimulationLoop(world=world, tick_hz=5.0)
    save_every = _save_interval_s()
    last_save = time.monotonic()

    def _run_sim() -> None:
        nonlocal last_save
        last = time.time()
        while not stop.is_set():
            now = time.time()
            dt = now - last
            last = now
            with world_lock:
                loop.tick(dt)
            time.sleep(loop.tick_interval_s)
            if persist and (time.monotonic() - last_save) >= save_every:
                with world_lock:
                    try:
                        save_world_state(state_path, world)
                    except OSError as e:
                        logger.warning("sauvegarde état monde échouée : %s", e)
                last_save = time.monotonic()

    thread = threading.Thread(target=_run_sim, name="mmo-sim", daemon=True)
    thread.start()
    app.state.world = world
    app.state.world_lock = world_lock
    app.state._stop_sim = stop
    app.state._persist = persist
    app.state._state_path = state_path
    yield
    stop.set()
    if persist:
        with world_lock:
            try:
                save_world_state(state_path, world)
                logger.info("état monde sauvegardé vers %s (arrêt)", state_path)
            except OSError as e:
                logger.warning("sauvegarde finale état monde échouée : %s", e)


app = FastAPI(title="LBG MMO Server", lifespan=_lifespan)


class HealthResponse(BaseModel):
    ok: bool = True
    service: str = "mmo_server"


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse()


@app.get("/v1/world/lyra")
def get_world_lyra(
    npc_id: str = Query(..., description="Identifiant monde du PNJ (ex. npc:smith)"),
) -> dict[str, Any]:
    """
    Retourne un objet `lyra` utilisable tel quel dans `context.lyra` (source monde, pas de double pas côté agents).
    """
    lock: threading.Lock = app.state.world_lock
    with lock:
        world: WorldState = app.state.world
        npc = world.npcs.get(npc_id)
        if npc is None:
            raise HTTPException(status_code=404, detail=f"npc not found: {npc_id!r}")
        lyra = _lyra_context_for_npc(npc, world.now_s)
    return {"npc_id": npc_id, "lyra": lyra}


def _require_mmo_internal_token(got: str | None) -> None:
    """
    Gate optionnel pour endpoints internes d'écriture du mmo_server.
    Variable : LBG_MMO_INTERNAL_TOKEN.
    """
    expected = os.environ.get("LBG_MMO_INTERNAL_TOKEN", "").strip()
    if not expected:
        return
    if not (isinstance(got, str) and got == expected):
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "hint": "missing/invalid X-LBG-Service-Token"},
        )


@app.post("/internal/v1/npc/{npc_id}/reputation")
def post_internal_reputation(
    npc_id: str,
    payload: dict[str, object],
    x_lbg_service_token: str | None = Header(default=None, alias="X-LBG-Service-Token"),
) -> dict[str, object]:
    """
    Mise à jour interne (LAN) : applique un delta de réputation au PNJ.

    Body JSON:
      - delta: int (borné [-100,100])
    Header (si token configuré) : X-LBG-Service-Token
    """
    _require_mmo_internal_token(x_lbg_service_token)
    try:
        d = int(payload.get("delta"))  # type: ignore[arg-type]
    except Exception:
        raise HTTPException(status_code=400, detail={"error": "bad_request", "hint": "delta int requis"})
    if d < -100 or d > 100:
        raise HTTPException(status_code=400, detail={"error": "bad_request", "hint": "delta hors bornes [-100,100]"})

    lock: threading.Lock = app.state.world_lock
    with lock:
        world: WorldState = app.state.world
        npc = world.npcs.get(npc_id)
        if npc is None:
            raise HTTPException(status_code=404, detail=f"npc not found: {npc_id!r}")
        cur = int(getattr(npc, "reputation_value", 0))
        nxt = cur + d
        if nxt < -100:
            nxt = -100
        if nxt > 100:
            nxt = 100
        npc.reputation_value = int(nxt)
        lyra = _lyra_context_for_npc(npc, world.now_s)
    return {"ok": True, "npc_id": npc_id, "reputation_value": int(nxt), "lyra": lyra}
