"""Tests catalogue perform Lia."""

from lbg_agents.lia_perform import is_valid_perform, perform_catalog_hint, perform_ids


def test_perform_ids_loaded():
    ids = perform_ids()
    assert "dance" in ids
    assert "search" in ids


def test_is_valid_perform():
    assert is_valid_perform("dance") is True
    assert is_valid_perform("unknown_gesture") is False


def test_hint_mentions_perform():
    hint = perform_catalog_hint()
    assert "perform" in hint
    assert "dance" in hint
