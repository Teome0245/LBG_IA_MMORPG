extends Node3D

const ENTITY_SCENE_PATH := "res://scenes/EntityView.tscn"
var _entity_scene: PackedScene
const MOVE_SPEED := 7.0
const MOVE_SEND_INTERVAL := 0.12
const MOVE_MIN_DIST := 0.35
const CAM_DIST_MIN := 4.0
const CAM_DIST_MAX := 55.0
const CAM_PITCH_MIN := -1.1
const CAM_PITCH_MAX := -0.15
const NPC_PICK_RADIUS := 5.0
const GROUND_PLANE_Y := 0.0
## Prime : coords SWG étalées — n’afficher que les PNJ proches du joueur.
const PRIME_NPC_VIEW_RADIUS := 55.0
const PRIME_ZONE_PLAYER_RADIUS := 250.0

@onready var _entities_root: Node3D = $Entities
@onready var _camera: Camera3D = $Camera3D
@onready var _hud: Label = $CanvasLayer/HUD
@onready var _target_label: Label = $CanvasLayer/TargetLabel
@onready var _chat_panel: Control = $CanvasLayer/ChatPanel
@onready var _chat_log: RichTextLabel = $CanvasLayer/ChatPanel/ChatLog
@onready var _chat_input: LineEdit = $CanvasLayer/ChatPanel/ChatInput

var _views: Dictionary = {}
var _move_cooldown := 0.0
var _last_sent_pos := Vector3.ZERO
var _local_pos := Vector3.ZERO
var _has_local := false
var _cam_yaw := -0.6
var _cam_pitch := -0.45
var _cam_dist := 14.0
var _predict_local := false
var _rmb_drag := false
var _last_mouse := Vector2.ZERO
var _click_dest: Vector3 = Vector3.ZERO
var _has_click_dest := false
@onready var _click_marker: MeshInstance3D = $ClickMarker
@onready var _ground: MeshInstance3D = $Ground
@onready var _cantina: Node3D = $CantinaInterior

func _ready() -> void:
	add_to_group("world")
	GameState.bind_entity_visibility(_entity_visible_near_player)
	_entity_scene = load(ENTITY_SCENE_PATH) as PackedScene
	if _entity_scene == null:
		push_error("EntityView.tscn non chargé")
		_append_chat("ERR", "Capsules PNJ non chargées (EntityView.tscn)")
	Network.message_received.connect(_on_message)
	Network.disconnected.connect(_on_disconnected)
	_refresh_all_entities()
	_update_world_shell()
	_update_camera(0.0)
	_chat_input.text_submitted.connect(_on_chat_submitted)
	_chat_input.placeholder_text = "Parler au PNJ (Entrée) — Tab = cible"
	_update_hud()
	_click_marker.visible = false
	_set_ui_mouse_passthrough()
	var mode_hint := "Prime: PNJ proches visibles" if Config.server_mode == Config.ServerMode.PRIME else "Terre1"
	GameState.append_chat_line("", "SYS", "%s | Clic sol | Tab/T cible | ZQSD" % mode_hint)
	_refresh_chat_panel()

func _on_disconnected() -> void:
	GameState.append_chat_line("", "SYS", "Déconnecté — retour écran connexion")
	get_tree().change_scene_to_file("res://scenes/Login.tscn")

func _uses_cantina_shell() -> bool:
	if Config.server_mode != Config.ServerMode.PRIME:
		return false
	if _player_in_cantina_cell():
		return true
	for eid in GameState.entities:
		var ent: Dictionary = GameState.entities[eid]
		if int(ent.get("cell", 0)) == GameState.CANTINA_CELL:
			return true
	return false


func _player_in_cantina_cell() -> bool:
	var key := GameState.tracked_lbgemu_player_id()
	if key.is_empty():
		return false
	var ent: Dictionary = GameState.entities.get(key, {})
	return int(ent.get("cell", 0)) == GameState.CANTINA_CELL


func _update_world_shell() -> void:
	var cantina_on := _uses_cantina_shell()
	if _cantina != null:
		_cantina.visible = cantina_on
	if _ground != null:
		_ground.visible = not cantina_on
	if cantina_on:
		_cam_dist = clampf(_cam_dist, 6.0, 24.0)


func _prime_observer_active() -> bool:
	return Config.server_mode == Config.ServerMode.PRIME and not GameState.tracked_lbgemu_player_id().is_empty()

