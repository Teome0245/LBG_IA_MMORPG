extends Node
## WebSocket JSON — mmmorpg-ws/1 et lbg-ws/1 (gateway Prime).

signal connected
signal disconnected
signal message_received(msg: Dictionary)
signal connection_failed(reason: String)
signal prime_session_ready

var _ws: WebSocketPeer = WebSocketPeer.new()
var _state: int = WebSocketPeer.STATE_CLOSED
var _player_name: String = ""
var _session_token: String = ""
var _prime_logged_in := false
var _prime_character_id := 0

func is_ws_open() -> bool:
	return _state == WebSocketPeer.STATE_OPEN

func connect_with_player(player_name: String, resume_token: String = "") -> Error:
	_player_name = player_name.strip_edges()
	GameState.local_player_name = _player_name
	if _player_name.is_empty():
		connection_failed.emit("Nom joueur vide")
		return ERR_INVALID_PARAMETER
	_session_token = resume_token
	_prime_logged_in = false
	_prime_character_id = 0
	if _state != WebSocketPeer.STATE_CLOSED:
		_ws.close()
		_poll()
	_ws = WebSocketPeer.new()
	_state = WebSocketPeer.STATE_CLOSED
	var err := _ws.connect_to_url(Config.ws_url())
	if err != OK:
		connection_failed.emit("connect_to_url: %s" % error_string(err))
		return err
	return OK

func disconnect_from_server() -> void:
	if _state != WebSocketPeer.STATE_CLOSED:
		_ws.close()
	_poll()

func send_message(msg: Dictionary) -> void:
	if not is_ws_open():
		return
	_ws.send_text(JSON.stringify(msg))

func send_hello() -> void:
	if Config.server_mode == Config.ServerMode.PRIME:
		send_message({
			"type": "login",
			"username": _player_name,
			"password": "lbg_dev",
		})
	else:
		var payload := {
			"type": "hello",
			"player_name": _player_name,
		}
		if not _session_token.is_empty():
			payload["resume_token"] = _session_token
		elif not GameState.session_token.is_empty():
			payload["resume_token"] = GameState.session_token
		send_message(payload)

func send_move(x: float, y: float, z: float) -> void:
	if Config.server_mode == Config.ServerMode.PRIME:
		send_message({
			"type": "move",
			"direction": [x, z],
			"dt": 0.1,
			"pos": [x, y, z],
		})
	else:
		send_message({"type": "move", "x": x, "y": y, "z": z})

func send_npc_dialogue(x: float, y: float, z: float, world_npc_id: String, npc_name: String, text: String) -> void:
	if Config.server_mode == Config.ServerMode.PRIME:
		send_message({
			"type": "interact",
			"target_id": world_npc_id,
			"action": "talk",
			"message": text,
			"pos": [x, y, z],
		})
		return
	send_message({
		"type": "move",
		"x": x,
		"y": y,
		"z": z,
		"world_npc_id": world_npc_id,
		"npc_name": npc_name,
		"text": text,
	})

func _process(_delta: float) -> void:
	_poll()

func _poll() -> void:
	_ws.poll()
	var new_state := _ws.get_ready_state()
	if new_state != _state:
		var was_open := _state == WebSocketPeer.STATE_OPEN
		_state = new_state
		if not was_open and new_state == WebSocketPeer.STATE_OPEN:
			send_hello()
			connected.emit()
		elif was_open and new_state != WebSocketPeer.STATE_OPEN:
			disconnected.emit()
	if not is_ws_open():
		return
	while _ws.get_available_packet_count() > 0:
		var packet := _ws.get_packet()
		var raw := packet.get_string_from_utf8()
		_parse_incoming(raw)

func _parse_incoming(raw: String) -> void:
	var parser := JSON.new()
	if parser.parse(raw) != OK:
		push_warning("JSON invalide: %s" % raw.substr(0, 120))
		return
	var data = parser.data
	if typeof(data) != TYPE_DICTIONARY:
		return
	if Config.server_mode == Config.ServerMode.PRIME and _dispatch_prime(data):
		return
	message_received.emit(data)

func _dispatch_prime(data: Dictionary) -> bool:
	var t: String = str(data.get("type", ""))
	match t:
		"login_result":
			if data.get("success", false):
				_prime_logged_in = true
				send_message({"type": "get_characters"})
			else:
				connection_failed.emit(str(data.get("reason", "login refused")))
			return true
		"characters_list":
			var chars: Array = data.get("characters", [])
			if chars.is_empty():
				connection_failed.emit("aucun personnage")
				return true
			var c: Dictionary = chars[0]
			_prime_character_id = int(c.get("id", 1))
			send_message({
				"type": "select_character",
				"character_id": _prime_character_id,
			})
			return true
		"enter_world":
			var pos: Array = data.get("position", [0, 0, 0])
			var fake_welcome := {
				"type": "welcome",
				"player_id": "1",
				"planet_id": "tatooine",
				"zone": str(data.get("map", "lbg_prime")),
				"entities": _normalize_prime_entities(data.get("entities", [])),
			}
			if pos.size() >= 3:
				fake_welcome["spawn_pos"] = pos
			message_received.emit(fake_welcome)
			prime_session_ready.emit()
			return true
		"world_state":
			var tick_msg := {
				"type": "world_tick",
				"entities": _normalize_prime_entities(data.get("entities", [])),
			}
			if data.has("chat"):
				var ch: Dictionary = data.chat
				tick_msg["npc_reply"] = str(ch.get("message", ""))
			message_received.emit(tick_msg)
			return true
		"chat":
			message_received.emit({
				"type": "world_tick",
				"npc_reply": str(data.get("message", "")),
				"trace_id": "prime",
			})
			return true
		"error":
			message_received.emit({"type": "error", "message": data.get("message", data)})
			return true
	return false

func _normalize_prime_entities(raw: Variant) -> Array:
	var out: Array = []
	if typeof(raw) != TYPE_ARRAY:
		return out
	for ent in raw:
		if typeof(ent) != TYPE_DICTIONARY:
			continue
		var e: Dictionary = ent
		var pos: Array = e.get("pos", [0, 0, 0])
		var pid := str(e.get("pilot_id", "")).strip_edges()
		var norm := {
			"id": pid if not pid.is_empty() else str(e.get("id", "")),
			"kind": str(e.get("kind", "npc")),
			"name": str(e.get("name", "")),
			"x": float(pos[0]) if pos.size() > 0 else 0.0,
			"y": float(pos[1]) if pos.size() > 1 else 0.0,
			"z": float(pos[2]) if pos.size() > 2 else 0.0,
			"cell": int(e.get("cell", 0)),
		}
		if e.has("source"):
			norm["source"] = str(e.get("source", ""))
		if e.has("role"):
			norm["role"] = str(e.get("role", ""))
		if not pid.is_empty():
			norm["pilot_id"] = pid
		var lp: Variant = e.get("local_pos", null)
		if lp is Array and lp.size() >= 3:
			norm["local_pos"] = [float(lp[0]), float(lp[1]), float(lp[2])]
		out.append(norm)
	return out
