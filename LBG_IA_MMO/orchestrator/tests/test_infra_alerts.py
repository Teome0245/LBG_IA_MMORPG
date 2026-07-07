"""Tests synthèse alertes infra."""

from __future__ import annotations

from services import jobs as svc_jobs
from services.infra_alerts import build_infra_alerts


def test_build_infra_alerts_empty(monkeypatch):
    monkeypatch.setattr(svc_jobs, "list_jobs", lambda actor_id=None: [])
    out = build_infra_alerts(include_probe=False)
    assert out["ok"] is True
    assert out["outcome"] == "ok"
    assert "summary_fr" in out


def test_build_infra_alerts_waiting_job(monkeypatch):
    job = svc_jobs.Job(
        id="job-test-wait",
        actor_id="system:storage_watchdog",
        objective="Surveillance stockage Proxmox",
        status="waiting_approval",
    )
    monkeypatch.setattr(svc_jobs, "list_jobs", lambda actor_id=None: [job])
    monkeypatch.setattr(
        "services.infra_alerts._fetch_proxmox_snapshot",
        lambda: {"ok": False, "skipped": "test"},
    )
    monkeypatch.setattr(
        "services.infra_alerts._fetch_gpu_snapshot",
        lambda: {"ok": False, "skipped": "test"},
    )
    out = build_infra_alerts(include_probe=False)
    assert out["outcome"] == "waiting_approval"
    assert out["pending_job_id"] == "job-test-wait"
    assert len(out["waiting_approval"]) == 1


def test_build_infra_alerts_ram_warn(monkeypatch):
    monkeypatch.setattr(svc_jobs, "list_jobs", lambda actor_id=None: [])
    monkeypatch.setattr(
        "services.infra_alerts._fetch_proxmox_snapshot",
        lambda: {
            "ok": True,
            "outcome": "warn",
            "alerts": ["precu: RAM VM 94% (vmid 245)"],
            "lan_vms": {
                "matched": {
                    "precu": {
                        "vmid": 245,
                        "status": {
                            "ok": True,
                            "status": {"mem_pct": 94.5, "cpu_pct": 18, "status": "running"},
                        },
                    }
                }
            },
        },
    )
    monkeypatch.setattr(
        "services.infra_alerts._fetch_gpu_snapshot",
        lambda: {"ok": True, "outcome": "warn", "summary_fr": "nvidia-smi KO"},
    )
    out = build_infra_alerts(include_probe=False)
    assert out["outcome"] in ("warn", "critical")
    assert "245" in out["summary_fr"] or "Précu" in out["summary_fr"] or "precu" in out["summary_fr"].lower()
    assert out["vm_dashboard"]
