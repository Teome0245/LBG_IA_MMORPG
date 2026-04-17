from lbg_agents.lyra_bridge import step_context_lyra_once


def test_mmo_world_source_skips_engine_step() -> None:
    ctx = {
        "lyra": {
            "gauges": {"hunger": 0.5, "thirst": 0.5, "fatigue": 0.5},
            "meta": {"source": "mmo_world", "world_now_s": 42.0},
        }
    }
    c2, out = step_context_lyra_once(ctx)
    assert c2["lyra"]["gauges"]["hunger"] == 0.5
    assert out == c2["lyra"]
