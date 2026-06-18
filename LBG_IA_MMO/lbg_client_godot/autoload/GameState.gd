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
## Fil de chat par PNJ (évite le mélange au Tab).
var chat_threads: Dictionary = {}  # npc_id -> Array[{from, text}]
var chat_session_lines: Array = []  # SYS globaux (connexion, aide)
## Origine affichage Prime (coords SWG → repère client autour du spawn).
var display_origin: Vector3 = Vector3.ZERO
## Filtre de visibilité (World → _entity_visible_near_player) : ciblage = capsules affichées.
var _entity_visible_fn: Callable = Callable()
const CANTINA_CELL: int = 1082877
const _CantinaInterior := preload("res://scenes/world/CantinaInterior.gd")

func normalize_entity(ent: Dictionary) -> Dictionary:
	var e := ent.duplicate()
	e["id"] = str(e.get("id", e.get("pilot_id", "")))
	if e.has("source"):
		e["source"] = str(e.get("source", ""))
	if not e.has("x"):
		var pos: Variant = e.get("pos", null)
		if pos is Array and pos.size() >= 3:
			e["x"] = float(pos[0])
			e["y"] = float(pos[1])
			e["z"] = float(pos[2])
	if not e.has("local_pos") and e.has("local_x"):
		e["local_pos"] = [float(e.local_x), float(e.local_y), float(e.local_z)]
	return e

func bind_entity_visibility(fn: Callable) -> void:
	_entity_visible_fn = fn

func entity_is_visible(ent: Dictionary) -> bool:
	if _entity_visible_fn.is_valid():
		return bool(_entity_visible_fn.call(ent))
	return true

func set_display_origin_from_spawn(spawn: Array) -> void:
	if spawn.size() >= 3:
		display_origin = Vector3(float(spawn[0]), float(spawn[1]), float(spawn[2]))

func _lbgemu_ent_ready(ent: Dictionary) -> bool:
	if ent.is_empty() or str(ent.get("source", "")) != "core3":
		return false
	if int(ent.get("cell", 0)) == CANTINA_CELL and (_has_interior_local(ent) or ent.has("local_x")):
		return true
	var p := server_position(ent)
	return absf(p.x) > 200.0 or absf(p.z) > 200.0

## Joueur lbgemu suivi en Prime — priorité Teome si snapshot valide.
func tracked_lbgemu_player_id() -> String:
	for key in ["player:Teome", "player:Lia", "player:Nix"]:
		var ent: Dictionary = entities.get(key, {})
		if _lbgemu_ent_ready(ent):
			return key
	return ""

func server_position(ent: Dictionary) -> Vector3:
	return Vector3(
		float(ent.get("x", 0)),
		float(ent.get("y", 0)),
		float(ent.get("z", 0)),
	)

func _interior_local_godot(ent: Dictionary) -> Vector3:
	var lp: Variant = ent.get("local_pos")
	if lp is Array and lp.size() >= 3:
		return _CantinaInterior.swg_local_to_godot(
			float(lp[0]),
			float(lp[1]),
			float(lp[2]),
		)
	return Vector3.ZERO

func _has_interior_local(ent: Dictionary) -> bool:
	return ent.has("local_pos") and ent.get("local_pos") is Array

func display_position(ent: Dictionary) -> Vector3:
	var obs_key := tracked_lbgemu_player_id()
	if not obs_key.is_empty():
		var obs: Dictionary = entities.get(obs_key, {})
		if int(ent.get("cell", 0)) == CANTINA_CELL and int(obs.get("cell", 0)) == CANTINA_CELL:
			if _has_interior_local(ent) and _has_interior_local(obs):
				return _interior_local_godot(ent) - _interior_local_godot(obs)
			return server_position(ent) - server_position(obs)
	return to_display_position(server_position(ent))

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
	chat_threads.clear()
	chat_session_lines.clear()
	display_origin = Vector3.ZERO

func append_chat_line(npc_id: String, from_name: String, text: String) -> void:
	var line := {"from": from_name, "text": text}
	if npc_id.is_empty():
		chat_session_lines.append(line)
		return
	if not chat_threads.has(npc_id):
		chat_threads[npc_id] = []
	(chat_threads[npc_id] as Array).append(line)

func chat_lines_for(npc_id: String) -> Array:
	var out: Array = []
	for line in chat_session_lines:
		out.append(line)
	if npc_id.is_empty():
		return out
	if chat_threads.has(npc_id):
		for line in chat_threads[npc_id]:
			out.append(line)
	return out

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
		# Fantômes gateway (même pseudo) — pas les joueurs lbgemu (source core3)
		if str(e.get("kind", "")) == "player" and eid != player_id and not local_player_name.is_empty():
			if str(e.get("source", "")) != "core3" and str(e.get("name", "")) == local_player_name:
				continue
		incoming[eid] = e
	# Snapshot autoritatif : retirer ce qui n'est plus dans le tick
	for eid in entities.keys():
		if not incoming.has(eid):
			entities.erase(eid)
	for eid in incoming:
		entities[eid] = incoming[eid]
	ensure_target_visible()

func is_targetable_npc(ent: Dictionary) -> bool:
	if str(ent.get("kind", "")) != "npc":
		return false
	if str(ent.get("role", "")) in ["mob", "monster"]:
		return false
	return entity_is_visible(ent)

func _targetable_npc_ids(
	local_display: Vector3 = Vector3.ZERO,
	radius: float = -1.0,
) -> Array[String]:
	var npc_ids: Array[String] = []
	var use_radius := radius >= 0.0
	for eid in entities:
		var ent: Dictionary = entities[eid]
		if not is_targetable_npc(ent):
			continue
		if use_radius:
			var p := display_position(ent)
			if Vector2(p.x - local_display.x, p.z - local_display.z).length() > radius:
				continue
		npc_ids.append(eid)
	npc_ids.sort()
	return npc_ids

func ensure_target_visible() -> void:
	if target_npc_id.is_empty():
		_pick_default_npc_target()
		return
	var ent: Dictionary = entities.get(target_npc_id, {})
	if ent.is_empty() or not is_targetable_npc(ent):
		_pick_default_npc_target()

func _pick_default_npc_target() -> void:
	var best_id := ""
	var best_d := INF
	for eid in _targetable_npc_ids():
		var p := display_position(entities[eid])
		var d := Vector2(p.x, p.z).length()
		if d < best_d:
			best_d = d
			best_id = eid
	target_npc_id = best_id

func cycle_npc_target(step: int = 1) -> void:
	var npc_ids := _targetable_npc_ids()
	if npc_ids.is_empty():
		target_npc_id = ""
		return
	var idx := npc_ids.find(target_npc_id)
	if idx < 0:
		target_npc_id = npc_ids[0]
		return
	target_npc_id = npc_ids[(idx + step) % npc_ids.size()]

func cycle_npc_target_near(local_display: Vector3, radius: float, step: int = 1) -> void:
	var npc_ids := _targetable_npc_ids(local_display, radius)
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
