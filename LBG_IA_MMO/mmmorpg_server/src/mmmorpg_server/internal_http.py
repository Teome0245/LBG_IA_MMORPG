from __future__ import annotations

import json
import logging
import math
import os
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import unquote

from mmmorpg_server.game_state import GameState
from mmmorpg_server.world_catalog import race_display_name

LOG = logging.getLogger("mmmorpg.internal_http")

_metrics_lock = threading.Lock()
_metrics_started_s = time.time()
_metrics_counters: dict[str, int] = {}


def _metrics_enabled() -> bool:
    return os.environ.get("MMMORPG_INTERNAL_HTTP_METRICS", "0").strip().lower() in ("1", "true", "yes", "on")


def _metrics_inc(name: str, n: int = 1) -> None:
    if not _metrics_enabled():
        return
    if n <= 0:
        return
    with _metrics_lock:
        _metrics_counters[name] = int(_metrics_counters.get(name, 0)) + int(n)


def _metrics_render_text() -> str:
    with _metrics_lock:
        snap = dict(_metrics_counters)
    uptime = max(0.0, time.time() - _metrics_started_s)
    lines: list[str] = []
    lines.append("# HELP lbg_process_uptime_seconds Uptime du process (best-effort).")
    lines.append("# TYPE lbg_process_uptime_seconds gauge")
    lines.append(f"lbg_process_uptime_seconds {uptime:.3f}")
    for k in sorted(snap.keys()):
        lines.append(f"# HELP {k} Counter (auto-generated name).")
        lines.append(f"# TYPE {k} counter")
        lines.append(f"{k} {int(snap[k])}")
    lines.append("")
    return "\n".join(lines)

@dataclass
class _TokenBucket:
    rps: float
    burst: int
    tokens: float
    last_s: float


class _RateLimiter:
    def __init__(self, *, rps: float, burst: int) -> None:
        self._rps = float(rps)
        self._burst = int(burst)
        self._buckets: dict[str, _TokenBucket] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, *, now_s: float | None = None) -> bool:
        if self._rps <= 0.0 or self._burst <= 0:
            return True
        now = time.time() if now_s is None else float(now_s)
        with self._lock:
            b = self._buckets.get(key)
            if b is None:
                b = _TokenBucket(rps=self._rps, burst=self._burst, tokens=float(self._burst), last_s=now)
                self._buckets[key] = b
            # recharge
            dt = max(0.0, now - b.last_s)
            b.tokens = min(float(b.burst), b.tokens + dt * b.rps)
            b.last_s = now
            if b.tokens >= 1.0:
                b.tokens -= 1.0
                return True
            return False


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def _gauges_for_npc(*, npc_id: str, world_now_s: float) -> dict[str, float]:
    """
    Snapshot minimal (R&D) : jauges 0–1 cohérentes avec `fusion_spec_lyra.md` (kind=npc_world).
    On reste déterministe (npc_id + temps) pour avoir un comportement stable en test.
    """
    seed = sum(ord(c) for c in npc_id) % 997
    t = world_now_s * 0.01 + seed
    hunger = 0.45 + 0.25 * math.sin(t * 0.9)
    thirst = 0.55 + 0.25 * math.sin(t * 1.1 + 1.7)
    fatigue = 0.35 + 0.30 * math.sin(t * 0.7 + 0.3)
    return {
        "hunger": _clamp01(float(hunger)),
        "thirst": _clamp01(float(thirst)),
        "fatigue": _clamp01(float(fatigue)),
    }


def build_lyra_snapshot(*, game: GameState, npc_id: str, trace_id: str | None = None) -> dict[str, Any] | None:
    npc = game.get_npc(npc_id)
    if not npc:
        return None
    world_now_s = float(game.time.world_time_s)
    flags = game.get_npc_commit_flags(npc_id)
    lyra: dict[str, Any] = {
        "version": "lyra-context-2",
        "kind": "npc_world",
        "gauges": game.get_npc_gauges(npc_id, default=_gauges_for_npc(npc_id=npc_id, world_now_s=world_now_s)),
        "meta": {
            "source": "mmmorpg_ws",
            "world_now_s": world_now_s,
            "npc_id": npc.id,
            "npc_name": npc.name,
            "reputation": {"value": int(game.get_npc_reputation(npc_id))},
        },
    }
    rid = getattr(npc, "race_id", "") if npc else ""
    if isinstance(rid, str) and rid.strip():
        lyra["meta"]["race_id"] = rid.strip()
        lyra["meta"]["race_display"] = race_display_name(rid.strip())
    if flags:
        lyra["meta"]["world_flags"] = flags
    if isinstance(trace_id, str) and trace_id.strip():
        lyra["meta"]["trace_id"] = trace_id.strip()
    return lyra


