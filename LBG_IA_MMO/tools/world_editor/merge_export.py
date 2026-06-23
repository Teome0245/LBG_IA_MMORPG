#!/usr/bin/env python3
"""Fusion export World Editor → catalogue PNJ + world_poi + locations."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def load_session(path: Path) -> dict:
    if not path.is_file():
        return {"active": False, "npc_slots": {}, "poi": {}}
    sess = {"active": False, "actor": "", "npc_slots": {}, "poi": {}, "last_dump": None}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k == "active":
            sess["active"] = v in ("1", "true")
        elif k == "actor":
            sess["actor"] = v
        elif k.startswith("npc:"):
            pid = k[4:]
            parts = v.split(",")
            if len(parts) >= 5:
                sess["npc_slots"][pid] = {
                    "x": float(parts[0]),
                    "y": float(parts[1]),
                    "z": float(parts[2]),
                    "cell": int(float(parts[3])),
                    "heading": float(parts[4]),
                    "mobile": parts[5] if len(parts) > 5 else "",
                    "roster_id": parts[6] if len(parts) > 6 else "",
                }
        elif k.startswith("wpoi."):
            poi_id = k[5:]
            parts = v.split(",")
            if len(parts) >= 5:
                sess["poi"][poi_id] = {
                    "template": parts[0],
                    "x": float(parts[1]),
                    "y": float(parts[2]),
                    "z": float(parts[3]),
                    "heading": float(parts[4]),
                    "object_id": int(float(parts[5])) if len(parts) > 5 else 0,
                    "root_cell_id": int(float(parts[6])) if len(parts) > 6 else 0,
                }
    return sess


def build_pilot_roster_map(catalog: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for r in catalog.get("rosters", []):
        rid = r.get("roster_id") or ""
        for s in r.get("slots", []):
            pid = s.get("pilot_id")
            if pid:
                out[pid] = rid
    return out


def enrich_npc_rosters(npc_slots: dict, pilot_roster: dict[str, str]) -> None:
    for pid, slot in npc_slots.items():
        if not slot.get("roster_id"):
            slot["roster_id"] = pilot_roster.get(pid, "")


def merge_npc_into_catalog(catalog: dict, npc_slots: dict) -> int:
    """Met à jour service_post + binding.post/home pour les rosters trainers."""
    roster_posts: dict[str, dict] = {}
    for pid, slot in npc_slots.items():
        rid = slot.get("roster_id") or ""
        if not rid:
            continue
        post = {
            "x": slot["x"],
            "y": slot["y"],
            "z": slot["z"],
            "heading": slot["heading"],
            "cell": slot["cell"],
        }
        roster_posts[rid] = post

    updated = 0
    for r in catalog.get("rosters", []):
        rid = r.get("roster_id")
        if rid not in roster_posts:
            continue
        post = roster_posts[rid]
        r["service_post"] = dict(post)
        for s in r.get("slots", []):
            b = s.setdefault("binding", {})
            b["post"] = dict(post)
            b["home"] = dict(post)
        updated += 1
    return updated


def merge_lost_heaven_hub(content: Path, poi_map: dict) -> None:
    """Met à jour lost_heaven_hub.json quand le starport est exporté."""
    hub_path = content / "locations/lost_heaven_hub.json"
    if not hub_path.is_file():
        return
    star = poi_map.get("poi:lost_heaven_starport")
    if not star:
        return
    hub = json.loads(hub_path.read_text(encoding="utf-8"))
    hub["status"] = "starport_placed"
    wx = float(star.get("x", 0))
    wy = float(star.get("y", 0))
    wz = float(star.get("z", 9))
    hub["world_anchor"] = {"x": wx, "y": wy, "z": wz}
    nps = hub.get("new_player_spawn") or {}
    nps["world"] = {
        "x": wx,
        "y": wy,
        "z": wz,
        "heading": float(star.get("heading", 90)),
        "cell": int(star.get("root_cell_id", 0) or 0),
    }
    nps["status"] = "active_structure"
    hub["new_player_spawn"] = nps
    for poi in hub.get("poi_buildings") or []:
        if poi.get("poi_id") == "poi:lost_heaven_starport":
            poi["status"] = "placed"
            poi["structure_template"] = star.get("template", "")
            poi["object_id"] = star.get("object_id", 0)
            poi["root_cell_id"] = star.get("root_cell_id", 0)
            break
    hub_path.write_text(json.dumps(hub, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def merge_locations(loc: dict, npc_slots: dict, poi: dict) -> None:
    if poi.get("root_cell_id"):
        loc["building_cell"] = poi["root_cell_id"]
    posts_by_prof = {}
    for pid, slot in npc_slots.items():
        rid = slot.get("roster_id") or ""
        for prefix in (
            "roster:mos_trainer_",
            "roster:mos_entertainer_trainer",
        ):
            if rid.startswith(prefix) or rid == prefix.rstrip("_"):
                prof = rid.replace("roster:mos_trainer_", "").replace(
                    "roster:mos_entertainer_trainer", "entertainer"
                )
                posts_by_prof[prof] = slot
    for p in loc.get("posts", []):
        prof = p.get("profession")
        if prof and prof in posts_by_prof:
            s = posts_by_prof[prof]
            p["spawn"] = {
                "x": s["x"],
                "y": s["y"],
                "z": s["z"],
                "heading": s["heading"],
                "cell": s["cell"],
            }


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/opt/LBG_IA_MMO")
    bin_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/opt/lbg-new-mmo-clean/MMOCoreORB/bin")
    session_path = bin_dir / "ia_bridge/world_editor_session.json"
    content = root / "content/core3"

    sess = load_session(session_path)
    npc_slots = sess.get("npc_slots") or {}
    poi_map: dict = sess.get("poi") or {}

    catalog_path = content / "core3_npc_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    enrich_npc_rosters(npc_slots, build_pilot_roster_map(catalog))
    n = merge_npc_into_catalog(catalog, npc_slots)
    catalog_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    me_poi = poi_map.get("poi:mos_eisley_training_center") or {}
    loc_path = content / "locations/mos_eisley_training_center.json"
    if loc_path.is_file() and me_poi:
        loc = json.loads(loc_path.read_text(encoding="utf-8"))
        merge_locations(loc, npc_slots, me_poi)
        loc_path.write_text(json.dumps(loc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    merge_lost_heaven_hub(content, poi_map)

    npc_export = [
        {
            "pilot_id": pid,
            "roster_id": s.get("roster_id", ""),
            "mobile_template": s.get("mobile", ""),
            "service_post": {
                "x": s["x"],
                "y": s["y"],
                "z": s["z"],
                "heading": s["heading"],
                "cell": s["cell"],
            },
        }
        for pid, s in npc_slots.items()
    ]
    pois_export = []
    for poi_id in sorted(poi_map.keys()):
        p = poi_map[poi_id]
        pois_export.append(
            {
                "poi_id": poi_id,
                "structure_template": p.get("template", ""),
                "world": {
                    "x": p.get("x"),
                    "y": p.get("y"),
                    "z": p.get("z", 6),
                    "heading": p.get("heading", 0),
                },
                "root_cell_id": p.get("root_cell_id", 0),
                "object_id": p.get("object_id", 0),
            }
        )
    export_doc = {
        "schema_version": 1,
        "zone_id": "tatooine",
        "display_zone": "Scrapaltai",
        "hub_location_id": "loc:lost_heaven_hub",
        "exported_at": datetime.now(ZoneInfo(os.environ.get("LBG_LOCAL_TIMEZONE", "Europe/Paris"))).isoformat(timespec="seconds"),
        "exported_by": sess.get("actor") or "agent",
        "pois": pois_export,
        "npc_slots": npc_export,
    }
    for poi_out in (
        content / "world_poi/scrapaltai.json",
        content / "world_poi/tatooine.json",
    ):
        poi_out.parent.mkdir(parents=True, exist_ok=True)
        poi_out.write_text(
            json.dumps(export_doc, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    mirror = bin_dir / "ia_bridge/core3_npc_catalog.json"
    if mirror.parent.is_dir():
        mirror.write_text(catalog_path.read_text(encoding="utf-8"), encoding="utf-8")

    print(f"merge_ok rosters_updated={n} npc_slots={len(npc_slots)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
