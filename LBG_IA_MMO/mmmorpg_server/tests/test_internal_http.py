from __future__ import annotations

import json
import urllib.request
import urllib.error

from mmmorpg_server.game_state import GameState
from mmmorpg_server.internal_http import start_internal_http


def _http_get_json(url: str, *, headers: dict[str, str] | None = None) -> dict:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(req, timeout=2.0) as r:  # nosec - tests only
        data = r.read().decode("utf-8")
    return json.loads(data)


def _http_post_json(url: str, payload: dict, *, headers: dict[str, str] | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8")
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=2.0) as r:  # nosec - tests only
            out = r.read().decode("utf-8")
            return int(r.status), json.loads(out)
    except urllib.error.HTTPError as e:
        out = e.read().decode("utf-8")
        return int(e.code), json.loads(out) if out else {}


def test_internal_http_healthz_and_lyra_snapshot() -> None:
    game = GameState()
    http = start_internal_http(host="127.0.0.1", port=0, game=game, token="")
    try:
        j = _http_get_json(f"http://127.0.0.1:{http.port}/healthz")
        assert j["status"] == "ok"
        feats = j.get("protocol_features") or {}
        assert feats.get("ws_move_world_commit") is True

        snap = _http_get_json(
            f"http://127.0.0.1:{http.port}/internal/v1/npc/npc:merchant/lyra-snapshot?trace_id=t1"
        )
        assert snap["status"] == "ok"
        lyra = snap["lyra"]
        assert lyra["version"] == "lyra-context-2"
        assert lyra["kind"] == "npc_world"
        assert lyra["meta"]["npc_id"] == "npc:merchant"
        assert lyra["meta"]["trace_id"] == "t1"
        assert lyra["meta"].get("race_id") == "race:halfblood_khar"
        assert lyra["meta"].get("race_display") == "Métis Khar'Zuun"
        rep = lyra["meta"]["reputation"]
        assert isinstance(rep, dict)
        assert isinstance(rep.get("value"), int)
        gauges = lyra["gauges"]
        assert 0.0 <= float(gauges["hunger"]) <= 1.0
        assert 0.0 <= float(gauges["thirst"]) <= 1.0
        assert 0.0 <= float(gauges["fatigue"]) <= 1.0
    finally:
        http.stop()


def test_internal_http_token_gate() -> None:
    game = GameState()
    http = start_internal_http(host="127.0.0.1", port=0, game=game, token="secret")
    try:
        # sans token -> 401
        req = urllib.request.Request(f"http://127.0.0.1:{http.port}/healthz", method="GET")
        try:
            urllib.request.urlopen(req, timeout=2.0)  # nosec - tests only
            assert False, "expected 401"
        except Exception as e:
            # urllib throws HTTPError
            assert "401" in str(e)

        j = _http_get_json(
            f"http://127.0.0.1:{http.port}/healthz",
            headers={"X-LBG-Service-Token": "secret"},
        )
        assert j["status"] == "ok"
        assert (j.get("protocol_features") or {}).get("ws_move_world_commit") is True
    finally:
        http.stop()


def test_internal_http_dialogue_commit_idempotent() -> None:
    game = GameState()
    http = start_internal_http(host="127.0.0.1", port=0, game=game, token="secret")
    try:
        url = f"http://127.0.0.1:{http.port}/internal/v1/npc/npc:merchant/dialogue-commit"
        headers = {"X-LBG-Service-Token": "secret"}

        code1, j1 = _http_post_json(url, {"trace_id": "t-commit-1", "flags": {"quest_accepted": True}}, headers=headers)
        assert code1 == 200
        assert j1["accepted"] is True

        # Même trace_id => noop mais accepté
        code2, j2 = _http_post_json(url, {"trace_id": "t-commit-1", "flags": {"quest_accepted": False}}, headers=headers)
        assert code2 == 200
        assert j2["accepted"] is True
    finally:
        http.stop()

