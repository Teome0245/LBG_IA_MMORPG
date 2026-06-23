"""Planner — supervision Proxmox."""

from __future__ import annotations

from services.planner import plan_deterministic


def test_plan_proxmox_supervision():
    plan = plan_deterministic("superviser l'état du cluster proxmox et les VMs")
    assert plan.steps
    assert plan.steps[0].action.get("kind") == "proxmox_status"
    assert "proxmox" in plan.reason.lower() or "Proxmox" in plan.steps[0].summary


def test_plan_proxmox_storage_supervision():
    plan = plan_deterministic(
        "Surveillance stockage Proxmox local-lvm et Prime 246 — sonde thin pool, remédiation disque si alerte"
    )
    assert plan.steps
    kinds = [s.action.get("kind") for s in plan.steps]
    assert "proxmox_storage" in kinds
    assert "storage_remediation_plan" in kinds
    assert "stockage" in plan.reason.lower() or "Proxmox" in plan.reason
