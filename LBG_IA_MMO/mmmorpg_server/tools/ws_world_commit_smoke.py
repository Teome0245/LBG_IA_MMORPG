#!/usr/bin/env python3
"""
Smoke — WebSocket `move` + `world_commit` (sans LLM) → vérif snapshot HTTP interne Lyra.

Usage (depuis LBG_IA_MMO/) :
  python3 mmmorpg_server/tools/ws_world_commit_smoke.py \\
    --ws ws://192.168.0.245:7733 \\
    --internal http://192.168.0.245:8773 \\
    --npc-id npc:merchant \\
    --reputation-delta 7

Prérequis : `websockets` (dépendance du paquet lbg-mmmorpg-server).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from websockets.asyncio.client import connect


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _healthz_features(*, internal_base: str, token: str) -> dict[str, Any]:
    url = f"{internal_base.rstrip('/')}/healthz"
    req = urllib.request.Request(url, method="GET")
    if token.strip():
        req.add_header("X-LBG-Service-Token", token.strip())
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body if isinstance(body, dict) else {}


def _get_rep(*, internal_base: str, npc_id: str, token: str, trace_q: str) -> int:
    path = f"/internal/v1/npc/{urllib.parse.quote(npc_id, safe=':')}/lyra-snapshot"
    url = f"{internal_base.rstrip('/')}{path}?trace_id={urllib.parse.quote(trace_q)}"
    req = urllib.request.Request(url, method="GET")
    if token.strip():
        req.add_header("X-LBG-Service-Token", token.strip())
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:800]
        raise SystemExit(f"HTTP {e.code} sur snapshot: {detail}") from e
    ly = body.get("lyra") if isinstance(body, dict) else None
    if not isinstance(ly, dict):
        raise SystemExit(f"réponse snapshot invalide: {body!r}"[:2000])
    meta = ly.get("meta") if isinstance(ly.get("meta"), dict) else {}
    rep = meta.get("reputation") if isinstance(meta.get("reputation"), dict) else {}
    try:
        return int(rep.get("value", 0))
    except Exception:
        return 0


async def _run(
    *,
    ws_url: str,
    internal_base: str,
    npc_id: str,
    token: str,
    rep_delta: int,
    timeout_s: float,
) -> None:
    hz = _healthz_features(internal_base=internal_base, token=token)
    feats = hz.get("protocol_features") if isinstance(hz.get("protocol_features"), dict) else {}
    if feats.get("ws_move_world_commit") is not True:
        raise SystemExit(
            "HTTP interne : healthz ne signale pas protocol_features.ws_move_world_commit. "
            "Le binaire sur la VM MMO est probablement **antérieur** au jalon WS `move.world_commit`. "
            "Redéploie le rôle **mmo** (ex. `LBG_DEPLOY_ROLE=mmo bash infra/scripts/deploy_vm.sh`) "
            "ou `LBG_DEPLOY_ROLE=all`, puis `systemctl restart lbg-mmmorpg-ws` sur 245."
        )

    trace = f"ws_world_commit_{uuid.uuid4().hex}"
    before = _get_rep(internal_base=internal_base, npc_id=npc_id, token=token, trace_q="before_" + trace)
    move_payload: dict[str, Any] = {
        "type": "move",
        "x": 3.0,
        "y": 0.0,
        "z": 2.0,
        "world_commit": {
            "npc_id": npc_id,
            "trace_id": trace,
            "flags": {"reputation_delta": int(rep_delta)},
        },
    }
    async with connect(ws_url, open_timeout=min(10.0, timeout_s)) as ws:
        await ws.send(_json_dumps({"type": "hello", "player_name": "smoke_world_commit"}))
        raw0 = await asyncio.wait_for(ws.recv(), timeout=min(10.0, timeout_s))
        w0 = json.loads(raw0)
        if w0.get("type") != "welcome":
            raise SystemExit(f"attendu welcome, reçu: {raw0[:500]!r}")
        await ws.send(_json_dumps(move_payload))
        deadline = time.time() + timeout_s
        saw_err = False
        while time.time() < deadline:
            raw = await asyncio.wait_for(ws.recv(), timeout=min(5.0, max(0.2, deadline - time.time())))
            msg = json.loads(raw)
            if msg.get("type") == "error":
                saw_err = True
                raise SystemExit(f"erreur WS serveur: {msg.get('message')}")
            if msg.get("type") == "world_tick":
                break
        if saw_err:
            raise SystemExit("erreur WS")
    # Laisse le temps au thread HTTP interne de voir l’état après commit (serveur = WS + HTTP).
    await asyncio.sleep(0.2)
    after = _get_rep(internal_base=internal_base, npc_id=npc_id, token=token, trace_q="after_" + trace)
    lo = max(-100, min(100, before + int(rep_delta)))
    if after != lo:
        raise SystemExit(
            f"réputation attendue {lo} (avant={before}, delta={rep_delta}), reçu {after}. "
            "Si healthz annonçait ws_move_world_commit mais la réputation ne bouge pas, "
            "vérifie `journalctl -u lbg-mmmorpg-ws -n 80` sur la VM MMO (erreur world_commit / refus)."
        )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ws", dest="ws_url", required=True, help="ex. ws://192.168.0.245:7733")
    p.add_argument("--internal", dest="internal_base", required=True, help="ex. http://192.168.0.245:8773")
    p.add_argument("--npc-id", default="npc:merchant")
    p.add_argument("--token", default="", help="X-LBG-Service-Token pour snapshot HTTP interne")
    p.add_argument("--reputation-delta", type=int, default=7)
    p.add_argument("--timeout", type=float, default=30.0)
    args = p.parse_args()
    asyncio.run(
        _run(
            ws_url=args.ws_url,
            internal_base=args.internal_base,
            npc_id=args.npc_id.strip(),
            token=args.token,
            rep_delta=int(args.reputation_delta),
            timeout_s=float(args.timeout),
        )
    )
    print("OK: WS move+world_commit → snapshot réputation cohérent")


if __name__ == "__main__":
    main()
