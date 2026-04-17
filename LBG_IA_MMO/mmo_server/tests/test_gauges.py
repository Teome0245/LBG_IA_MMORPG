from lyra_engine.gauges import GaugesState


def test_gauges_step_increases_and_caps() -> None:
    g = GaugesState(hunger=0.99, thirst=0.99, fatigue=0.99)
    g.step(10_000)
    assert 0.0 <= g.hunger <= 1.0
    assert 0.0 <= g.thirst <= 1.0
    assert 0.0 <= g.fatigue <= 1.0
    assert g.hunger == 1.0
    assert g.thirst == 1.0
    assert g.fatigue == 1.0

