"""Tests sondes SOE M3 — critères login headless."""

from team.godot_soe_probe import _login_ok


def test_login_ok_full_message() -> None:
    out = "  [Login] OK connexion LoginServer terminee\n"
    assert _login_ok(out) is True


def test_login_ok_token_only_no_zone() -> None:
    out = (
        "  [LoginClientToken] account=4  user=Bot_IA\n"
        "  [Login] Aucun personnage disponible\n"
    )
    assert _login_ok(out) is True


def test_login_ok_enumerate_characters() -> None:
    out = "  [EnumerateCharacterId] 1 personnage(s)\n      [0] [cluster=3] Lia\n"
    assert _login_ok(out) is True


def test_login_ok_rejects_echec() -> None:
    out = "  [Login] ECHEC : aucun token recu\n"
    assert _login_ok(out) is False


def test_login_ok_rejects_empty_roster() -> None:
    out = "  [EnumerateCharacterId] 0 personnage(s)\n"
    assert _login_ok(out) is False
