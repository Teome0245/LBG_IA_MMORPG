# network_bridge.gd — Pont UDP local Python -> Godot (port 12345)
extends Node

const BIND_PORT: int = 12345

@export var entity_manager_path: NodePath = NodePath("../EntityManager")
@export var snapshot_bridge_path: NodePath = NodePath("../SnapshotBridge")
@export var world_map_path:      NodePath = NodePath("../WorldMap")
@export var main_path:           NodePath = NodePath("..")

var _udp:       PacketPeerUDP = PacketPeerUDP.new()
var _em:        EntityManager = null
var _snap:      Node          = null
var _main:      Node          = null
var _active:    bool          = false
var _demo_cleared: bool       = false
var _live_packets: int        = 0

func _ready() -> void:
	_em   = get_node_or_null(entity_manager_path) as EntityManager
	_snap = get_node_or_null(snapshot_bridge_path)
	_main = get_node_or_null(main_path)
	var err: int = _udp.bind(BIND_PORT)
	if err != OK:
		push_warning("NetworkBridge: port %d indisponible (err %d)" % [BIND_PORT, err])
		return
	_active = true
	print("[Bridge] En ecoute UDP :%d (toutes interfaces)" % BIND_PORT)

func _process(_delta: float) -> void:
	if not _active:
		return
	while _udp.get_available_packet_count() > 0:
		var raw: PackedByteArray = _udp.get_packet()
		var text: String         = raw.get_string_from_utf8()
		_dispatch(text)

func _dispatch(text: String) -> void:
	var pkt: Variant = JSON.parse_string(text)
	if not pkt is Dictionary:
		return
	var d: Dictionary = pkt as Dictionary
	_live_packets += 1
	if _snap and _snap.has_method("notify_live_packet"):
		_snap.notify_live_packet()
	var t := str(d.get("t", ""))
	if t == "sp" or t == "mv" or t == "cn":
		_clear_demo_if_needed()
	var oid := _resolve_oid(d)
	match t:
		"mv":
			if _em:
				_em.move(oid, Vector3(float(d.get("x", 0.0)),
						float(d.get("y", 0.0)),
						float(d.get("z", 0.0))))
		"sp":
			if _em:
				_em.spawn(oid, Vector3(float(d.get("x", 0.0)),
						float(d.get("y", 0.0)),
						float(d.get("z", 0.0))),
					_parse_color(str(d.get("c", "npc"))),
					str(d.get("l", "")))
		"dp":
			if _em:
				_em.despawn(oid)
		"zc":
			if _em:
				_em.clear()
			_demo_cleared = true
			if _main and _main.has_method("on_zone_change"):
				_main.on_zone_change()
		# M5 — Joueur connecté : spawn + suivi caméra + clear demo
		"cn":
			if not _demo_cleared and _em:
				_em.clear()
				_demo_cleared = true
			var cn_oid := _resolve_oid(d)
			var x   := float(d.get("x", 0.0))
			var y   := float(d.get("y", 0.0))
			var z   := float(d.get("z", 0.0))
			var pl  := str(d.get("pl", ""))
			if _em and cn_oid != 0:
				_em.spawn(cn_oid, Vector3(x, y, z), Entity.COLOR_PLAYER_OFFICIAL, "YOU")
			var pc: PlayerController = get_node_or_null("../PlayerController") as PlayerController
			if pc and cn_oid != 0:
				pc.set_player_id(cn_oid)
				pc.send_initial_position(x, y, z)
			if _main and _main.has_method("on_player_connected"):
				_main.on_player_connected(cn_oid, pl)
			print("[Bridge] Joueur connecté: 0x%016x  planet=%s  pos=(%.1f,%.1f,%.1f)" % [cn_oid, pl, x, y, z])
		# M5 — Etat locomotion → StateLabel
		"ls":
			if _main and _main.has_method("on_locomotion_state"):
				_main.on_locomotion_state(str(d.get("s", "STANDING")))
		"ws":
			_load_ws_json(str(d.get("path", "")))

func _load_ws_json(path: String) -> void:
	if path == "":
		return
	if path.begins_with("/") or path.contains(":\\"):
		if FileAccess.file_exists(path):
			var src := FileAccess.open(path, FileAccess.READ)
			var cache_path := "res://cache/mos_eisley_ws.json"
			var dst := FileAccess.open(cache_path, FileAccess.WRITE)
			if src and dst:
				dst.store_buffer(src.get_buffer(src.get_length()))
				dst.close()
				src.close()
	var ws: WsObjectsLayer = get_node_or_null("../WorldMap/WsObjectsLayer") as WsObjectsLayer
	if ws:
		ws.reload()
		print("[Bridge] ws JSON recharge WsObjectsLayer")

func _parse_color(c: String) -> Color:
	match c:
		"blue":   return Entity.COLOR_PLAYER_OFFICIAL
		"green":  return Entity.COLOR_PLAYER_BOT
		"orange": return Entity.COLOR_NPC
	return Entity.COLOR_OBJECT

func _resolve_oid(d: Dictionary) -> int:
	if d.has("sid"):
		return _hash_id(str(d.get("sid", "")))
	return int(d.get("id", 0))

func _hash_id(s: String) -> int:
	return Crc32Util.entity_oid(s)

func is_live() -> bool:
	return _live_packets > 0

func _clear_demo_if_needed() -> void:
	if _demo_cleared:
		return
	if _em:
		_em.clear()
	_demo_cleared = true
	if _main and _main.has_method("on_mirror_udp_active"):
		_main.on_mirror_udp_active()
	print("[Bridge] flux UDP Prime actif — demo effacee")

func _short_tmpl(tmpl: String) -> String:
	var base: String = tmpl.get_file().get_basename()
	if base.begins_with("shared_"):
		base = base.substr(7)
	if base.length() > 20:
		return base.substr(0, 18) + ".."
	return base
