extends Node
## Cache client — entités, session, cible PNJ.

var player_id: String = ""
var local_player_name: String = ""
var session_token: String = ""
var planet_id: String = ""
var zone_id: String = ""
var entities: Dictionary = {}  # id -> Dictionary snapshot
var target_npc_id: String = ""
var _npc_reply_by_trace: Dictionary = {}
## Origine affichage Prime (coords SWG → repère client autour du spawn).
var display_origin: Vector3 = Vector3.ZERO

func normalize_entity(ent: Dictionary) -> Dictionary:
	var e := ent.duplicate()
	e["id"] = str(e.get("id", e.get("pilot_id", "")))
	if not e.has("x"):
		var pos: Variant = e.get("pos", null)
		if pos is Array and pos.size() >= 3:
			e["x"] = float(pos[0])
			e["y"] = float(pos[1])
			e["z"] = float(pos[2])
	return e

func set_display_origin_from_spawn(spawn: Array) -> void:
	if spawn.size() >= 3:
		display_origin = Vector3(float(spawn[0]), float(spawn[1]), float(spawn[2]))

func display_position(ent: Dictionary) -> Vector3:
	return to_display_position(Vector3(
		float(ent.get("x", 0)),
		float(ent.get("y", 0)),
		float(ent.get("z", 0)),
	))

func to_display_position(server: Vector3) -> Vector3:
	if display_origin == Vector3.ZERO:
		return server
	return server - display_origin

func to_server_position(display: Vector3) -> Vector3:
	if display_origin == Vector3.ZERO:
		return display
	return display + display_origin

func reset() -> void:
	player_id = ""
	local_player_name = ""
	session_token = ""
	planet_id = ""
	zone_id = ""
	entities.clear()
	target_npc_id = ""
	_npc_reply_by_trace.clear()
	display_origin = Vector3.ZERO

func apply_welcome(msg: Dictionary) -> void:
	if msg.has("player_id"):
		player_id = str(msg.player_id)
	if msg.has("session_token"):
		session_token = str(msg.session_token)
	if msg.has("planet_id"):
		planet_id = str(msg.planet_id)
	if msg.has("zone"):
		zone_id = str(msg.zone)
	if msg.has("map"):
		zone_id = str(msg.map)
	if msg.has("spawn_pos") and msg.spawn_pos is Array:
		set_display_origin_from_spawn(msg.spawn_pos)
	if msg.has("entities") and msg.entities is Array:
		merge_entities(msg.entities)
	_pick_default_npc_target()

func merge_entities(list: Array) -> void:
	if list.is_empty():
		return
	var incoming: Dictionary = {}
	for ent in list:
		if typeof(ent) != TYPE_DICTIONARY:
			continue
		var e: Dictionary = normalize_entity(ent)
		if str(e.get("id", "")).is_empty():
			continue
		var eid := str(e.id)
		# Fantômes : anciennes sessions même pseudo (reconnexion sans resume_token)
		if str(e.get("kind", "")) == "player" and eid != player_id and not local_player_name.is_empty():
			if str(e.get("name", "")) == local_player_name:
				continue
		incoming[eid] = e
	# Snapshot autoritatif : retirer ce qui n'est plus dans le tick
	for eid in entities.keys():
		if not incoming.has(eid):
			entities.erase(eid)
	for eid in incoming:
		entities[eid] = incoming[eid]
	if target_npc_id.is_empty() or not entities.has(target_npc_id):
		_pick_default_npc_target()

func _pick_default_npc_target() -> void:
	for eid in entities:
		var ent: Dictionary = entities[eid]
		if str(ent.get("kind", "")) == "npc":
			var role := str(ent.get("role", ""))
			if role not in ["mob", "monster"]:
				target_npc_id = eid
				return

func cycle_npc_target(step: int = 1) -> void:
	var npc_ids: Array[String] = []
	for eid in entities:
		var ent: Dictionary = entities[eid]
		if str(ent.get("kind", "")) != "npc":
			continue
		if str(ent.get("role", "")) in ["mob", "monster"]:
			continue
		npc_ids.append(eid)
	npc_ids.sort()
	if npc_ids.is_empty():
		target_npc_id = ""
		return
	var idx := npc_ids.find(target_npc_id)
	if idx < 0:
		target_npc_id = npc_ids[0]
		return
	target_npc_id = npc_ids[(idx + step) % npc_ids.size()]

func target_npc_snapshot() -> Dictionary:
	if target_npc_id.is_empty():
		return {}
	return entities.get(target_npc_id, {})

func track_npc_reply(trace_id: String, text: String, is_final: bool) -> String:
	if trace_id.is_empty():
		return text
	var prev: Dictionary = _npc_reply_by_trace.get(trace_id, {})
	if is_final or not prev.has("text"):
		_npc_reply_by_trace[trace_id] = {"text": text, "final": is_final}
		return text
	return str(prev.get("text", text))

func local_player_snapshot() -> Dictionary:
	if player_id.is_empty():
		return {}
	return entities.get(player_id, {})
