from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from lbg_companion_bot.main import create_app


def test_healthz_ok() -> None:
    app = create_app()
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_chat_stub_mode_persists_session(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "companion.sqlite3"
    monkeypatch.setenv("LBG_COMPANION_DB_PATH", str(db_path))
    monkeypatch.setenv("LBG_COMPANION_LLM_DISABLED", "1")
    monkeypatch.delenv("LBG_COMPANION_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LBG_COMPANION_LLM_MODEL", raising=False)

    app = create_app()
    client = TestClient(app)

    r1 = client.post("/v1/chat", json={"session_id": "s1", "text": "Salut !"}, params={"debug": "true"})
    assert r1.status_code == 200
    j1 = r1.json()
    assert j1["session_id"] == "s1"
    assert isinstance(j1["reply"], str) and j1["reply"]
    assert "debug" in j1 and isinstance(j1["debug"], dict)

    r2 = client.post("/v1/chat", json={"session_id": "s1", "text": "Tu te souviens ?"}, params={"debug": "false"})
    assert r2.status_code == 200
    j2 = r2.json()
    assert j2["session_id"] == "s1"
    assert isinstance(j2["reply"], str) and j2["reply"]
    assert j2.get("debug") is None

    assert db_path.exists()


def test_get_session_and_tick(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "companion.sqlite3"
    monkeypatch.setenv("LBG_COMPANION_DB_PATH", str(db_path))
    monkeypatch.setenv("LBG_COMPANION_LLM_DISABLED", "1")
    monkeypatch.setenv("LBG_COMPANION_AUTONOMOUS_MIN_NUDGE_INTERVAL_S", "1")
    monkeypatch.setenv("LBG_COMPANION_AUTONOMOUS_MAX_NUDGES_PER_WINDOW", "2")
    monkeypatch.setenv("LBG_COMPANION_AUTONOMOUS_WINDOW_S", "60")

    app = create_app()
    client = TestClient(app)

    r = client.post("/v1/chat", json={"session_id": "s2", "text": "Hello"}, params={"debug": "false"})
    assert r.status_code == 200

    s = client.get("/v1/session/s2", params={"limit": "10", "debug": "true"})
    assert s.status_code == 200
    js = s.json()
    assert js["session_id"] == "s2"
    assert isinstance(js["messages"], list)
    assert js.get("engine_state") is None or isinstance(js["engine_state"], dict)
    assert isinstance(js["meta"], dict)
    assert isinstance(js.get("last_message_id"), int)

    e0 = client.get("/v1/session/s2/events", params={"after_id": "0", "limit": "50", "debug": "false"})
    assert e0.status_code == 200
    je0 = e0.json()
    assert je0["session_id"] == "s2"
    assert isinstance(je0["events"], list)
    assert je0.get("debug") is None

    t = client.post("/v1/session/s2/tick", params={"debug": "true"})
    assert t.status_code == 200
    jt = t.json()
    assert jt["session_id"] == "s2"
    assert "debug" in jt and isinstance(jt["debug"], dict)

