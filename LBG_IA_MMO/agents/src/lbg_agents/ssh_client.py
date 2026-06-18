"""Exécution SSH **allowlistée** vers les VM LAN (rapatrié de LBG_Project_03).

Utilise ``ssh`` en sous-processus (identité ``LBG_SSH_IDENTITY``, user ``LBG_SSH_USER``).
Pas de shell interactif ; commandes validées par allowlist avant envoi. **Désactivé par
défaut** (``LBG_MCP_SSH_ENABLED=1`` pour activer). Le moteur de jobs / la policy gèrent en
amont dry-run et approbation : ce module n'exécute que des commandes déjà autorisées.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class SshResult:
    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    host: str
    command: str
    transport: str = "ssh"

    @property
    def error(self) -> str:
        if self.ok:
            return ""
        return self.stderr.strip() or f"ssh exit {self.exit_code}"


def ssh_enabled() -> bool:
    """SSH désactivé par défaut (sécurité) ; ``LBG_MCP_SSH_ENABLED=1`` pour activer."""
    return os.environ.get("LBG_MCP_SSH_ENABLED", "0").strip().lower() in ("1", "true", "yes", "on")


def orchestrator_local_host() -> str:
    for key in ("LBG_ORCHESTRATOR_HOST", "LBG_LAN_HOST_CORE"):
        v = os.environ.get(key, "").strip()
        if v:
            return v.split(":")[0]
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return "127.0.0.1"


def ssh_user() -> str:
    return os.environ.get("LBG_SSH_USER", "").strip() or "lbg"


def should_use_ssh_for_host(host: str) -> bool:
    if not ssh_enabled():
        return False
    h = (host or "").strip()
    if not h or h in ("127.0.0.1", "localhost") or h.startswith("127."):
        return False
    return h != orchestrator_local_host()


def _ssh_opts() -> list[str]:
    opts = [
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=8",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "LogLevel=ERROR",
    ]
    identity = os.environ.get("LBG_SSH_IDENTITY", "").strip()
    if identity:
        opts.extend(["-i", identity])
    return opts


def _default_allow_patterns() -> list[re.Pattern[str]]:
    raw = os.environ.get("LBG_SSH_CMD_ALLOWLIST", "").strip()
    if raw:
        return [re.compile(p.strip(), re.I) for p in raw.split(",") if p.strip()]
    return [
        re.compile(r"^curl\s+-", re.I),
        re.compile(r"^systemctl\s+is-active\s+", re.I),
        re.compile(r"^systemctl\s+status\s+", re.I),
        re.compile(r"^test\s+-", re.I),
        re.compile(r"^uptime\b", re.I),
        re.compile(r"^df\s+-", re.I),
        re.compile(r"^free\b", re.I),
        re.compile(r"^journalctl\s+-u\s+", re.I),
    ]


def command_allowed(command: str) -> bool:
    cmd = (command or "").strip()
    if not cmd or len(cmd) > 4000:
        return False
    # Refus dur : substitutions/chaînage vers commandes destructrices.
    if re.search(r"[`$<>]|;\s*(rm|sudo|chmod|chown|mkfs|dd\s)", cmd, re.I):
        return False
    return any(p.search(cmd) for p in _default_allow_patterns())


def run_ssh(host: str, command: str, *, user: str | None = None, trusted: bool = False) -> SshResult:
    """Exécute ``command`` sur ``user@host`` (allowlist sauf ``trusted=True``)."""
    host = (host or "").strip()
    u = (user or ssh_user()).strip()
    cmd = (command or "").strip()
    if not trusted and not command_allowed(cmd):
        return SshResult(False, 1, "", f"commande SSH refusée (allowlist): {cmd[:120]}", host, cmd)
    argv = ["ssh", *_ssh_opts(), f"{u}@{host}", cmd]
    try:
        timeout = float(os.environ.get("LBG_SSH_TIMEOUT_S", "45"))
    except ValueError:
        timeout = 45.0
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return SshResult(False, 124, "", f"ssh timeout ({timeout}s)", host, cmd)
    except OSError as e:
        return SshResult(False, 1, "", f"{type(e).__name__}: {e}", host, cmd)
    return SshResult(
        ok=proc.returncode == 0,
        exit_code=int(proc.returncode),
        stdout=(proc.stdout or "")[:8000],
        stderr=(proc.stderr or "")[:2000],
        host=host,
        command=cmd,
    )
