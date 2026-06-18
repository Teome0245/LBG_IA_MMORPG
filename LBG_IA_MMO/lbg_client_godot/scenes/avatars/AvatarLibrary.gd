extends Node
## Résolution visuel entité → scène GLB ou placeholder (manifest.json).

const MANIFEST_PATH := "res://assets/avatars/manifest.json"
const PLACEHOLDER_PATH := "res://scenes/avatars/PlaceholderHumanoid.tscn"

var _manifest: Dictionary = {}


func _ready() -> void:
	_reload()


func _reload() -> void:
	_manifest = {}
	if not FileAccess.file_exists(MANIFEST_PATH):
		return
	var txt := FileAccess.get_file_as_string(MANIFEST_PATH)
	var data: Variant = JSON.parse_string(txt)
	if data is Dictionary:
		_manifest = data


func resolve_visual_path(ent: Dictionary) -> String:
	var candidates: Array[String] = []
	var species := str(ent.get("species", "")).strip_edges()
	if not species.is_empty():
		candidates.append(_map_lookup("species", species))
	var mobile := str(ent.get("mobile_template", "")).strip_edges()
	if mobile.is_empty():
		mobile = _binding_mobile(ent)
	if not mobile.is_empty():
		candidates.append(_map_lookup("mobile_template", mobile))
	var pid := str(ent.get("pilot_id", ent.get("id", ""))).strip_edges()
	if pid.begins_with("npc:"):
		candidates.append(_map_lookup("pilot_id", pid))
	candidates.append(str(_manifest.get("default_visual", PLACEHOLDER_PATH)))
	for path in candidates:
		if path.is_empty():
			continue
		if ResourceLoader.exists(path):
			return path
	if ResourceLoader.exists(PLACEHOLDER_PATH):
		return PLACEHOLDER_PATH
	return ""


func _map_lookup(section: String, key: String) -> String:
	var block: Variant = _manifest.get(section)
	if block is Dictionary:
		return str(block.get(key, "")).strip_edges()
	return ""


func _binding_mobile(ent: Dictionary) -> String:
	var binding: Variant = ent.get("binding")
	if binding is Dictionary:
		return str(binding.get("mobile_template", "")).strip_edges()
	return ""
