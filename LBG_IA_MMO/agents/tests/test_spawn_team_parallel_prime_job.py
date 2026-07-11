"""Tests spawn parallèle Vulcan + ZB-1."""

from __future__ import annotations

import lbg_agents.spawn_team_parallel_prime_job as job


def test_parallel_specs_has_build_and_zb1() -> None:
    objectives = [spec[1].lower() for spec in job.PARALLEL_SPECS]
    assert any("core3" in o or "vulcan" in o for o in objectives)
    assert any("zb-1" in o or "zb1" in o for o in objectives)


def test_parallel_context_flags() -> None:
    for _role, _obj, ctx in job.PARALLEL_SPECS:
        assert ctx.get("parallel_prime") is True
