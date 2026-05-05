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
from mmmorpg_server.ia_context_sanitize import (
    build_server_session_summary_parts,
    merge_session_summaries,
    sanitize_ia_history,
)
from mmmorpg_server.internal_http import start_internal_http
from mmmorpg_server.persistence import load_state, save_state
from mmmorpg_server.protocol import (
    msg_error,
    msg_welcome,
    msg_world_tick,
)

LOG = logging.getLogger("mmmorpg")
PendingReply = tuple[str, str, dict[str, Any] | None]


def _player_quest_state(game: GameState, player_id: str) -> dict[str, Any] | None:
    ent = game.entities.get(player_id)
    if not ent or getattr(ent, "kind", None) != "player":
        return None
    st = ent.stats if isinstance(ent.stats, dict) else {}
    qs = st.get("quest_state")
    return qs if isinstance(qs, dict) else None


def _persist_game_state(game: GameState, raw_path: str, *, source: str) -> bool:
    """Sauvegarde l'état monde persistant sans interrompre la boucle WS."""
    path_text = (raw_path or "").strip()
    if not path_text:
        return False
    try:
        seen, flags, rep, gauges = game.export_commit_state()
        save_state(Path(path_text), seen_trace_ids=seen, npc_flags=flags, npc_reputation=rep, npc_gauges=gauges)
        LOG.info(
            "état mmmorpg sauvegardé vers %s (source=%s commits=%s, npcs=%s)",
            path_text,
            source,
            len(seen),
            len(flags),
        )
        return True
    except Exception as e:
        LOG.warning("impossible de sauvegarder l’état mmmorpg vers %s (source=%s) : %s", path_text, source, e)
        return False


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


def _dialogue_commit_world_event(
    *,
    commit: dict[str, Any],
    trace_id: str,
    reason: str,
) -> dict[str, Any]:
    """Construit l'événement client associé à un commit monde accepté."""
    npc_id = str(commit.get("npc_id") or "").strip()
    flags = commit.get("flags")
    flags_out = dict(flags) if isinstance(flags, dict) else {}
    summary = "État PNJ mis à jour."
    if any(str(k).startswith("aid_") for k in flags_out):
        summary = "Aide appliquée."
    elif flags_out.get("quest_completed") is True:
        qid = flags_out.get("quest_id")
        summary = (
            f"Quête accomplie: {qid.strip()}"
            if isinstance(qid, str) and qid.strip()
            else "Quête accomplie."
        )
    elif isinstance(flags_out.get("quest_id"), str):
        summary = f"Quête mise à jour: {flags_out['quest_id']}"
    elif "reputation_delta" in flags_out:
        summary = "Réputation mise à jour."
    return {
        "type": "dialogue_commit",
        "npc_id": npc_id,
        "trace_id": trace_id,
        "status": "accepted",
        "reason": reason,
        "flags": flags_out,
        "summary": summary,
    }