def test_internal_http_commit_rejects_unknown_flags() -> None:
    game = GameState()
    http = start_internal_http(host="127.0.0.1", port=0, game=game, token="secret")
    try:
        url = f"http://127.0.0.1:{http.port}/internal/v1/npc/npc:merchant/dialogue-commit"
        headers = {"X-LBG-Service-Token": "secret"}
        code, j = _http_post_json(url, {"trace_id": "t-commit-bad-1", "flags": {"lol_nope": True}}, headers=headers)
        assert code == 409
        assert j["accepted"] is False
        assert "unsupported flag" in (j.get("reason") or "")
    finally:
        http.stop()


def test_internal_http_commit_rejects_too_many_flags() -> None:
    game = GameState()
    http = start_internal_http(host="127.0.0.1", port=0, game=game, token="secret")
    try:
        url = f"http://127.0.0.1:{http.port}/internal/v1/npc/npc:merchant/dialogue-commit"
        headers = {"X-LBG-Service-Token": "secret"}
        flags = {f"quest_id": "q:1", **{f"mood": "ok"}, **{f"rp_tone": "neutral"}}
        # ajouter 10 clés non supportées pour dépasser la limite
        for i in range(20):
            flags[f"k{i}"] = "x"
        code, j = _http_post_json(url, {"trace_id": "t-commit-bad-many", "flags": flags}, headers=headers)
        assert code == 409
        assert j["accepted"] is False
    finally:
        http.stop()


def test_internal_http_snapshot_exposes_world_flags_after_commit() -> None:
    game = GameState()
    http = start_internal_http(host="127.0.0.1", port=0, game=game, token="secret")
    try:
        commit_url = f"http://127.0.0.1:{http.port}/internal/v1/npc/npc:merchant/dialogue-commit"
        headers = {"X-LBG-Service-Token": "secret"}
        code, j = _http_post_json(commit_url, {"trace_id": "t-commit-ok-2", "flags": {"quest_id": "q:starter"}}, headers=headers)
        assert code == 200
        assert j["accepted"] is True

        snap = _http_get_json(
            f"http://127.0.0.1:{http.port}/internal/v1/npc/npc:merchant/lyra-snapshot?trace_id=t2",
            headers=headers,
        )
        flags = snap["lyra"]["meta"]["world_flags"]
        assert flags["quest_id"] == "q:starter"
    finally:
        http.stop()


def test_internal_http_snapshot_exposes_reputation_after_commit() -> None:
    game = GameState()
    http = start_internal_http(host="127.0.0.1", port=0, game=game, token="secret")
    try:
        commit_url = f"http://127.0.0.1:{http.port}/internal/v1/npc/npc:merchant/dialogue-commit"
        headers = {"X-LBG-Service-Token": "secret"}
        code, j = _http_post_json(
            commit_url,
            {"trace_id": "t-rep-1", "flags": {"reputation_delta": 11}},
            headers=headers,
        )
        assert code == 200
        assert j["accepted"] is True

        snap = _http_get_json(
            f"http://127.0.0.1:{http.port}/internal/v1/npc/npc:merchant/lyra-snapshot?trace_id=t-rep-snap",
            headers=headers,
        )
        rep = snap["lyra"]["meta"]["reputation"]["value"]
        assert rep == 11
    finally:
        http.stop()


def test_internal_http_snapshot_reflects_aid_gauges_after_commit() -> None:
    game = GameState()
    http = start_internal_http(host="127.0.0.1", port=0, game=game, token="secret")
    try:
        commit_url = f"http://127.0.0.1:{http.port}/internal/v1/npc/npc:merchant/dialogue-commit"
        headers = {"X-LBG-Service-Token": "secret"}

        snap1 = _http_get_json(
            f"http://127.0.0.1:{http.port}/internal/v1/npc/npc:merchant/lyra-snapshot?trace_id=t-aid-0",
            headers=headers,
        )
        g1 = snap1["lyra"]["gauges"]

        code, j = _http_post_json(
            commit_url,
            {"trace_id": "t-aid-1", "flags": {"aid_hunger_delta": -0.2, "aid_thirst_delta": -0.1, "aid_fatigue_delta": -0.3}},
            headers=headers,
        )
        assert code == 200
        assert j["accepted"] is True

        snap2 = _http_get_json(
            f"http://127.0.0.1:{http.port}/internal/v1/npc/npc:merchant/lyra-snapshot?trace_id=t-aid-2",
            headers=headers,
        )
        g2 = snap2["lyra"]["gauges"]

        assert float(g2["hunger"]) < float(g1["hunger"])
        assert float(g2["thirst"]) < float(g1["thirst"])
        assert float(g2["fatigue"]) < float(g1["fatigue"])
    finally:
        http.stop()


