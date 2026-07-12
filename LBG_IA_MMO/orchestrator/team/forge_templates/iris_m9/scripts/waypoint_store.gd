# waypoint_store.gd — Waypoints perso carte planétaire (M9c)
extends RefCounted
class_name WaypointStore

const PATH := "user://waypoints.json"
const FALLBACK_PATH := "res://config/waypoints.json"
const MAX_WAYPOINTS: int = 5

static func load_all() -> Array:
	var path := PATH if FileAccess.file_exists(PATH) else FALLBACK_PATH
	if not FileAccess.file_exists(path):
		return []
	var f := FileAccess.open(path, FileAccess.READ)
	var raw: Variant = JSON.parse_string(f.get_as_text())
	f.close()
	if raw is Dictionary:
		var arr: Variant = (raw as Dictionary).get("waypoints", [])
		return arr if arr is Array else []
	return []

static func save_all(waypoints: Array) -> bool:
	var payload := {
		"schema_version": 1,
		"max_waypoints": MAX_WAYPOINTS,
		"waypoints": waypoints.slice(0, MAX_WAYPOINTS),
	}
	var f := FileAccess.open(PATH, FileAccess.WRITE)
	if f == null:
		push_warning("WaypointStore: impossible d'écrire %s" % PATH)
		return false
	f.store_string(JSON.stringify(payload, "\t"))
	f.close()
	return true

static func add_waypoint(label: String, x: float, z: float) -> Dictionary:
	var wps := load_all()
	if wps.size() >= MAX_WAYPOINTS:
		return {"ok": false, "reason": "max_waypoints"}
	var wp := {
		"id": "wp:%d" % Time.get_ticks_msec(),
		"label": label if label != "" else "Waypoint %d" % (wps.size() + 1),
		"x": x,
		"z": z,
		"created_at": Time.get_datetime_string_from_system(true),
	}
	wps.append(wp)
	save_all(wps)
	return {"ok": true, "waypoint": wp}

static func remove_waypoint(wp_id: String) -> void:
	var wps := load_all()
	var out: Array = []
	for item: Variant in wps:
		if item is Dictionary and str((item as Dictionary).get("id", "")) != wp_id:
			out.append(item)
	save_all(out)
