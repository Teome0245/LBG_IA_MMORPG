"""Registre minimal des VM LAN cibles (résolution server_id → hôte).

Rapatrié/condensé de LBG_Project_03 (`orchestrator/mcp/registry.py`) : permet aux actions
DevOps (``ssh_run``) de viser une VM par identifiant logique (``linux-140`` / ``core`` …)
plutôt qu'une IP en dur. Les hôtes sont surchargeables par variables d'environnement.
"""

from __future__ import annotations

import os

# Alias logiques -> rôle canonique.
_ALIASES: dict[str, str] = {
    "linux-140": "core",
    "core": "core",
    "backend": "core",
    "140": "core",
    "linux-110": "front",
    "front": "front",
    "nginx": "front",
    "pilot": "front",
    "110": "front",
    "linux-245": "precu",
    "precu": "precu",
    "swgemu": "precu",
    "245": "precu",
    "linux-246": "mmo",
    "mmo": "mmo",
    "prime": "mmo",
    "core3": "mmo",
    "swg": "mmo",
    "246": "mmo",
}

# Rôle -> (variable d'env hôte, IP par défaut LAN).
_ROLE_ENV: dict[str, tuple[str, str]] = {
    "core": ("LBG_LAN_HOST_CORE", "192.168.0.140"),
    "front": ("LBG_LAN_HOST_FRONT", "192.168.0.110"),
    "mmo": ("LBG_LAN_HOST_MMO", "192.168.0.246"),
    "precu": ("LBG_LAN_HOST_PRECU", "192.168.0.245"),
}


def canonical_role(server_id: str) -> str | None:
    s = (server_id or "").strip().lower()
    if not s:
        return None
    return _ALIASES.get(s)


def resolve_host(server_id: str) -> str | None:
    """Hôte (IP/nom) pour un identifiant de serveur, ou ``None`` si inconnu."""
    role = canonical_role(server_id)
    if role is None:
        return None
    env_key, default_ip = _ROLE_ENV[role]
    host = os.environ.get(env_key, "").strip()
    return (host.split(":")[0] if host else default_ip) or None


def known_server_ids() -> list[str]:
    return sorted(_ALIASES.keys())