func _sync_prime_observer_anchor() -> void:
	if not _prime_observer_active():
		return
	var key := GameState.tracked_lbgemu_player_id()
	var ent: Dictionary = GameState.entities.get(key, {})
	if ent.is_empty():
		return
	# Cantina : repère relatif à l'observateur (évite double soustraction sur les PNJ)
	if int(ent.get("cell", 0)) == GameState.CANTINA_CELL:
		GameState.display_origin = Vector3.ZERO
	else:
		GameState.display_origin = GameState.server_position(ent)
	_local_pos = Vector3.ZERO
	_has_local = true
	_predict_local = false

func _entity_visible_near_player(ent: Dictionary) -> bool:
	if Config.server_mode != Config.ServerMode.PRIME:
		return true
	var kind := str(ent.get("kind", ""))
	if kind == "player":
		if str(ent.get("id", "")) == GameState.player_id:
			return true
		if str(ent.get("source", "")) == "core3" or str(ent.get("id", "")).begins_with("player:"):
			if _uses_cantina_shell():
				return int(ent.get("cell", 0)) == GameState.CANTINA_CELL
			if not _has_local:
				return true
			var zp := GameState.display_position(ent)
			var dist_xz := Vector2(zp.x - _local_pos.x, zp.z - _local_pos.z).length()
			if int(ent.get("cell", 0)) == GameState.CANTINA_CELL:
				return true
			return dist_xz <= PRIME_ZONE_PLAYER_RADIUS
		return false
	if kind == "npc" and _uses_cantina_shell():
		return int(ent.get("cell", 0)) == GameState.CANTINA_CELL
	if not _has_local:
		return true
	var p := GameState.display_position(ent)
	return Vector2(p.x - _local_pos.x, p.z - _local_pos.z).length() <= PRIME_NPC_VIEW_RADIUS

func _set_ui_mouse_passthrough() -> void:
	# Les labels du HUD ne doivent pas avaler les clics sur tout l'écran.
	for node in [_hud, _target_label, _chat_log]:
		if node is Control:
			node.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_chat_panel.mouse_filter = Control.MOUSE_FILTER_PASS
	_chat_input.mouse_filter = Control.MOUSE_FILTER_STOP

func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT:
		_rmb_drag = false

func _physics_process(delta: float) -> void:
	if not Network.is_ws_open():
		return
	# Clavier : seulement bloqué si le champ chat a le focus
	if _chat_input.has_focus():
		_update_camera(0.0)
		return
	if _prime_observer_active():
		_move_cooldown = maxf(_move_cooldown - delta, 0.0)
		_update_camera(0.0)
		return
	if _rmb_drag:
		_update_camera(0.0)
	# Déplacement clic souris vers _click_dest
	if _has_click_dest:
		var to := _click_dest - _local_pos
		to.y = 0.0
		if to.length() < 0.45:
			_has_click_dest = false
			_click_marker.visible = false
		else:
			var step := MOVE_SPEED * delta
			_local_pos += to.normalized() * minf(step, to.length())
			_has_local = true
			_predict_local = true
			_move_cooldown -= delta
			if _move_cooldown <= 0.0 and _local_pos.distance_to(_last_sent_pos) >= MOVE_MIN_DIST:
				_move_cooldown = MOVE_SEND_INTERVAL
				_last_sent_pos = _local_pos
				_send_move_to_server()
				_sync_local_view()
			_update_camera(0.0)
			return
	var dir := Vector3.ZERO
	if Input.is_action_pressed("move_forward"):
		dir.z -= 1.0
	if Input.is_action_pressed("move_back"):
		dir.z += 1.0
	if Input.is_action_pressed("move_left"):
		dir.x -= 1.0
	if Input.is_action_pressed("move_right"):
		dir.x += 1.0
	if dir.length_squared() > 0.001:
		dir = dir.normalized()
		_local_pos += dir * MOVE_SPEED * delta
		_has_local = true
		_predict_local = true
		_move_cooldown -= delta
		if _move_cooldown <= 0.0 and _local_pos.distance_to(_last_sent_pos) >= MOVE_MIN_DIST:
			_move_cooldown = MOVE_SEND_INTERVAL
			_last_sent_pos = _local_pos
			_send_move_to_server()
			_sync_local_view()
	if not _chat_input.has_focus() and Input.is_action_just_pressed("cycle_target"):
		_cycle_target()
	_update_camera(delta)

