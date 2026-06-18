"""Sonde mémoire VM — parsing et planificateur."""

from __future__ import annotations

import pytest

from lbg_agents.vm_memory_probe import _parse_probe_output, _status


def test_parse_probe_output():
    raw = (
        "mem_total=12884901888 mem_used=8589934592 mem_avail=4294967296\n"
        "swap_total=4294967296 swap_used=0\n"
        "proc core3-clean 7864320\n"
        "proc python3 65536\n"
    )
    m = _parse_probe_output(raw)
    assert m["mem_total_b"] == 12884901888
    assert m["mem_avail_pct"] > 30
    assert m["top_processes"][0]["comm"] == "core3-clean"


def test_status_warn_and_critical():
    warn = _status({"mem_avail_pct": 12.0, "swap_used_pct": 0})
    crit = _status({"mem_avail_pct": 5.0, "swap_used_pct": 95.0})
    assert warn == "warn"
    assert crit == "critical"


