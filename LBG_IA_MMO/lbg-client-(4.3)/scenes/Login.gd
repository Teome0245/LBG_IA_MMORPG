extends Control

@onready var _host: LineEdit = $Panel/VBox/Host
@onready var _port: LineEdit = $Panel/VBox/Port
@onready var _mode: OptionButton = $Panel/VBox/ServerMode
@onready var _player: LineEdit = $Panel/VBox/PlayerName
@onready var _status: Label = $Panel/VBox/Status
@onready var _connect_btn: Button = $Panel/VBox/ConnectBtn

const MODE_TERRE1 := 0
const MODE_PRIME := 1
const WORLD_SCENE := "res://scenes/World.tscn"

var _entering_world := false

func _ready() -> void:
	add_to_group("ui")
	_setup_server_modes()
	_mode.item_selected.connect(_on_mode_changed)
	_host.text = Config.host
	_apply_mode_to_port()
	_player.text = "godot_lbg"
	_refresh_status_idle()
	_connect_btn.pressed.connect(_on_connect_pressed)
	Network.connected.connect(_on_network_connected)
	Network.connection_failed.connect(_on_connection_failed)
	Network.message_received.connect(_on_message)
	Network.disconnected.connect(_on_disconnected)

func _setup_server_modes() -> void:
	_mode.clear()
	_mode.add_item("Terre1 — mmmorpg (7733)", MODE_TERRE1)
	_mode.add_item("Tatooine Prime — gateway (50000)", MODE_PRIME)
	_mode.select(0)
	_on_mode_changed(0)

func _mode_index_to_config(idx: int) -> Config.ServerMode:
	return Config.ServerMode.PRIME if idx == MODE_PRIME else Config.ServerMode.MMMORPG

func _on_mode_changed(idx: int) -> void:
	Config.server_mode = _mode_index_to_config(idx)
	Config.port_override = -1
	_apply_mode_to_port()
	_refresh_status_idle()

func _apply_mode_to_port() -> void:
	_port.text = str(Config.get_port())
	_port.editable = true

func _refresh_status_idle() -> void:
	_status.text = "Prêt — %s | %s" % [Config.mode_label(), Config.ws_url()]

func _on_connect_pressed() -> void:
	Config.host = _host.text.strip_edges()
	Config.server_mode = _mode_index_to_config(_mode.selected)
	if _port.text.is_valid_int():
		Config.port_override = int(_port.text)
	else:
		Config.port_override = -1
	_status.text = "Connexion à %s…" % Config.ws_url()
	var resume := GameState.session_token
	GameState.reset()
	GameState.session_token = resume
	var err := Network.connect_with_player(_player.text, resume)
	if err != OK:
		_status.text = "Erreur: %s" % error_string(err)

func _on_network_connected() -> void:
	_status.text = "Connecté — attente welcome…"
	get_tree().create_timer(15.0).timeout.connect(_on_welcome_timeout)

func _on_welcome_timeout() -> void:
	if get_tree().current_scene != self:
		return
	if _status.text.contains("attente welcome"):
		_status.text = "Timeout — serveur %s" % Config.ws_url()

func _on_connection_failed(reason: String) -> void:
	_status.text = "Échec: %s" % reason

func _on_disconnected() -> void:
	_status.text = "Déconnecté"
	_refresh_status_idle()

func _on_message(msg: Dictionary) -> void:
	var t: String = str(msg.get("type", ""))
	if t == "error":
		_status.text = "Serveur: %s" % str(msg.get("message", msg))
		return
	if t == "welcome":
		if _entering_world:
			return
		_entering_world = true
		GameState.apply_welcome(msg)
		_status.text = "Welcome — %d entités — chargement monde…" % GameState.entities.size()
		call_deferred("_load_world_scene")
		return

func _load_world_scene() -> void:
	if not ResourceLoader.exists(WORLD_SCENE):
		_entering_world = false
		_status.text = "Fichier absent : %s (ouvrez lbg_client_godot/)" % WORLD_SCENE
		return
	var packed: Variant = ResourceLoader.load(WORLD_SCENE, "PackedScene")
	if packed == null:
		_entering_world = false
		_status.text = "World.tscn illisible — onglet Erreurs Godot (souvent script World.gd)"
		return
	var err := get_tree().change_scene_to_packed(packed as PackedScene)
	if err != OK:
		_entering_world = false
		_status.text = "Monde : %s (code %d)" % [error_string(err), err]