def test_internal_http_dialogue_commit_player_inventory() -> None:
    game = GameState()
    http = start_internal_http(host="127.0.0.1", port=0, game=game, token="secret")
    try:
        ply = game.add_player("HttpLoot")
        url = f"http://127.0.0.1:{http.port}/internal/v1/npc/npc:merchant/dialogue-commit"
        headers = {"X-LBG-Service-Token": "secret"}
        code_miss, j_miss = _http_post_json(
            url,
            {
                "trace_id": "t-inv-miss",
                "flags": {"player_item_id": "item:x", "player_item_qty_delta": 1},
            },
            headers=headers,
        )
        assert code_miss == 409
        assert j_miss.get("accepted") is False

        code_ok, j_ok = _http_post_json(
            url,
            {
                "trace_id": "t-inv-http",
                "player_id": ply.id,
                "flags": {
                    "player_item_id": "item:via_http",
                    "player_item_qty_delta": 2,
                    "player_item_label": "Objet HTTP",
                },
            },
            headers=headers,
        )
        assert code_ok == 200
        assert j_ok.get("accepted") is True
        inv = (game.entities[ply.id].stats or {}).get("inventory")
        assert isinstance(inv, list)
        row = next((x for x in inv if isinstance(x, dict) and x.get("item_id") == "item:via_http"), None)
        assert row is not None
        assert row.get("qty") == 2
    finally:
        http.stop()


def test_internal_http_rate_limit(monkeypatch: object) -> None:
    # Activer un RL très bas pour provoquer un 429 rapidement.
    import os

    os.environ["MMMORPG_INTERNAL_HTTP_RL_RPS"] = "1"
    os.environ["MMMORPG_INTERNAL_HTTP_RL_BURST"] = "1"
    try:
        game = GameState()
        http = start_internal_http(host="127.0.0.1", port=0, game=game, token="")
        try:
            _http_get_json(f"http://127.0.0.1:{http.port}/healthz")
            req = urllib.request.Request(f"http://127.0.0.1:{http.port}/healthz", method="GET")
            try:
                urllib.request.urlopen(req, timeout=2.0)  # nosec - tests only
                assert False, "expected 429"
            except Exception as e:
                assert "429" in str(e)
        finally:
            http.stop()
    finally:
        # Nettoyage env pour ne pas polluer d'autres tests.
        os.environ.pop("MMMORPG_INTERNAL_HTTP_RL_RPS", None)
        os.environ.pop("MMMORPG_INTERNAL_HTTP_RL_BURST", None)


def test_internal_http_metrics_disabled_by_default() -> None:
    game = GameState()
    http = start_internal_http(host="127.0.0.1", port=0, game=game, token="")
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{http.port}/metrics", method="GET")
        try:
            urllib.request.urlopen(req, timeout=2.0)  # nosec - tests only
            assert False, "expected 404"
        except urllib.error.HTTPError as e:
            assert int(e.code) == 404
            body = e.read().decode("utf-8")
            assert "metrics disabled" in body
    finally:
        http.stop()


def test_internal_http_metrics_enabled(monkeypatch: object) -> None:
    import os

    monkeypatch.setenv("MMMORPG_INTERNAL_HTTP_METRICS", "1")
    game = GameState()
    http = start_internal_http(host="127.0.0.1", port=0, game=game, token="")
    try:
        # Un hit normal pour générer des compteurs de réponses.
        _http_get_json(f"http://127.0.0.1:{http.port}/healthz")

        req = urllib.request.Request(f"http://127.0.0.1:{http.port}/metrics", method="GET")
        with urllib.request.urlopen(req, timeout=2.0) as r:  # nosec - tests only
            assert int(r.status) == 200
            body = r.read().decode("utf-8")
        assert "lbg_process_uptime_seconds" in body
        assert "mmmorpg_internal_http_http_responses_total" in body
    finally:
        http.stop()
