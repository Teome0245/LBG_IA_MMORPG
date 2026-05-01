import asyncio

import pytest

from services.lyra_regulator import regulate_lyra_if_configured


def test_regulator_world_reduces_highest_need(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_LYRA_REGULATOR_ENABLED", "1")
    monkeypatch.setenv("LBG_LYRA_REGULATOR_COOLDOWN_S", "0")
    ctx = {
        "lyra": {
            "kind": "npc_world",
            "gauges": {"hunger": 0.8, "thirst": 0.2, "fatigue": 0.3},
            "meta": {},
        }
    }

    async def _run() -> None:
        await regulate_lyra_if_configured(ctx)

    asyncio.run(_run())
    assert float(ctx["lyra"]["gauges"]["hunger"]) < 0.8
    assert ctx["lyra"]["meta"]["lyra_regulation"]["applied"] is True


def test_regulator_assistant_recovers_low_energy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_LYRA_REGULATOR_ENABLED", "1")
    monkeypatch.setenv("LBG_LYRA_REGULATOR_COOLDOWN_S", "0")
    ctx = {
        "lyra": {
            "kind": "assistant",
            "gauges": {"chaleur": 60.0, "energie": 20.0, "patience": 65.0, "confiance": 70.0},
            "meta": {},
        }
    }

    async def _run() -> None:
        await regulate_lyra_if_configured(ctx)

    asyncio.run(_run())
    assert float(ctx["lyra"]["gauges"]["energie"]) > 20.0
    assert ctx["lyra"]["meta"]["lyra_regulation"]["action"] == "recover_energy"


def test_regulator_respects_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_LYRA_REGULATOR_ENABLED", "1")
    monkeypatch.setenv("LBG_LYRA_REGULATOR_COOLDOWN_S", "3600")
    ctx = {
        "lyra": {
            "kind": "npc_world",
            "gauges": {"hunger": 0.8, "thirst": 0.2, "fatigue": 0.3},
            "meta": {},
        }
    }

    async def _run() -> None:
        await regulate_lyra_if_configured(ctx)
        before = float(ctx["lyra"]["gauges"]["hunger"])
        await regulate_lyra_if_configured(ctx)
        after = float(ctx["lyra"]["gauges"]["hunger"])
        assert after == before

    asyncio.run(_run())
    assert ctx["lyra"]["meta"]["lyra_regulation"]["reason"] == "cooldown"

