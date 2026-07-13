"""Tests pont inspiration_scan (Pygmalion)."""

from __future__ import annotations

from pathlib import Path

from team.inspiration_scan import infographiste_ia_root, probe_inspiration_dataset
from team.models import TeamTask


def test_infographiste_ia_root_detects_sibling() -> None:
    root = infographiste_ia_root()
    if root is not None:
        assert (root / "orchestrator.py").is_file()


def test_probe_inspiration_dataset_without_dataset(monkeypatch, tmp_path: Path) -> None:
    fake = tmp_path / "Infographiste_IA"
    fake.mkdir()
    (fake / "orchestrator.py").write_text("# stub\n", encoding="utf-8")
    (fake / "config").mkdir()
    (fake / "config" / "art_styles.json").write_text('{"styles":{}}', encoding="utf-8")
    monkeypatch.setenv("LBG_INFOGRAPHISTE_IA_ROOT", str(fake))
    task = TeamTask(id="t1", role="dev_game", actor_id="test", objective="audit lora inspiration")
    out = probe_inspiration_dataset(task)
    assert out["kind"] == "inspiration_probe"
    assert out["ok"] is False