func _send_move_to_server() -> void:
	var srv := GameState.to_server_position(_local_pos)
	Network.send_move(srv.x, srv.y, srv.z)

func _cycle_target() -> void:
	if Config.server_mode == Config.ServerMode.PRIME and _has_local:
		GameState.cycle_npc_target_near(_local_pos, PRIME_NPC_VIEW_RADIUS, 1)
	else:
		GameState.cycle_npc_target(1)
	_refresh_target_highlight()
	_update_hud()
	_refresh_chat_panel()
	var tgt := GameState.target_npc_snapshot()
	if not tgt.is_empty():
		var nm := str(tgt.get("name", GameState.target_npc_id))
		GameState.append_chat_line(
			GameState.target_npc_id,
			"SYS",
			"— Dialogue avec %s —" % nm,
		)
		_refresh_chat_panel()

func _mouse_screen_pos(event: InputEvent) -> Vector2:
	if event is InputEventMouse:
		return (event as InputEventMouse).position
	return Vector2.ZERO

func _is_mouse_over_chat_ui(screen_pos: Vector2) -> bool:
	if _chat_panel == null:
		return false
	var rect := _chat_panel.get_global_rect()
	if rect.size.x < 1.0 or rect.size.y < 1.0:
		return false
	return rect.has_point(screen_pos)

func _ray_hit_ground(screen_pos: Vector2) -> Vector3:
	var ray_o := _camera.project_ray_origin(screen_pos)
	var ray_d := _camera.project_ray_normal(screen_pos)
	var space := get_world_3d().direct_space_state
	var query := PhysicsRayQueryParameters3D.create(ray_o, ray_o + ray_d * 200.0)
	query.collide_with_areas = false
	var hit := space.intersect_ray(query)
	if not hit.is_empty():
		return hit.position
	var plane_y := _local_pos.y if _has_local else GROUND_PLANE_Y
	if absf(ray_d.y) < 0.0001:
		return Vector3.ZERO
	var t := (plane_y - ray_o.y) / ray_d.y
	if t < 0.0:
		return Vector3.ZERO
	return ray_o + ray_d * t

func _pick_npc_at_screen(screen_pos: Vector2) -> String:
	var hit := _ray_hit_ground(screen_pos)
	if not _has_local:
		return ""
	var best_id := ""
	var best_d := NPC_PICK_RADIUS
	for eid in _views:
		if not GameState.entities.has(eid):
			continue
		var ent: Dictionary = GameState.entities[eid]
		if not GameState.is_targetable_npc(ent):
			continue
		var ep := GameState.display_position(ent)
		var d := Vector2(hit.x - ep.x, hit.z - ep.z).length()
		if d < best_d:
			best_d = d
			best_id = eid
	return best_id

func _input(event: InputEvent) -> void:
	if event is InputEventMouse:
		var mpos := _mouse_screen_pos(event)
		if _is_mouse_over_chat_ui(mpos) and not _rmb_drag:
			return
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_RIGHT:
			if mb.pressed and not _chat_input.has_focus():
				_rmb_drag = true
				_last_mouse = mb.position
			else:
				_rmb_drag = false
			return
		if mb.button_index == MOUSE_BUTTON_WHEEL_UP and mb.pressed:
			_cam_dist = clampf(_cam_dist - 2.0, CAM_DIST_MIN, CAM_DIST_MAX)
			return
		if mb.button_index == MOUSE_BUTTON_WHEEL_DOWN and mb.pressed:
			_cam_dist = clampf(_cam_dist + 2.0, CAM_DIST_MIN, CAM_DIST_MAX)
			return
		if mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT and not _chat_input.has_focus():
			var picked := _pick_npc_at_screen(mb.position)
			if not picked.is_empty():
				GameState.target_npc_id = picked
				_refresh_target_highlight()
				_update_hud()
				var tgt := GameState.target_npc_snapshot()
				GameState.append_chat_line(picked, "SYS", "— Dialogue avec %s —" % str(tgt.get("name", picked)))
				_refresh_chat_panel()
			else:
				var dest := _ray_hit_ground(mb.position)
				if dest != Vector3.ZERO:
					_click_dest = Vector3(dest.x, _local_pos.y, dest.z)
					_has_click_dest = true
					_click_marker.global_position = _click_dest + Vector3(0, 0.05, 0)
					_click_marker.visible = true
			return
	if event is InputEventMouseMotion and _rmb_drag:
		var mm := event as InputEventMouseMotion
		var delta := mm.position - _last_mouse
		_last_mouse = mm.position
		_cam_yaw -= delta.x * 0.005
		_cam_pitch = clampf(_cam_pitch - delta.y * 0.004, CAM_PITCH_MIN, CAM_PITCH_MAX)
		return

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_ESCAPE:
			if _chat_input.has_focus():
				_chat_input.release_focus()
			else:
				_has_click_dest = false
				_click_marker.visible = false
			get_viewport().set_input_as_handled()
			return
	if _chat_input.has_focus():
		return
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_T:
			_cycle_target()
			get_viewport().set_input_as_handled()
		elif event.keycode == KEY_Q:
			_cam_yaw -= 0.12
		elif event.keycode == KEY_E and not event.shift_pressed:
			_cam_yaw += 0.12

