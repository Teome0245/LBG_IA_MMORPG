#!/usr/bin/env python3
"""
Client CLI minimal — WS (mmmorpg) → pont IA → npc_reply.

Usage (depuis la racine LBG_IA_MMO/) :
  ./.venv/bin/python mmmorpg_server/tools/ws_ia_cli.py \
    --ws ws://192.168.0.245:7733 \
    --npc-id npc:innkeeper \
    --npc-name "Mara l’aubergiste" \
    --text "Une chambre pour la nuit, s'il vous plaît."

Sortie :
  - affiche `trace_id`
  - affiche la réplique `npc_reply`
  - mesure une latence (ms) jusqu'au premier message qui contient `npc_reply`
  - avec `--final-only`, mesure jusqu'au premier `npc_reply` dont `trace_id` est non vide
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from typing import Any

from websockets.asyncio.client import connect


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _percentile(sorted_nums: list[int], p: float) -> int | None:
    if not sorted_nums:
        return None
    idx = int((p * len(sorted_nums)) + 0.999999) - 1  # ceil(p*n)-1
    if idx < 0:
        idx = 0
    if idx >= len(sorted_nums):
        idx = len(sorted_nums) - 1
    return sorted_nums[idx]


async def _run_once(
    *,
    ws_uri: str,
    player_name: str,
    npc_id: str,
    npc_name: str,
    text: str,
    timeout_s: float,
    final_only: bool,
) -> dict[str, Any]:
    t0 = time.time()
    async with connect(ws_uri, open_timeout=3) as ws:
        await ws.send(
            _json_dumps(
                {
                    "type": "hello",
                    "player_name": player_name,
                    "world_npc_id": npc_id,
                    "npc_name": npc_name,
                    "text": text,
                }
            )
        )

        # Attendre `npc_reply` (peut arriver sur welcome ou sur un world_tick).
        # En mode fiabilisation, un placeholder peut arriver très vite (trace_id vide),
        # puis une réponse "finale" plus tard (trace_id non vide).
        deadline = time.time() + timeout_s
        got_welcome = False
        first_placeholder: dict[str, Any] | None = None
        while time.time() < deadline:
            raw = await asyncio.wait_for(ws.recv(), timeout=min(5.0, max(0.1, deadline - time.time())))
            msg = json.loads(raw)
            if msg.get("type") == "welcome":
                got_welcome = True
            reply = msg.get("npc_reply")
            if isinstance(reply, str) and reply.strip():
                trace_id = msg.get("trace_id")
                dt_ms = int(round((time.time() - t0) * 1000))
                tid = trace_id if isinstance(trace_id, str) else ""
                if final_only:
                    if tid.strip():
                        res = {
                            "ok": True,
                            "welcome_seen": bool(got_welcome),
                            "elapsed_ms": dt_ms,
                            "trace_id": tid.strip(),
                            "npc_reply": reply.strip(),
                        }
                        if first_placeholder is not None:
                            res["placeholder"] = first_placeholder
                        return res
                    # Placeholder / réponse sans trace : ignorer et continuer.
                    if first_placeholder is None:
                        first_placeholder = {
                            "ok": True,
                            "welcome_seen": bool(got_welcome),
                            "elapsed_ms": dt_ms,
                            "trace_id": "",
                            "npc_reply": reply.strip(),
                        }
                    continue

                # Mode "premier npc_reply" (par défaut)
                return {
                    "ok": True,
                    "welcome_seen": bool(got_welcome),
                    "elapsed_ms": dt_ms,
                    "trace_id": tid.strip(),
                    "npc_reply": reply.strip(),
                }

    if final_only:
        raise TimeoutError(f"timeout après {timeout_s:.1f}s (aucune réponse finale: npc_reply avec trace_id non vide)")
    raise TimeoutError(f"timeout après {timeout_s:.1f}s (aucun npc_reply reçu)")


def main() -> int:
    p = argparse.ArgumentParser(description="Client CLI WS → pont IA → npc_reply")
    p.add_argument("--ws", default="ws://192.168.0.245:7733", help="URI WebSocket mmmorpg")
    p.add_argument("--player-name", default="cli", help="Nom joueur (hello)")
    p.add_argument("--npc-id", required=True, help="world_npc_id (ex. npc:innkeeper)")
    p.add_argument("--npc-name", default="PNJ", help="npc_name (affichage IA)")
    p.add_argument("--text", required=True, help="Texte joueur à envoyer")
    p.add_argument("--timeout-s", type=float, default=60.0, help="Timeout total d'attente npc_reply")
    p.add_argument("--repeat", type=int, default=1, help="Nombre d'itérations (benchmark séquentiel)")
    p.add_argument("--sleep-ms", type=int, default=0, help="Pause (ms) entre itérations")
    p.add_argument("--json", action="store_true", help="Sortie JSON (benchmark / automation)")
    p.add_argument(
        "--final-only",
        action="store_true",
        help="Attendre une réponse finale (trace_id non vide) au lieu du premier npc_reply (placeholder possible).",
    )
    args = p.parse_args()

    try:
        repeat = max(1, int(args.repeat))
        sleep_ms = max(0, int(args.sleep_ms))

        async def _amain() -> dict[str, Any]:
            times: list[int] = []
            errors: list[str] = []
            last_ok: dict[str, Any] | None = None
            last_placeholder: dict[str, Any] | None = None
            for i in range(repeat):
                try:
                    res = await _run_once(
                        ws_uri=args.ws,
                        player_name=args.player_name,
                        npc_id=args.npc_id,
                        npc_name=args.npc_name,
                        text=args.text,
                        timeout_s=float(args.timeout_s),
                        final_only=bool(args.final_only),
                    )
                    ph = res.get("placeholder")
                    if isinstance(ph, dict):
                        last_placeholder = ph
                    last_ok = res
                    times.append(int(res["elapsed_ms"]))
                except Exception as e:
                    errors.append(f"{type(e).__name__}: {e}")
                if sleep_ms and i < repeat - 1:
                    await asyncio.sleep(sleep_ms / 1000.0)

            sorted_times = sorted(times)
            out: dict[str, Any] = {
                "ok": bool(times),
                "n_requested": repeat,
                "n_ok": len(times),
                "n_errors": len(errors),
                "min_ms": sorted_times[0] if sorted_times else None,
                "p50_ms": _percentile(sorted_times, 0.50),
                "p95_ms": _percentile(sorted_times, 0.95),
                "max_ms": sorted_times[-1] if sorted_times else None,
                "errors": errors[:5],
            }
            if last_ok is not None:
                out["trace_id"] = last_ok.get("trace_id", "")
                out["npc_reply"] = last_ok.get("npc_reply", "")
                out["welcome_seen"] = bool(last_ok.get("welcome_seen"))
            if last_placeholder is not None:
                out["placeholder_reply"] = last_placeholder.get("npc_reply", "")
                out["placeholder_elapsed_ms"] = last_placeholder.get("elapsed_ms")
            return out

        summary = asyncio.run(_amain())
        if args.json or repeat > 1:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            if summary.get("ok") is True:
                print("ok: true")
                print(f"welcome_seen: {str(bool(summary.get('welcome_seen'))).lower()}")
                print(f"elapsed_ms: {int(summary.get('min_ms') or 0)}")
                print(f"trace_id: {summary.get('trace_id','')}")
                print("npc_reply:")
                print(summary.get("npc_reply", ""))
            else:
                print(f"ok: false\nerror: {', '.join(summary.get('errors') or ['erreur inconnue'])}")
                return 2
        return 0 if summary.get("ok") else 2
    except TimeoutError as e:
        print(f"ok: false\nerror: {e}")
        return 2
    except Exception as e:
        print(f"ok: false\nerror: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

