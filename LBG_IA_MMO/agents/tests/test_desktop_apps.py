"""Tests des aides open_app rapatriées de P03 (alias, chemin .exe, learn, hints, inférence)."""

from __future__ import annotations

import pytest

from lbg_agents.desktop_apps import (
    default_desktop_action_from_text,
    enrich_open_app_action,
    extract_exe_path_from_goal,
    hint_for_desktop_error,
    normalize_desktop_app,
    open_app_action_from_goal,
    open_app_args_from_goal,
)


def test_infer_vghd() -> None:
    act = default_desktop_action_from_text("tu peux lancer vghd sur mon pc ?")
    assert act and act["kind"] == "open_app" and act["app"] == "vghd"


def test_infer_none_without_verb() -> None:
    assert default_desktop_action_from_text("quelle heure est-il ?") is None


def test_normalize_aliases() -> None:
    assert normalize_desktop_app("MSWORD") == "word"
    assert normalize_desktop_app("swg") == "swgemu"
    assert normalize_desktop_app("notepad") == "notepadpp"


def test_enrich_office_learn_default_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_DESKTOP_OPEN_APP_LEARN", raising=False)
    act = enrich_open_app_action({"kind": "open_app", "app": "word"})
    assert act["app"] == "word"
    assert act.get("learn") is True


def test_learn_default_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_DESKTOP_OPEN_APP_LEARN", "0")
    # Office/custom restent à learn=true (hors PATH) même si auto-learn global off.
    act = enrich_open_app_action({"kind": "open_app", "app": "word"})
    assert act.get("learn") is True
    # Une app générique (firefox) ne force pas learn si auto-learn off.
    act2 = enrich_open_app_action({"kind": "open_app", "app": "firefox"})
    assert "learn" not in act2 or act2.get("learn") is not True


def test_exe_path_from_goal() -> None:
    exe = extract_exe_path_from_goal("lance swgemu sur mon pc (J:\\swgemu\\StarWarsGalaxies\\SWGEmu.exe)")
    assert exe == "J:\\swgemu\\StarWarsGalaxies\\SWGEmu.exe"


def test_open_app_args_swgemu_with_path() -> None:
    args = open_app_args_from_goal("lance swgemu sur mon pc (J:\\swgemu\\StarWarsGalaxies\\SWGEmu.exe)")
    assert args is not None
    assert args["app"] == "swgemu"
    assert args.get("command") == "J:\\swgemu\\StarWarsGalaxies\\SWGEmu.exe"
    assert args["learn"] is True


def test_open_app_action_alias_swg() -> None:
    act = open_app_action_from_goal("démarre swg")
    assert act is not None and act["app"] == "swgemu"


def test_hint_winerror() -> None:
    h = hint_for_desktop_error("[WinError 2] Le fichier spécifié est introuvable")
    assert h and "LBG_DESKTOP_APP_MAP_JSON" in h


def test_hint_allowlist() -> None:
    h = hint_for_desktop_error("app non autorisée (allowlist)")
    assert h and "LBG_DESKTOP_LEARN_ENABLED" in h


def test_hint_none_for_plain_message() -> None:
    assert hint_for_desktop_error("tout va bien") is None
