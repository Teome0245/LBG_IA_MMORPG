from fastapi.testclient import TestClient

from lbg_agents.combat_http_app import app


def test_healthz_shape() -> None:
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    assert j["service"] == "combat_http"
    assert j["invoke"] == "POST /invoke"


def test_invoke_returns_stub_shape() -> None:
    client = TestClient(app)
    r = client.post(
        "/invoke",
        json={"actor_id": "p:1", "text": "Je combats un gobelin", "context": {}},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["agent"] == "combat_stub"
    enc = j.get("encounter")
    assert isinstance(enc, dict)
    assert enc.get("opponent") == "Gobelin"