func _on_message(msg: Dictionary) -> void:
	var t: String = str(msg.get("type", ""))
	match t:
		"world_tick":
			if msg.has("entities"):
				GameState.merge_entities(msg.entities)
			_refresh_all_entities()
			_handle_npc_reply(msg)
		"welcome":
			GameState.apply_welcome(msg)
			if msg.has("spawn_pos"):
				var sp: Array = msg.spawn_pos
				if sp.size() >= 3:
					_local_pos = GameState.display_position({
						"x": sp[0], "y": sp[1], "z": sp[2],
					})
					_last_sent_pos = _local_pos
					_has_local = true
					_predict_local = false
			_refresh_all_entities()
			_refresh_chat_panel()
		"error":
			var m := str(msg.get("message", msg))
			if not m.contains("rate_limited"):
				GameState.append_chat_line(GameState.target_npc_id, "ERR", m)
				_refresh_chat_panel()

func _handle_npc_reply(msg: Dictionary) -> void:
	var rep := str(msg.get("npc_reply", "")).strip_edges()
	if rep.is_empty():
		return
	var tid := str(msg.get("trace_id", ""))
	var is_final := not rep.begins_with("[…]") and not rep.begins_with("…")
	var shown := GameState.track_npc_reply(tid, rep, is_final)
	var tgt := GameState.target_npc_snapshot()
	var speaker := str(tgt.get("name", "PNJ"))
	var nid := GameState.target_npc_id
	if msg.has("from"):
		var from_id := str(msg.get("from", ""))
		if from_id.begins_with("npc:"):
			nid = from_id
	GameState.append_chat_line(nid, speaker, shown)
	_refresh_chat_panel()

func _refresh_all_entities() -> void:
	if _prime_observer_active():
		_sync_prime_observer_anchor()
	var player_snap := GameState.local_player_snapshot()
	if _prime_observer_active():
		pass
	elif not player_snap.is_empty() and not _predict_local:
		_local_pos = GameState.display_position(player_snap)
		_has_local = true
	elif not player_snap.is_empty() and _views.has(GameState.player_id):
		# Resync doux si le serveur nous a téléporté loin
		var disp := GameState.display_position(player_snap)
		var sx := disp.x
		var sz := disp.z
		if Vector2(_local_pos.x - sx, _local_pos.z - sz).length() > 4.0:
			_local_pos = disp
			_predict_local = false
	for eid in GameState.entities:
		var ent: Dictionary = GameState.entities[eid]
		# Joueur local Godot (id 1) + joueurs zone Core3 (lbgemu) en lecture seule
		if str(ent.get("kind", "")) == "player":
			if eid == GameState.player_id and _prime_observer_active():
				continue
			var is_core3: bool = str(ent.get("source", "")) == "core3" or str(eid).begins_with("player:")
			if eid != GameState.player_id and not is_core3:
				continue
		if not _entity_visible_near_player(ent):
			if _views.has(eid):
				_views[eid].queue_free()
				_views.erase(eid)
			continue
		if not _views.has(eid):
			if _entity_scene == null:
				continue
			var node: Node3D = _entity_scene.instantiate()
			_entities_root.add_child(node)
			node.call("setup", ent)
			_views[eid] = node
		else:
			_views[eid].call("update_from_snapshot", ent)
	_sync_local_view()
	_update_world_shell()
	GameState.ensure_target_visible()
	_refresh_target_highlight()
	_update_hud()
	for eid in _views.keys():
		if not GameState.entities.has(eid):
			_views[eid].queue_free()
			_views.erase(eid)

