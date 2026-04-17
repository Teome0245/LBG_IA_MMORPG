"""Point d'entrée WebSocket — Phase 1."""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import time
from typing import Any

from websockets.asyncio.server import ServerConnection, serve

from mmmorpg_server import config
from mmmorpg_server.game_state import GameState
from mmmorpg_server.protocol import (
    msg_error,
    msg_welcome,
    msg_world_tick,
)

LOG = logging.getLogger("mmmorpg")


async def game_loop_broadcast(game: GameState, clients: set[ServerConnection]) -> None:
    dt = 1.0 / config.TICK_RATE_HZ
    try:
        while True:
            await asyncio.sleep(dt)
            game.tick(dt)
            payload = json.dumps(
                msg_world_tick(
                    world_time_s=game.time.world_time_s,
                    day_fraction=game.time.day_fraction,
                    entities=game.entity_snapshots(),
                )
            )
            stale: list[ServerConnection] = []
            for ws in clients:
                try:
                    await ws.send(payload)
                except Exception:
                    stale.append(ws)
            for ws in stale:
                clients.discard(ws)
    except asyncio.CancelledError:
        raise


def _inbound_to_utf8(raw: str | bytes) -> tuple[str | None, str | None]:
    """Retourne (texte, erreur) ; erreur non vide si frame refusée."""
    if isinstance(raw, str):
        data = raw.encode("utf-8")
        if len(data) > config.MAX_WS_INBOUND_BYTES:
            return None, "message trop volumineux"
        return raw, None
    if isinstance(raw, (bytes, bytearray)):
        if len(raw) > config.MAX_WS_INBOUND_BYTES:
            return None, "message trop volumineux"
        try:
            return raw.decode("utf-8"), None
        except UnicodeDecodeError:
            return None, "UTF-8 invalide"
    return None, "type de message non supporté"


async def client_handler(
    ws: ServerConnection,
    game: GameState,
    clients: set[ServerConnection],
) -> None:
    player_id: str | None = None
    last_move_at: float = 0.0
    try:
        async for raw in ws:
            text, err = _inbound_to_utf8(raw)
            if err:
                await ws.send(json.dumps(msg_error(err)))
                continue
            assert text is not None
            try:
                data: dict[str, Any] = json.loads(text)
            except json.JSONDecodeError:
                await ws.send(json.dumps(msg_error("JSON invalide")))
                continue
            msg_type = data.get("type")
            if msg_type == "hello":
                if player_id:
                    await ws.send(json.dumps(msg_error("hello déjà enregistré")))
                    continue
                name = str(data.get("player_name") or "Voyageur").strip() or "Voyageur"
                ent = game.add_player(name)
                player_id = ent.id
                clients.add(ws)
                await ws.send(
                    json.dumps(
                        msg_welcome(
                            player_id=ent.id,
                            planet_id=game.planet.id,
                            world_time_s=game.time.world_time_s,
                            day_fraction=game.time.day_fraction,
                            entities=game.entity_snapshots(),
                        )
                    )
                )
            elif msg_type == "move" and player_id:
                now = time.monotonic()
                if now - last_move_at < config.MOVE_MIN_INTERVAL_S:
                    continue
                last_move_at = now
                game.apply_player_move(
                    player_id,
                    float(data.get("x", 0.0)),
                    float(data.get("y", 0.0)),
                    float(data.get("z", 0.0)),
                )
            elif msg_type == "move" and not player_id:
                await ws.send(json.dumps(msg_error("hello requis avant move")))
            else:
                await ws.send(json.dumps(msg_error(f"type inconnu: {msg_type!r}")))
    finally:
        if player_id:
            game.remove_player(player_id)
        clients.discard(ws)


async def run_server(
    *,
    stop_event: asyncio.Event,
    register_signals: bool = False,
    host: str | None = None,
    port: int | None = None,
    ready_event: asyncio.Event | None = None,
    configure_logging: bool = False,
) -> None:
    """
    Lance le serveur jusqu'à ``stop_event``.
    ``register_signals`` : SIGINT / SIGTERM déclenchent ``stop_event`` (hors tests).
    ``ready_event`` : signalé une fois le socket en écoute (tests / orchestration).
    """
    if configure_logging:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    bind_host = host if host is not None else config.HOST
    bind_port = config.PORT if port is None else port

    loop = asyncio.get_running_loop()
    installed: list[int] = []
    if register_signals:
        def _shutdown() -> None:
            if not stop_event.is_set():
                LOG.info("Signal reçu — arrêt du serveur…")
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _shutdown)
                installed.append(int(sig))
            except (NotImplementedError, RuntimeError):
                LOG.warning("Impossible d'enregistrer le signal %s (plateforme)", sig)
                break

    game = GameState()
    clients: set[ServerConnection] = set()
    tick_task = asyncio.create_task(game_loop_broadcast(game, clients))

    async def _handler(ws: ServerConnection) -> None:
        await client_handler(ws, game, clients)

    try:
        LOG.info(
            "MMMORPG serveur Phase 1 — ws://%s:%s (tick %.1f Hz)",
            bind_host,
            bind_port,
            config.TICK_RATE_HZ,
        )
        async with serve(
            _handler,
            bind_host,
            bind_port,
            ping_interval=30,
            ping_timeout=60,
        ):
            if ready_event is not None:
                ready_event.set()
            await stop_event.wait()
        LOG.info("Serveur arrêté proprement.")
    finally:
        for sig_int in installed:
            try:
                loop.remove_signal_handler(sig_int)
            except Exception:
                pass
        tick_task.cancel()
        try:
            await tick_task
        except asyncio.CancelledError:
            pass


def main() -> None:
    async def _amain() -> None:
        stop = asyncio.Event()
        await run_server(
            stop_event=stop,
            register_signals=True,
            configure_logging=True,
        )

    asyncio.run(_amain())
