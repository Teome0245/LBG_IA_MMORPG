"""Tests inventaire réseau LAN."""

from __future__ import annotations

from unittest.mock import patch

from lbg_agents.network_inventory import run_network_inventory


def test_network_inventory_returns_devices(monkeypatch) -> None:
    monkeypatch.setenv("LBG_LAN_HOST_CORE", "192.168.0.140")
    monkeypatch.setenv("LBG_LAN_HOST_FRONT", "192.168.0.110")
    monkeypatch.setenv("LBG_LAN_HOST_MMO", "192.168.0.245")
    monkeypatch.setenv("LBG_AGENT_DESKTOP_URL", "http://192.168.0.10:5005")

    def fake_scan(cidr: str) -> dict[str, list[int]]:
        return {
            "192.168.0.1": [80, 443],
            "192.168.0.50": [5000, 5001],
            "192.168.0.60": [8006],
            "192.168.0.70": [902, 443],
        }

    with patch("lbg_agents.network_inventory._scan_subnet", side_effect=fake_scan):
        with patch("lbg_agents.network_inventory._http_probe", return_value={"ok": True, "status_code": 200}):
            with patch("lbg_agents.network_inventory._tcp_reachable", return_value=True):
                with patch("lbg_agents.network_inventory._http_fingerprint", return_value={"ok": False}):
                    out = run_network_inventory(actor_id="ops:1", text="inventaire réseau", context={})

    assert out["ok"] is True
    assert out["agent"] == "network_inventory"
    devices = out["devices"]
    assert isinstance(devices, list) and len(devices) >= 7
    hosts = {d["host"] for d in devices}
    assert "192.168.0.140" in hosts
    assert "192.168.0.1" in hosts
    assert "192.168.0.50" in hosts
    assert out["n_hosts_alive"] == 4
    assert "scan_cidr" in out
    syn = next(d for d in devices if d["host"] == "192.168.0.50")
    assert syn.get("device_hint") == "synology/nas"
    prox = next(d for d in devices if d["host"] == "192.168.0.60")
    assert prox.get("device_hint") == "proxmox"
    assert isinstance(out.get("devices_export"), list)
    core = next(d for d in devices if d["host"] == "192.168.0.140")
    assert "devops_probe" in (core.get("action_suggestions") or [])


def test_action_suggestions_for_desktop(monkeypatch) -> None:
    monkeypatch.setenv("LBG_NETWORK_SCAN_ENABLED", "0")
    monkeypatch.setenv(
        "LBG_NETWORK_KNOWN_DEVICES",
        '[{"host":"192.168.0.10","label":"pc-windows","role":"desktop"}]',
    )
    with patch("lbg_agents.network_inventory._tcp_reachable", return_value=True):
        with patch("lbg_agents.network_inventory._http_probe", return_value={"ok": True, "status_code": 200}):
            out = run_network_inventory(actor_id="ops:1", text="scan", context={})
    pc = next(d for d in out["devices"] if d["host"] == "192.168.0.10")
    assert "desktop_control" in pc.get("action_suggestions", [])


def test_router_override_replaces_wrong_gateway(monkeypatch) -> None:
    monkeypatch.setenv("LBG_NETWORK_SCAN_ENABLED", "0")
    monkeypatch.setenv("LBG_NETWORK_ROUTER_HOST", "192.168.0.254")
    monkeypatch.setenv(
        "LBG_NETWORK_KNOWN_DEVICES",
        '[{"host":"192.168.0.1","label":"freebox-routeur","role":"router"}]',
    )
    out = run_network_inventory(actor_id="ops:1", text="inventaire", context={})
    hosts = {d["host"]: d for d in out["devices"]}
    assert "192.168.0.1" not in hosts
    assert hosts["192.168.0.254"]["label"] == "freebox-routeur"


def test_network_inventory_known_devices_json(monkeypatch) -> None:
    monkeypatch.setenv(
        "LBG_NETWORK_KNOWN_DEVICES",
        '[{"host":"192.168.0.254","label":"freebox","role":"router"},'
        '{"host":"192.168.0.246","label":"precu-vm","role":"precu","server_id":"precu"}]',
    )
    monkeypatch.setenv("LBG_NETWORK_SCAN_ENABLED", "0")

    out = run_network_inventory(actor_id="ops:1", text="inventaire", context={})
    hosts = {d["host"] for d in out["devices"]}
    assert "192.168.0.254" in hosts
    assert "192.168.0.246" in hosts
    fb = next(d for d in out["devices"] if d["host"] == "192.168.0.254")
    assert fb.get("label") == "freebox"
    precu = next(d for d in out["devices"] if d["host"] == "192.168.0.246")
    assert precu.get("label") == "precu-vm"
    assert precu.get("server_id") == "precu"