def _parse_qs(url: str) -> dict[str, str]:
    if "?" not in url:
        return {}
    _, raw = url.split("?", 1)
    out: dict[str, str] = {}
    for part in raw.split("&"):
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
        else:
            k, v = part, ""
        out[k] = v
    return out


@dataclass(frozen=True)
class InternalHttp:
    server: ThreadingHTTPServer
    thread: threading.Thread
    host: str
    port: int

    def stop(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=2.0)


def start_internal_http(*, host: str, port: int, game: GameState, token: str = "") -> InternalHttp:
    token = token.strip()
    # Import local pour éviter une dépendance circulaire "config -> internal_http" en tests.
    from mmmorpg_server import config as cfg

    rl = _RateLimiter(rps=cfg.INTERNAL_HTTP_RL_RPS, burst=cfg.INTERNAL_HTTP_RL_BURST)
    # CORS (pilot_web / outils) : l'HTTP interne est souvent appelé cross-origin depuis un navigateur.
    # On reste permissif en LAN (serveur exposé uniquement réseau privé) et on s'appuie sur le token optionnel.
    cors_allow_origin = "*"
    cors_allow_headers = "Content-Type, X-LBG-Service-Token"
    cors_allow_methods = "GET, POST, OPTIONS"

    class Handler(BaseHTTPRequestHandler):
        server_version = "lbg-mmmorpg-internal-http/0.1"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 (format)
            # silence volontaire : journald côté systemd capture déjà WS ; HTTP interne est best-effort
            return

        def _rate_limit_ok(self) -> bool:
            remote = getattr(self, "client_address", ("?", 0))[0]
            return rl.allow(str(remote))

        def _send_ratelimited(self) -> None:
            self._send_json(
                HTTPStatus.TOO_MANY_REQUESTS,
                {"error": "rate_limited", "hint": "slow down", "retry_after_s": 1},
            )

        def _auth_ok(self) -> bool:
            if not token:
                return True
            got = self.headers.get("X-LBG-Service-Token", "")
            return isinstance(got, str) and got == token

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            # CORS (permet fetch depuis pilot_web ou un client Godot WebView)
            self.send_header("Access-Control-Allow-Origin", cors_allow_origin)
            self.send_header("Access-Control-Allow-Methods", cors_allow_methods)
            self.send_header("Access-Control-Allow-Headers", cors_allow_headers)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            try:
                meth = str(getattr(self, "command", "GET") or "GET")
                route = "json"
                if isinstance(self.path, str):
                    if self.path.startswith("/internal/v1/npc/") and "/lyra-snapshot" in self.path:
                        route = "lyra_snapshot"
                    elif self.path.startswith("/internal/v1/npc/") and self.path.endswith("/dialogue-commit"):
                        route = "dialogue_commit"
                    elif self.path == "/healthz":
                        route = "healthz"
                _metrics_inc(f"mmmorpg_internal_http_http_responses_total{{method=\"{meth}\",route=\"{route}\",status=\"{int(status)}\"}}")
            except Exception:
                pass

        def _send_plain(self, status: int, body: str, content_type: str) -> None:
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Access-Control-Allow-Origin", cors_allow_origin)
            self.send_header("Access-Control-Allow-Methods", cors_allow_methods)
            self.send_header("Access-Control-Allow-Headers", cors_allow_headers)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            try:
                meth = str(getattr(self, "command", "GET") or "GET")
                route = "metrics" if self.path == "/metrics" else "plain"
                _metrics_inc(f"mmmorpg_internal_http_http_responses_total{{method=\"{meth}\",route=\"{route}\",status=\"{int(status)}\"}}")
            except Exception:
                pass

        def do_OPTIONS(self) -> None:  # noqa: N802
            # Preflight CORS (navigateur) — ne nécessite pas d'auth.
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Access-Control-Allow-Origin", cors_allow_origin)
            self.send_header("Access-Control-Allow-Methods", cors_allow_methods)
            self.send_header("Access-Control-Allow-Headers", cors_allow_headers)
            self.send_header("Access-Control-Max-Age", "600")
            self.end_headers()
            try:
                _metrics_inc('mmmorpg_internal_http_http_responses_total{method="OPTIONS",route="cors_preflight",status="204"}')
            except Exception:
                pass

        def _read_json(self) -> dict[str, Any] | None:
            try:
                n = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                n = 0
            if n <= 0 or n > 256 * 1024:
                return None
            raw = self.rfile.read(n)
            try:
                data = json.loads(raw.decode("utf-8"))
            except Exception:
                return None
            return data if isinstance(data, dict) else None

        def do_GET(self) -> None:  # noqa: N802
            # Métriques Prometheus (opt-in) — hors auth / hors rate-limit (sinon on ne peut pas scraper facilement).
            if self.path == "/metrics":
                if not _metrics_enabled():
                    self._send_plain(HTTPStatus.NOT_FOUND, "metrics disabled\n", "text/plain; charset=utf-8")
                    return
                self._send_plain(HTTPStatus.OK, _metrics_render_text(), "text/plain; version=0.0.4; charset=utf-8")
                return

            if not self._rate_limit_ok():
                self._send_ratelimited()
                return
            if not self._auth_ok():
                try:
                    LOG.info(
                        "lyra_snapshot auth_denied remote=%s path=%s",
                        getattr(self, "client_address", ("?", 0))[0],
                        self.path,
                    )
                except Exception:
                    pass
                self._send_json(
                    HTTPStatus.UNAUTHORIZED,
                    {"error": "unauthorized", "hint": "missing/invalid X-LBG-Service-Token"},
                )
                return

            if self.path == "/healthz":
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "status": "ok",
                        "service": "mmmorpg_internal_http",
                        "ts": time.time(),
                        # Détectable par les smokes / ops : présent uniquement si le paquet déployé inclut le jalon WS.
                        "protocol_features": {"ws_move_world_commit": True},
                    },
                )
                return

            if self.path.startswith("/internal/v1/npc/") and "/lyra-snapshot" in self.path:
                # /internal/v1/npc/{npc_id}/lyra-snapshot?trace_id=...
                before, _, after = self.path.partition("?")
                prefix = "/internal/v1/npc/"
                suffix = "/lyra-snapshot"
                if not (before.startswith(prefix) and before.endswith(suffix)):
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                    return
                npc_id = unquote(before[len(prefix) : -len(suffix)]).strip()
                if not npc_id:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "bad_request", "detail": "npc_id vide"})
                    return
                qs = _parse_qs(self.path)
                trace_id = qs.get("trace_id")
                lyra = build_lyra_snapshot(game=game, npc_id=npc_id, trace_id=trace_id)
                if not lyra:
                    try:
                        LOG.info(
                            "lyra_snapshot npc_not_found npc_id=%s trace_id=%s remote=%s",
                            npc_id,
                            trace_id or "",
                            getattr(self, "client_address", ("?", 0))[0],
                        )
                    except Exception:
                        pass
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "npc_not_found", "npc_id": npc_id})
                    return
                try:
                    LOG.info(
                        "lyra_snapshot ok npc_id=%s trace_id=%s remote=%s",
                        npc_id,
                        trace_id or "",
                        getattr(self, "client_address", ("?", 0))[0],
                    )
                except Exception:
                    pass
                self._send_json(HTTPStatus.OK, {"status": "ok", "lyra": lyra})
                return

            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            if not self._rate_limit_ok():
                self._send_ratelimited()
                return
            if not self._auth_ok():
                self._send_json(
                    HTTPStatus.UNAUTHORIZED,
                    {"error": "unauthorized", "hint": "missing/invalid X-LBG-Service-Token"},
                )
                return

            # Phase 2 : commit idempotent (dialogue)
            # POST /internal/v1/npc/{npc_id}/dialogue-commit
            if self.path.startswith("/internal/v1/npc/") and self.path.endswith("/dialogue-commit"):
                prefix = "/internal/v1/npc/"
                suffix = "/dialogue-commit"
                npc_id = unquote(self.path[len(prefix) : -len(suffix)]).strip().strip("/")
                body = self._read_json()
                if body is None:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "bad_request", "detail": "JSON invalide"})
                    return
                trace_id = body.get("trace_id")
                flags = body.get("flags")
                pid_raw = body.get("player_id")
                player_id_sess: str | None = None
                if isinstance(pid_raw, str) and pid_raw.strip():
                    player_id_sess = pid_raw.strip()
                if not isinstance(trace_id, str):
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "bad_request", "detail": "trace_id requis"})
                    return
                ok, reason = game.commit_dialogue(
                    npc_id=npc_id,
                    trace_id=trace_id,
                    flags=flags if isinstance(flags, dict) else None,
                    player_id=player_id_sess,
                )
                if ok:
                    LOG.info(
                        "dialogue_commit accepted npc_id=%s trace_id=%s remote=%s",
                        npc_id,
                        trace_id.strip(),
                        getattr(self, "client_address", ("?", 0))[0],
                    )
                    self._send_json(HTTPStatus.OK, {"status": "ok", "accepted": True, "reason": reason})
                else:
                    LOG.info(
                        "dialogue_commit rejected npc_id=%s trace_id=%s reason=%s remote=%s",
                        npc_id,
                        trace_id.strip(),
                        reason,
                        getattr(self, "client_address", ("?", 0))[0],
                    )
                    self._send_json(HTTPStatus.CONFLICT, {"status": "ok", "accepted": False, "reason": reason})
                return

            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    httpd = ThreadingHTTPServer((host, port), Handler)
    actual_host, actual_port = httpd.server_address[0], int(httpd.server_address[1])
    t = threading.Thread(target=httpd.serve_forever, name="mmmorpg-internal-http", daemon=True)
    t.start()
    return InternalHttp(server=httpd, thread=t, host=str(actual_host), port=actual_port)

