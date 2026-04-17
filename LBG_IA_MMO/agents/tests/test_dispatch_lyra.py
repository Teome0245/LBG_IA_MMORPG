from lbg_agents.dispatch import invoke_after_route


def test_fallback_echoes_context_lyra_as_output_lyra() -> None:
    out = invoke_after_route(
        "agent.fallback",
        actor_id="p:1",
        text="test",
        context={"lyra": {"gauges": {"stress": 42}, "version": "0.1"}},
    )
    assert out["agent"] == "minimal_stub"
    assert out.get("lyra") == {"gauges": {"stress": 42}, "version": "0.1"}


def test_fallback_steps_gauges_when_lyra_engine_installed() -> None:
    out = invoke_after_route(
        "agent.fallback",
        actor_id="p:1",
        text="test",
        context={
            "lyra": {
                "gauges": {"hunger": 0.0, "thirst": 0.0, "fatigue": 0.0},
                "dt_s": 10_000.0,
            }
        },
    )
    ly = out.get("lyra")
    assert isinstance(ly, dict)
    g = ly.get("gauges")
    assert isinstance(g, dict)
    # step(10000) augmente hunger/thirst/fatigue (coefficients > 0 dans lyra_engine)
    assert g["hunger"] > 0.0 or g["thirst"] > 0.0 or g["fatigue"] > 0.0
    meta = ly.get("meta")
    assert isinstance(meta, dict)
    assert meta.get("lyra_engine") == "gauges.step"
    assert meta.get("dt_s") == 10_000.0