def _queue_ia_bridge(
    *,
    game: GameState,
    ws: ServerConnection,
    pending_replies: dict[ServerConnection, PendingReply | None],
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

    # Mobs: pas de dialogue IA (évite sangliers "courtois").
    npc_ent = game.get_npc(npc_id)
    if npc_ent is not None:
        role = str(getattr(npc_ent, "role", "") or "").strip().lower()
        if role in ("mob", "monster"):
            pending_replies[ws] = (
                "Les créatures sauvages ne parlent pas — utilisez le combat (touche A).",
                trace_id,
                None,
            )
            return

    game.freeze_npc_and_face(npc_id, player_id, duration=NPC_CONVERSATION_RESUME_DELAY_S)

    ctx: dict[str, Any] = {"world_npc_id": npc_id, "history": []}
    # Rang 2 (ADR 0004) : persona MMO explicite côté pont WS — le client ne peut pas forcer local_assistant ici.
    ctx["lyra_engagement"] = "mmo_persona"
    if isinstance(npc_name, str) and npc_name.strip():
        ctx["npc_name"] = npc_name.strip()
    if config.IA_PLACEHOLDER_ENABLED and config.IA_PLACEHOLDER_REPLY:
        placeholder = _format_ia_placeholder(config.IA_PLACEHOLDER_REPLY, ctx.get("npc_name") if isinstance(ctx.get("npc_name"), str) else None)
        if placeholder:
            pending_replies[ws] = (placeholder, trace_id, None)
    # Résumé session : toujours construire la partie serveur (quête + PNJ + mémoire monde légère),
    # même si le client n'envoie pas d'ia_context.
    server_ssum = build_server_session_summary_parts(
        quest_state=_player_quest_state(game, player_id),
        npc_id=npc_id,
        npc_name=npc_name,
        npc_flags=game.get_npc_commit_flags(npc_id),
    )
    client_raw = ia_context.get("session_summary") if isinstance(ia_context, dict) else None
    ssum_merged = merge_session_summaries(
        server_parts=server_ssum,
        client_raw=client_raw,
    )
    if ssum_merged:
        ctx["session_summary"] = ssum_merged
    if isinstance(ia_context, dict):
        hist_san = sanitize_ia_history(ia_context.get("history"))
        if hist_san:
            ctx["history"] = hist_san
    # Permet aux clients/outils d'injecter un mini contexte vers l'IA (borné).
    # Important: ne pas permettre d'écraser `world_npc_id` ni d'injecter des structures arbitraires.
    if isinstance(ia_context, dict) and ia_context:
        for k, v in ia_context.items():
            if k in ("session_summary", "history"):
                continue
            if k in ("_require_action_json", "_no_cache"):
                if isinstance(v, bool):
                    ctx[k] = v
            elif k == "_world_action_kind":
                if isinstance(v, str) and v.strip().lower() in ("aid", "quest"):
                    ctx[k] = v.strip().lower()
            elif k == "_active_quest_id":
                vid = v.strip() if isinstance(v, str) else ""
                if vid and len(vid) <= 80:
                    ctx[k] = vid
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
                pending_replies[ws] = ("Désolé, je ne peux pas t'aider maintenant.", tid, None)
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
                pending_replies[ws] = ("Désolé, je ne peux pas t'aider maintenant.", tid, None)
                game.freeze_npc_and_face(npc_id, player_id, duration=NPC_CONVERSATION_RESUME_DELAY_S)
                return
            tid = j.get("trace_id") or tid
            res = j.get("result")
            out = res.get("output") if isinstance(res, dict) else None
            remote = out.get("remote") if isinstance(out, dict) else None
            rep = remote.get("reply") if isinstance(remote, dict) else None
            world_event: dict[str, Any] | None = None
            commit, commit_err = _extract_ia_dialogue_commit(j, target_npc_id=npc_id)
            if commit_err:
                LOG.warning("Pont IA: commit ignoré (%s trace_id=%s source=%s)", commit_err, tid, source)
            elif commit is not None and isinstance(tid, str) and tid.strip():
                ok, reason = game.commit_dialogue(
                    npc_id=commit["npc_id"],
                    trace_id=tid.strip(),
                    flags=commit.get("flags"),
                    player_id=player_id,
                )
                if ok:
                    if not config.PERSIST_DISABLE:
                        _persist_game_state(game, config.STATE_PATH, source=f"ia:{source}")
                    LOG.info(
                        "Pont IA: commit appliqué (npc_id=%s trace_id=%s reason=%s source=%s)",
                        commit["npc_id"],
                        tid.strip(),
                        reason,
                        source,
                    )
                    world_event = _dialogue_commit_world_event(
                        commit=commit,
                        trace_id=tid.strip(),
                        reason=reason,
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
                pending_replies[ws] = (rep.strip(), tid.strip(), world_event)
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
                pending_replies[ws] = ("Désolé, je ne peux pas t'aider maintenant.", tid, world_event)
                game.freeze_npc_and_face(npc_id, player_id, duration=NPC_CONVERSATION_RESUME_DELAY_S)
        except Exception:
            LOG.exception("Pont IA: exception pendant l'appel backend (source=%s)", source)
            pending_replies[ws] = ("Désolé, je ne peux pas t'aider maintenant.", tid, None)
            game.freeze_npc_and_face(npc_id, player_id, duration=NPC_CONVERSATION_RESUME_DELAY_S)
            return

    asyncio.create_task(_fetch_and_queue())


async def game_loop_broadcast(
    game: GameState,
    clients: set[ServerConnection],
    pending_replies: dict[ServerConnection, PendingReply | None],
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
                    world_event = extra[2] if extra else None
                    # Champ de vision : filtrer les entités (et locations) selon la position du joueur.
                    pid = getattr(ws, "player_id", None)
                    if not isinstance(pid, str) or not pid.strip():
                        pid = None
                    entities = game.entity_snapshots()
                    locations = game.locations
                    if pid:
                        entities = _filter_entities_for_player(game, pid, entities)
                        locations = _filter_locations_for_player(game, pid, locations)
                        # Combat/events gameplay : une entrée max par tick (best-effort).
                        if world_event is None:
                            wev = game.pop_next_player_event(pid)
                            if isinstance(wev, dict) and wev:
                                world_event = wev
                    payload = json.dumps(
                        msg_world_tick(
                            world_time_s=game.time.world_time_s,
                            day_fraction=game.time.day_fraction,
                            entities=entities,
                            locations=locations,
                            npc_reply=npc_reply,
                            trace_id=trace_id,
                            world_event=world_event,
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


def _filter_entities_for_player(game: GameState, player_id: str, snaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ent = game.entities.get(player_id)
    if not ent:
        return snaps
    px = float(getattr(ent, "x", 0.0) or 0.0)
    pz = float(getattr(ent, "z", 0.0) or 0.0)
    r = float(config.FOV_RANGE_M)
    r2 = r * r
    g = getattr(game, "_village_tile_grid", None)
    pzone = "village"
    try:
        if isinstance(getattr(ent, "stats", None), dict):
            pzone = str(ent.stats.get("zone") or "village").strip() or "village"
    except Exception:
        pzone = "village"

    def los_ok(x: float, z: float) -> bool:
        if not config.FOV_LOS_ENABLED or g is None:
            return True
        # Raycast grossier sur tuiles (Bresenham)
        t0 = g.world_to_tile(px, pz)
        t1 = g.world_to_tile(x, z)
        if t0 is None or t1 is None:
            return True
        x0, y0 = t0
        x1, y1 = t1
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        xcur, ycur = x0, y0
        # On ignore la première tuile (position joueur) et la dernière (cible)
        while not (xcur == x1 and ycur == y1):
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                xcur += sx
            if e2 < dx:
                err += dx
                ycur += sy
            if xcur == x1 and ycur == y1:
                break
            if not g.is_walkable_tile(int(xcur), int(ycur)):
                return False
        return True

    out: list[dict[str, Any]] = []
    for s in snaps:
        try:
            # Filtre instance/zone (intérieurs): ne montrer que ce qui est dans la même zone.
            szone = "village"
            st = s.get("stats")
            if isinstance(st, dict):
                szone = str(st.get("zone") or "village").strip() or "village"
            if szone != pzone:
                # Toujours inclure soi-même (debug) même si mal taggé.
                if s.get("id") != player_id:
                    continue
            if s.get("id") == player_id:
                out.append(s)
                continue
            x = float(s.get("x", 0.0) or 0.0)
            z = float(s.get("z", 0.0) or 0.0)
            dx = x - px
            dz = z - pz
            if dx * dx + dz * dz > r2:
                continue
            if pzone == "village" and not los_ok(x, z):
                continue
            out.append(s)
        except Exception:
            continue
    return out


def _filter_locations_for_player(game: GameState, player_id: str, locs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ent = game.entities.get(player_id)
    if not ent:
        return locs
    px = float(getattr(ent, "x", 0.0) or 0.0)
    pz = float(getattr(ent, "z", 0.0) or 0.0)
    r = float(config.FOV_RANGE_M)
    r2 = r * r
    pzone = "village"
    try:
        if isinstance(getattr(ent, "stats", None), dict):
            pzone = str(ent.stats.get("zone") or "village").strip() or "village"
    except Exception:
        pzone = "village"
    out: list[dict[str, Any]] = []
    for loc in locs:
        try:
            lzone = str(loc.get("zone") or "village").strip() or "village"
            if lzone != pzone:
                continue
            x = float(loc.get("x", 0.0) or 0.0)
            z = float(loc.get("z", 0.0) or 0.0)
            dx = x - px
            dz = z - pz
            if dx * dx + dz * dz <= r2:
                out.append(loc)
        except Exception:
            continue
    return out


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
    pending_replies: dict[ServerConnection, PendingReply | None],
) -> None:
    player_id: str | None = None
    last_move_at: float = 0.0
    last_rate_limit_err_at: float = 0.0
    last_combat_at: float = 0.0
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
                resume_token = data.get("resume_token")
                ent = None
                if isinstance(resume_token, str) and resume_token.strip():
                    ent = game.resume_player_by_token(resume_token)
                if ent is None:
                    ent = game.add_player(name)
                player_id = ent.id
                setattr(ws, "player_id", player_id)
                game.mark_player_connected(player_id)
                sess = game.ensure_player_session(player_id)

                await ws.send(
                    json.dumps(
                        msg_welcome(
                            player_id=ent.id,
                            session_token=sess,
                            game_data=game.game_data_snapshot(),
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
                        player_id=player_id,
                        player_x=float(data.get("x", 0.0)),
                        player_z=float(data.get("z", 0.0)),
                    )
                    if not ok:
                        await ws.send(json.dumps(msg_error(f"world_commit refusé: {reason}")))
                        continue
                    if not config.PERSIST_DISABLE:
                        _persist_game_state(game, config.STATE_PATH, source="world_commit")

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
                    # Erreur au plus 1/s (sinon spam) — le client peut adapter son sendMove.
                    if now - last_rate_limit_err_at > 1.0:
                        last_rate_limit_err_at = now
                        await ws.send(json.dumps(msg_error("rate_limited: move")))
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
            elif msg_type == "combat" and player_id:
                now = time.monotonic()
                if now - last_combat_at < 0.05:
                    continue
                last_combat_at = now
                action = (data.get("action") or "").strip().lower()
                target_id = data.get("target_id")
                if action in ("start", "on", "1", "true"):
                    ok, reason = game.set_player_combat(player_id=player_id, active=True, target_id=target_id if isinstance(target_id, str) else None)
                    if not ok:
                        await ws.send(json.dumps(msg_error(f"combat refusé: {reason}")))
                elif action in ("stop", "off", "0", "false"):
                    game.set_player_combat(player_id=player_id, active=False)
                else:
                    await ws.send(json.dumps(msg_error("combat.action invalide (start|stop)")))
            elif msg_type == "trade" and player_id:
                side = data.get("side")
                npc_id = data.get("npc_id")
                item_id = data.get("item_id")
                qty = data.get("qty", 1)
                trace_id = data.get("trace_id")
                try:
                    qi = int(qty)
                except Exception:
                    qi = 0
                ok, reason = game.trade(
                    player_id=player_id,
                    npc_id=npc_id if isinstance(npc_id, str) else "",
                    side=side if isinstance(side, str) else "",
                    item_id=item_id if isinstance(item_id, str) else "",
                    qty=qi,
                    player_x=float(data.get("x", 0.0)),
                    player_z=float(data.get("z", 0.0)),
                    trace_id=trace_id if isinstance(trace_id, str) else None,
                )
                if not ok:
                    await ws.send(json.dumps(msg_error(f"trade refusé: {reason}")))
            elif msg_type == "quest" and player_id:
                action = (data.get("action") or "").strip().lower()
                quest_id = data.get("quest_id")
                npc_id = data.get("npc_id")
                if action in ("accept", "start"):
                    ok, reason = game.quest_accept(
                        player_id=player_id,
                        quest_id=quest_id if isinstance(quest_id, str) else "",
                        npc_id=npc_id if isinstance(npc_id, str) else None,
                        player_x=float(data.get("x", 0.0)),
                        player_z=float(data.get("z", 0.0)),
                    )
                    if not ok:
                        await ws.send(json.dumps(msg_error(f"quest refusé: {reason}")))
                elif action in ("turnin", "complete"):
                    ok, reason = game.quest_turnin(
                        player_id=player_id,
                        npc_id=npc_id if isinstance(npc_id, str) else None,
                        player_x=float(data.get("x", 0.0)),
                        player_z=float(data.get("z", 0.0)),
                    )
                    if not ok:
                        await ws.send(json.dumps(msg_error(f"quest refusé: {reason}")))
                else:
                    await ws.send(json.dumps(msg_error("quest.action invalide (accept|turnin)")))
            elif msg_type == "job" and player_id:
                action = (data.get("action") or "").strip().lower()
                if action in ("gather",):
                    kind = (data.get("kind") or "").strip().lower()
                    resource_id = data.get("resource_id")
                    ok, reason = game.job_gather(
                        player_id=player_id,
                        kind=kind,
                        resource_id=resource_id if isinstance(resource_id, str) else None,
                        player_x=float(data.get("x", 0.0)),
                        player_z=float(data.get("z", 0.0)),
                    )
                    if not ok:
                        await ws.send(json.dumps(msg_error(f"job refusé: {reason}")))
                elif action in ("craft",):
                    rid = data.get("recipe_id")
                    ok, reason = game.job_craft(player_id=player_id, recipe_id=rid if isinstance(rid, str) else "")
                    if not ok:
                        await ws.send(json.dumps(msg_error(f"job refusé: {reason}")))
                else:
                    await ws.send(json.dumps(msg_error("job.action invalide (gather|craft)")))
            elif msg_type == "door" and player_id:
                action = (data.get("action") or "").strip().lower()
                door_id = data.get("door_id")
                if action and action not in ("use", "open", "enter", "toggle"):
                    await ws.send(json.dumps(msg_error("door.action invalide (use)")))
                    continue
                ok, reason = game.use_door(
                    player_id=player_id,
                    door_id=door_id if isinstance(door_id, str) else "",
                    player_x=float(data.get("x", 0.0)) if "x" in data else None,
                    player_z=float(data.get("z", 0.0)) if "z" in data else None,
                )
                if not ok:
                    await ws.send(json.dumps(msg_error(f"door refusé: {reason}")))
            else:
                await ws.send(json.dumps(msg_error(f"type inconnu: {msg_type!r}")))
    finally:
        if player_id:
            game.mark_player_disconnected(player_id)
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
    pending_replies: dict[ServerConnection, PendingReply | None] = {}
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