func _refresh_target_highlight() -> void:
	for eid in _views:
		_views[eid].call("set_targeted", eid == GameState.target_npc_id)

func _sync_local_view() -> void:
	if _prime_observer_active():
		var obs := GameState.tracked_lbgemu_player_id()
		if not obs.is_empty() and _views.has(obs):
			_views[obs].global_position = _local_pos
		return
	if GameState.player_id.is_empty():
		return
	if _views.has(GameState.player_id):
		_views[GameState.player_id].global_position = _local_pos

func _update_camera(_delta: float) -> void:
	if not _has_local:
		return
	var look_at := _local_pos + Vector3(0, 1.2, 0)
	var offset := Vector3(
		cos(_cam_pitch) * sin(_cam_yaw) * _cam_dist,
		-sin(_cam_pitch) * _cam_dist,
		cos(_cam_pitch) * cos(_cam_yaw) * _cam_dist,
	)
	_camera.global_position = look_at + offset
	_camera.look_at(look_at, Vector3.UP)

func _update_hud() -> void:
	var tgt := GameState.target_npc_snapshot()
	var tgt_name := str(tgt.get("name", "—"))
	var mode_extra := ""
	if _prime_observer_active():
		mode_extra = " | observateur lbgemu"
	_hud.text = "LBG — %s | %s | entités: %d%s | %s" % [
		GameState.planet_id if not GameState.planet_id.is_empty() else GameState.zone_id,
		Config.mode_label(),
		GameState.entities.size(),
		mode_extra,
		Config.ws_url(),
	]
	var near_n := _count_nearby_npcs()
	var zone_p := _zone_players_online()
	var zone_txt := ""
	if zone_p.size() > 0:
		zone_txt = " | zone: " + ", ".join(zone_p)
	var obs := ""
	if _prime_observer_active():
		obs = " | obs: %s (lbgemu)" % GameState.tracked_lbgemu_player_id().trim_prefix("player:")
	_target_label.text = "Cible: %s (%s) | PNJ: %d%s%s" % [tgt_name, GameState.target_npc_id, near_n, zone_txt, obs]

func _count_nearby_npcs() -> int:
	var n := 0
	for eid in GameState.entities:
		var ent: Dictionary = GameState.entities[eid]
		if str(ent.get("kind", "")) != "npc":
			continue
		if _entity_visible_near_player(ent):
			n += 1
	return n

func _zone_players_online() -> PackedStringArray:
	# Joueurs lbgemu visibles (capsules turquoise)
	var names: PackedStringArray = []
	for eid in GameState.entities:
		var ent: Dictionary = GameState.entities[eid]
		if str(ent.get("kind", "")) == "player" and str(ent.get("source", "")) == "core3":
			names.append(str(ent.get("name", eid)))
	return names

func _append_chat(from: String, text: String) -> void:
	GameState.append_chat_line(GameState.target_npc_id, from, text)
	_refresh_chat_panel()

func _refresh_chat_panel() -> void:
	_chat_log.clear()
	for line in GameState.chat_lines_for(GameState.target_npc_id):
		if typeof(line) != TYPE_DICTIONARY:
			continue
		var d: Dictionary = line
		var from_n := str(d.get("from", "?"))
		var txt := str(d.get("text", ""))
		var col := "#aaccff"
		if from_n == "Moi":
			col = "#ffe0a0"
		elif from_n == "SYS":
			col = "#88aa88"
		elif from_n == "ERR":
			col = "#ff8888"
		_chat_log.append_text("[color=%s]%s[/color]: %s\n" % [col, from_n, txt])

func _on_chat_submitted(text: String) -> void:
	var msg := text.strip_edges()
	_chat_input.clear()
	_chat_input.release_focus()
	if msg.is_empty():
		return
	var tgt := GameState.target_npc_snapshot()
	if tgt.is_empty():
		_append_chat("SYS", "Tab pour choisir un PNJ civil")
		return
	var npc_id := GameState.target_npc_id
	var npc_name := str(tgt.get("name", "PNJ"))
	GameState.append_chat_line(npc_id, "Moi", msg)
	_refresh_chat_panel()
	var srv := GameState.to_server_position(_local_pos)
	Network.send_npc_dialogue(srv.x, srv.y, srv.z, npc_id, npc_name, msg)
