from __future__ import annotations

import json
from pathlib import Path

from world.tools.watabou_import import build_grid_from_watabou, build_layout_from_watabou, build_watabou_stats


def test_import_watabou_pixie_seat_smoke() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "Boite à idées" / "pixie_seat.json"
    assert src.exists()

    grid = build_grid_from_watabou(watabou_json_path=src, tile_m=2.0, unit_m=1.0, padding_tiles=2)
    assert grid["kind"] == "watabou_grid_v1"
    w = int(grid["grid"]["w"])
    h = int(grid["grid"]["h"])
    assert w > 50
    assert h > 50
    rows = grid["grid"]["rows"]
    assert len(rows) == h
    assert all(len(r) == w for r in rows)

    # We should have at least some buildings and roads in this sample.
    joined = "\n".join(rows)
    assert "H" in joined
    assert "R" in joined

    layout = build_layout_from_watabou(watabou_json_path=src, unit_m=1.0)
    assert layout["kind"] == "watabou_layout_v1"
    assert len(layout["objects"]["buildings"]) > 10
    assert len(layout["objects"]["roads"]) > 1
    assert len(layout["objects"]["trees"]) > 10

    stats = build_watabou_stats(watabou_json_path=src, unit_m=1.0)
    assert stats["kind"] == "watabou_stats_v1"
    assert stats["buildings"] is not None
    assert stats["buildings"]["count"] == len(layout["objects"]["buildings"])
    assert stats["reference"]["doc_house_4x4tiles_at_2m_m2"] == 64.0

    # JSON-serializable
    json.dumps(grid)
    json.dumps(layout)
    json.dumps(stats)

