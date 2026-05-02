import json

import pytest

from lbg_agents.world_content import (
    format_creature_refs_for_prompt,
    format_race_for_prompt,
    list_race_ids,
    load_creatures_by_id,
    reset_cache,
)


def test_format_race_and_creatures_use_repo_catalog() -> None:
    reset_cache()
    s = format_race_for_prompt("race:human")
    assert s and "Humain" in s
    c = format_creature_refs_for_prompt(["creature:luporeve"])
    assert c and "Luporêve" in c and "Foret" in c


def test_custom_content_dir(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    reset_cache()
    d = tmp_path / "w"
    d.mkdir()
    (d / "races.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "races": [
                    {
                        "id": "race:custom",
                        "display_name": "Customoid",
                        "morphology": "Forme sphérique",
                        "lore_one_liner": "Vient d’ailleurs.",
                        "abilities": ["rouler"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (d / "creatures.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "creatures": [
                    {
                        "id": "creature:foo",
                        "name": "FooBeast",
                        "biome": "Test",
                        "danger_level": 9,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LBG_WORLD_CONTENT_DIR", str(d))
    reset_cache()
    ids = list_race_ids()
    assert "race:custom" in ids
    assert format_race_for_prompt("race:custom") and "Customoid" in format_race_for_prompt("race:custom")
    assert "FooBeast" in (format_creature_refs_for_prompt(["creature:foo"]) or "")
    assert "creature:foo" in load_creatures_by_id()
    monkeypatch.delenv("LBG_WORLD_CONTENT_DIR", raising=False)
    reset_cache()
