"""Tests unitaires (hash compatible Core3)."""

from core3_account_admin import hash_password, is_local_host, random_salt_hex, status_label


def test_random_salt_length():
    assert len(random_salt_hex()) == 32


def test_hash_password_deterministic():
    salt = "a" * 32
    secret = "test-secret"
    h1 = hash_password("mypass", salt, secret)
    h2 = hash_password("mypass", salt, secret)
    assert h1 == h2
    assert len(h1) == 64


def test_hash_password_changes_with_salt():
    secret = "test-secret"
    assert hash_password("x", "salt1", secret) != hash_password("x", "salt2", secret)


def test_status_label():
    assert status_label(False, False) == "offline"
    assert status_label(True, False) == "starting"
    assert status_label(True, True) == "ready"


def test_parse_account_api_path():
    from core3_account_admin import parse_account_api_path

    assert parse_account_api_path("/api/accounts/precu/1/characters") == ("precu", 1, "characters")
    assert parse_account_api_path("/api/accounts/prime/4") == ("prime", 4, None)
    assert parse_account_api_path("/api/accounts/1/characters") == ("precu", 1, "characters")


def test_is_local_host():
    assert is_local_host("")
    assert is_local_host("127.0.0.1")
    assert is_local_host("localhost")
    assert not is_local_host("192.168.0.246")
