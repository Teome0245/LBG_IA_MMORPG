from lbg_agents.proxmox_client import proxmox_hosts


def test_proxmox_hosts_single_default(monkeypatch):
    monkeypatch.delenv("LBG_PROXMOX_HOSTS", raising=False)
    monkeypatch.delenv("LBG_PROXMOX_SSH_HOSTS", raising=False)
    monkeypatch.delenv("LBG_PROXMOX_HOST", raising=False)
    assert proxmox_hosts() == ["192.168.0.200"]


def test_proxmox_hosts_multi_csv(monkeypatch):
    monkeypatch.setenv("LBG_PROXMOX_HOSTS", "192.168.0.200, 192.168.0.201")
    assert proxmox_hosts() == ["192.168.0.200", "192.168.0.201"]
