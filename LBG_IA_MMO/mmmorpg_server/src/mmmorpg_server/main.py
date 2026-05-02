"""Point d'entrée WebSocket — Phase 1."""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
from websockets.asyncio.server import ServerConnection, serve

from mmmorpg_server import config
from mmmorpg_server.game_state import GameState, NPC_CONVERSATION_RESUME_DELAY_S
from mmmorpg_server.internal_http import start_internal_http
from mmmorpg_server.persistence import load_state, save_state
from mmmorpg_server.protocol import (
    msg_error,
    msg_welcome,
    msg_world_tick,
)

LOG = logging.getLogger("mmmorpg")


def _format_ia_placeholder(template: str, npc_name: str | None) -> str:
    """Rend le placeholder IA plus incarné sans attendre le LLM."""
    raw = (template or "").strip()
    if not raw:
        return ""
    name = npc_name.strip() if isinstance(npc_name, str) and npc_name.strip() else "Le PNJ"
    return raw.replace("{npc_name}", name).replace("Le PNJ", name)


def _parse_move_world_commit(data: dict[str, Any]) -> dict[str, Any] | None | str:
    """
    Option `world_commit` sur `move` : commit PNJ synchrones (même liste blanche que HTTP
    dialogue-commit), **sans** appeler le pont IA — utile gameplay v1 (jalon #2).

    Retourne :
      - None : absent
      - str : message d'erreur client
      - dict : {"npc_id": str, "trace_id": str, "flags": dict | None}
    """
    raw = data.get("world_commit")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return "world_commit doit être un objet JSON"
    npc_id = raw.get("npc_id")
    trace_id = raw.get("trace_id")
    if not isinstance(npc_id, str) or not npc_id.strip():
        return "world_commit.npc_id requis (string non vide)"
    if not isinstance(trace_id, str) or not trace_id.strip():
        return "world_commit.trace_id requis (string non vide)"
    flags = raw.get("flags")
    if flags is not None and not isinstance(flags, dict):
        return "world_commit.flags doit être un objet ou absent"
    return {"npc_id": npc_id.strip(), "trace_id": trace_id.strip(), "flags": flags if isinstance(flags, dict) else None}


