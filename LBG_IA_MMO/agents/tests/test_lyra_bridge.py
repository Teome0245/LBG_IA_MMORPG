from lbg_agents.lyra_bridge import step_context_lyra_once


def test_step_context_lyra_once_no_lyra() -> None:
    ctx = {"npc_name": "X"}
    c2, ly = step_context_lyra_once(ctx)
    assert c2 is ctx
    assert ly is None


def test_step_context_lyra_once_echo_only() -> None:
    ctx = {"lyra": {"gauges": {"stress": 1}, "v": "1"}}
    c2, ly = step_context_lyra_once(ctx)
    assert c2 is ctx
    assert ly == ctx["lyra"]


def test_step_context_lyra_once_steps_and_copies_context() -> None:
    ctx = {
        "lyra": {
            "gauges": {"hunger": 0.0, "thirst": 0.0, "fatigue": 0.0},
            "dt_s": 5000.0,
        }
    }
    c2, ly = step_context_lyra_once(ctx)
    assert c2 is not ctx
    assert c2["lyra"]["gauges"]["hunger"] > 0
    assert ly == c2["lyra"]
