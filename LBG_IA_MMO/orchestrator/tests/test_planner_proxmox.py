"""Planner — supervision Proxmox."""

from __future__ import annotations

from services.planner import plan_deterministic


def test_plan_proxmox_supervision():
    plan = plan_deterministic("superviser l'état du cluster proxmox et les VMs")
    assert plan.steps
    assert plan.steps[0].action.get("kind") == "proxmox_status"
    assert "proxmox" in plan.reason.lower() or "Proxmox" in plan.steps[0].summary