def _extract_ia_dialogue_commit(
    route_response: dict[str, Any],
    *,
    target_npc_id: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """
    Extrait un commit monde produit par l'agent dialogue.

    Le serveur WS reste autoritaire : seul le PNJ ciblé par la conversation peut
    être modifié, et les flags seront revalidés par `GameState.commit_dialogue`.
    """
    target = (target_npc_id or "").strip()
    if not target or not isinstance(route_response, dict):
        return None, None

    result = route_response.get("result")
    output = result.get("output") if isinstance(result, dict) else None
    if not isinstance(output, dict):
        return None, None

    raw_commit = output.get("commit")
    if not isinstance(raw_commit, dict):
        remote = output.get("remote")
        raw_commit = remote.get("commit") if isinstance(remote, dict) else None
    if not isinstance(raw_commit, dict):
        return None, None

    raw_npc_id = raw_commit.get("npc_id")
    npc_id = raw_npc_id.strip() if isinstance(raw_npc_id, str) and raw_npc_id.strip() else target
    if npc_id != target:
        return None, f"commit npc mismatch: {npc_id!r} != {target!r}"

    flags = raw_commit.get("flags")
    if flags is not None and not isinstance(flags, dict):
        return None, "commit flags invalid"
    return {"npc_id": npc_id, "flags": flags if isinstance(flags, dict) else None}, None


def _queue_ia_bridge(
    *,
    game: GameState,
    ws: ServerConnection,
    pending_replies: dict[ServerConnection, tuple[str, str] | None],
    actor_id: str,
    player_id: str,
    text0: str,
    world_npc_id: str,
    npc_name: str | None,
    ia_context: dict[str, Any] | None,
    source: str,
) -> None:
    """Déclenche le pont jeu → IA (async) + placeholder optionnel."""
    if not config.IA_BACKEND_URL:
        return
    if not (isinstance(text0, str) and text0.strip() and isinstance(world_npc_id, str) and world_npc_id.strip()):
        return

    # Corrélation stable placeholder → réponse finale.
    # On génère un trace_id une fois, on le réutilise pour l'appel backend, et on met le même trace_id
    # sur le placeholder pour que le client puisse le remplacer.
    trace_id = uuid.uuid4().hex
    npc_id = world_npc_id.strip()
    game.freeze_npc_and_face(npc_id, player_id, duration=NPC_CONVERSATION_RESUME_DELAY_S)

    ctx: dict[str, Any] = {"world_npc_id": npc_id, "history": []}
    if isinstance(npc_name, str) and npc_name.strip():
        ctx["npc_name"] = npc_name.strip()
    if config.IA_PLACEHOLDER_ENABLED and config.IA_PLACEHOLDER_REPLY:
        placeholder = _format_ia_placeholder(config.IA_PLACEHOLDER_REPLY, ctx.get("npc_name") if isinstance(ctx.get("npc_name"), str) else None)
        if placeholder:
            pending_replies[ws] = (placeholder, trace_id)
    # Permet aux clients/outils d'injecter un mini contexte vers l'IA (borné).
    # Important: ne pas permettre d'écraser `world_npc_id` ni d'injecter des structures arbitraires.
    if isinstance(ia_context, dict) and ia_context:
        for k, v in ia_context.items():
            if k in ("_require_action_json", "_no_cache"):
                if isinstance(v, bool):
                    ctx[k] = v
    payload = {"actor_id": actor_id, "text": text0.strip(), "context": ctx}

    async def _fetch_and_queue() -> None:
        t0 = time.perf_counter()
        tid = trace_id
        try:
            timeout = httpx.Timeout(
                timeout=config.IA_TIMEOUT_S,
                connect=3.0,
                read=config.IA_TIMEOUT_S,
                write=10.0,
                pool=config.IA_TIMEOUT_S,
            )
            headers: dict[str, str] = {}
            if config.IA_BACKEND_TOKEN:
                headers["X-LBG-Service-Token"] = config.IA_BACKEND_TOKEN
            # Corrélation : trace_id côté backend/orchestrator/logs.
            headers["X-LBG-Trace-Id"] = tid
            LOG.info(
                "Pont IA: appel backend (source=%s actor_id=%s npc_id=%s trace_id=%s)",
                source,
                actor_id,
                npc_id,
                tid,
            )
            async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                r = await client.post(
                    f"{config.IA_BACKEND_URL}{config.IA_BACKEND_PATH}",
                    json=payload,
                    headers=headers,
                )
            if r.status_code != 200:
                LOG.warning(
                    "Pont IA: backend HTTP %s sur %s%s (trace_id=%s source=%s)",
                    r.status_code,
                    config.IA_BACKEND_URL,
                    config.IA_BACKEND_PATH,
                    tid,
                    source,
                )
                # UX: remplacer le placeholder par une fin explicite (sinon le joueur reste bloqué).
                pending_replies[ws] = ("Désolé, je ne peux pas t'aider maintenant.", tid)
                game.freeze_npc_and_face(npc_id, player_id, duration=NPC_CONVERSATION_RESUME_DELAY_S)
                return
            j = r.json()
            if not isinstance(j, dict):
                LOG.warning(
                    "Pont IA: réponse JSON invalide (type=%s trace_id=%s source=%s)",
                    type(j).__name__,
                    tid,
                    source,
                )
                pending_replies[ws] = ("Désolé, je ne peux pas t'aider maintenant.", tid)
                game.freeze_npc_and_face(npc_id, player_id, duration=NPC_CONVERSATION_RESUME_DELAY_S)
                return
            tid = j.get("trace_id") or tid
            res = j.get("result")
            out = res.get("output") if isinstance(res, dict) else None
            remote = out.get("remote") if isinstance(out, dict) else None
            rep = remote.get("reply") if isinstance(remote, dict) else None
            commit, commit_err = _extract_ia_dialogue_commit(j, target_npc_id=npc_id)
            if commit_err:
                LOG.warning("Pont IA: commit ignoré (%s trace_id=%s source=%s)", commit_err, tid, source)
            elif commit is not None and isinstance(tid, str) and tid.strip():
                ok, reason = game.commit_dialogue(
                    npc_id=commit["npc_id"],
                    trace_id=tid.strip(),
                    flags=commit.get("flags"),
                )
                if ok:
                    LOG.info(
                        "Pont IA: commit appliqué (npc_id=%s trace_id=%s reason=%s source=%s)",
                        commit["npc_id"],
                        tid.strip(),
                        reason,
                        source,
                    )
                else:
                    LOG.warning(
                        "Pont IA: commit refusé (npc_id=%s trace_id=%s reason=%s source=%s)",
                        commit["npc_id"],
                        tid.strip(),
                        reason,
                        source,
                    )
            if isinstance(rep, str) and rep.strip() and isinstance(tid, str) and tid.strip():
                pending_replies[ws] = (rep.strip(), tid.strip())
                game.freeze_npc_and_face(npc_id, player_id, duration=NPC_CONVERSATION_RESUME_DELAY_S)
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                LOG.info(
                    "Pont IA: reply en file (trace_id=%s elapsed_ms=%s source=%s)",
                    tid.strip(),
                    elapsed_ms,
                    source,
                )
            else:
                LOG.warning(
                    "Pont IA: pas de reply/trace_id (reply=%s, trace_id=%s)",
                    isinstance(rep, str) and bool(rep.strip()),
                    isinstance(tid, str) and bool(tid.strip()),
                )
                pending_replies[ws] = ("Désolé, je ne peux pas t'aider maintenant.", tid)
                game.freeze_npc_and_face(npc_id, player_id, duration=NPC_CONVERSATION_RESUME_DELAY_S)
        except Exception:
            LOG.exception("Pont IA: exception pendant l'appel backend (source=%s)", source)
            pending_replies[ws] = ("Désolé, je ne peux pas t'aider maintenant.", tid)
            game.freeze_npc_and_face(npc_id, player_id, duration=NPC_CONVERSATION_RESUME_DELAY_S)
            return

    asyncio.create_task(_fetch_and_queue())


async def game_loop_broadcast(
    game: GameState,
    clients: set[ServerConnection],
    pending_replies: dict[ServerConnection, tuple[str, str] | None],
) -> None:
    dt = 1.0 / config.TICK_RATE_HZ
    try:
        while True:
            await asyncio.sleep(dt)
            game.tick(dt)
            stale: list[ServerConnection] = []
            # Copie défensive : `clients` peut être modifié pendant l'itération (déconnexions / handlers).
            for ws in list(clients):
                try:
                    extra = pending_replies.get(ws)
                    npc_reply = extra[0] if extra else None
                    trace_id = extra[1] if extra else None
                    payload = json.dumps(
                        msg_world_tick(
                            world_time_s=game.time.world_time_s,
                            day_fraction=game.time.day_fraction,
                            entities=game.entity_snapshots(),
                            locations=game.locations,
                            npc_reply=npc_reply,
                            trace_id=trace_id,
                        )
                    )
                    await ws.send(payload)
                    # Ne consommer la réplique qu'une fois effectivement envoyée.
                    if extra is not None:
                        pending_replies.pop(ws, None)
                except Exception:
                    stale.append(ws)
            for ws in stale:
                clients.discard(ws)
                pending_replies.pop(ws, None)
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
    pending_replies: dict[ServerConnection, tuple[str, str] | None],
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

                await ws.send(
                    json.dumps(
                        msg_welcome(
                            player_id=ent.id,
                            planet_id=game.planet.id,
                            world_time_s=game.time.world_time_s,
                            day_fraction=game.time.day_fraction,
                            entities=game.entity_snapshots(),
                            locations=game.locations,
                        )
                    )
                )
                # Ajouter au broadcast *après* `welcome` pour éviter qu'un `world_tick` arrive
                # avant le message de bienvenue (race condition à 20 Hz).
                clients.add(ws)

                # Pont "jeu → IA" (optionnel) : réutiliser `hello` pour demander une réplique PNJ
                # en ajoutant des champs optionnels. Pour éviter de bloquer `welcome`, la réplique est
                # renvoyée sur le *prochain* `world_tick` (champs optionnels `npc_reply`, `trace_id`).
                if config.IA_BACKEND_URL:
                    text0 = data.get("text")
                    world_npc_id = data.get("world_npc_id")
                    npc_name = data.get("npc_name")
                    ia_context = data.get("ia_context")
                    _queue_ia_bridge(
                        game=game,
                        ws=ws,
                        pending_replies=pending_replies,
                        actor_id=f"player:{ent.id}",
                        player_id=ent.id,
                        text0=text0 if isinstance(text0, str) else "",
                        world_npc_id=world_npc_id if isinstance(world_npc_id, str) else "",
                        npc_name=npc_name if isinstance(npc_name, str) else None,
                        ia_context=ia_context if isinstance(ia_context, dict) else None,
                        source="hello",
                    )
            elif msg_type == "move" and player_id:
                text_ia = data.get("text")
                world_npc_id = data.get("world_npc_id")
                npc_name = data.get("npc_name")
                ia_context = data.get("ia_context")
                wc_payload = _parse_move_world_commit(data)
                if isinstance(wc_payload, str):
                    await ws.send(json.dumps(msg_error(wc_payload)))
                    continue
                has_ia = isinstance(text_ia, str) and text_ia.strip() and isinstance(world_npc_id, str) and world_npc_id.strip()
                if wc_payload is not None and has_ia:
                    await ws.send(
                        json.dumps(
                            msg_error(
                                "world_commit incompatible avec text+world_npc_id (pont IA) sur le même move"
                            )
                        )
                    )
                    continue
                if isinstance(wc_payload, dict):
                    ok, reason = game.commit_dialogue(
                        npc_id=wc_payload["npc_id"],
                        trace_id=wc_payload["trace_id"],
                        flags=wc_payload.get("flags"),
                    )
                    if not ok:
                        await ws.send(json.dumps(msg_error(f"world_commit refusé: {reason}")))
                        continue

                if has_ia:
                    # Pont IA via `move` (sans nouveau type) : ne pas être bloqué par l'anti-spam `move`.
                    _queue_ia_bridge(
                        game=game,
                        ws=ws,
                        pending_replies=pending_replies,
                        actor_id=f"player:{player_id}",
                        player_id=player_id,
                        text0=text_ia,
                        world_npc_id=world_npc_id,
                        npc_name=npc_name if isinstance(npc_name, str) else None,
                        ia_context=ia_context if isinstance(ia_context, dict) else None,
                        source="move",
                    )

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
    # Reprise persistance (phase 2) : commits/flags.
    if not config.PERSIST_DISABLE:
        raw_path = config.STATE_PATH or ""
        if raw_path:
            st = load_state(Path(raw_path))
            if st is not None:
                seen, flags, rep, gauges = st
                game.import_commit_state(seen_trace_ids=seen, npc_flags=flags, npc_reputation=rep, npc_gauges=gauges)
                LOG.info("état mmmorpg chargé depuis %s (commits=%s, npcs=%s)", raw_path, len(seen), len(flags))
    clients: set[ServerConnection] = set()
    pending_replies: dict[ServerConnection, tuple[str, str] | None] = {}
    tick_task = asyncio.create_task(game_loop_broadcast(game, clients, pending_replies))
    internal_http = None
    if config.INTERNAL_HTTP_PORT and config.INTERNAL_HTTP_PORT > 0:
        internal_http = start_internal_http(
            host=config.INTERNAL_HTTP_HOST,
            port=config.INTERNAL_HTTP_PORT,
            game=game,
            token=config.INTERNAL_HTTP_TOKEN,
        )
        LOG.info(
            "HTTP interne actif — http://%s:%s (healthz, internal/v1/npc/.../lyra-snapshot)",
            internal_http.host,
            internal_http.port,
        )

    async def _handler(ws: ServerConnection) -> None:
        await client_handler(ws, game, clients, pending_replies)

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
        if internal_http is not None:
            try:
                internal_http.stop()
            except Exception:
                pass
        # Sauvegarde persistance (phase 2) au shutdown.
        if not config.PERSIST_DISABLE:
            raw_path = config.STATE_PATH or ""
            if raw_path:
                try:
                    seen, flags, rep, gauges = game.export_commit_state()
                    save_state(Path(raw_path), seen_trace_ids=seen, npc_flags=flags, npc_reputation=rep, npc_gauges=gauges)
                    LOG.info("état mmmorpg sauvegardé vers %s (commits=%s, npcs=%s)", raw_path, len(seen), len(flags))
                except Exception as e:
                    LOG.warning("impossible de sauvegarder l’état mmmorpg vers %s : %s", raw_path, e)


def main() -> None:
    async def _amain() -> None:
        stop = asyncio.Event()
        await run_server(
            stop_event=stop,
            register_signals=True,
            configure_logging=True,
        )

    asyncio.run(_amain())
