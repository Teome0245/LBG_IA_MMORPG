from lbg_agents.local_time import local_now_iso, local_tz


def test_local_tz_default_paris():
    assert local_tz().key == "Europe/Paris"


def test_local_now_iso_has_offset():
    ts = local_now_iso()
    assert "+" in ts or ts.endswith("Z") is False
    assert "T" in ts
