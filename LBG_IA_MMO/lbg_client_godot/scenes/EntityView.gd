extends Node3D
## Entité monde — humanoïde (GLB / placeholder) ou capsule de secours.

const BASE_HUMANOID_SCENE := "res://scenes/avatars/BaseHumanoid.tscn"

var entity_id: String = ""
var _kind: String = "npc"
var _base_scale := Vector3.ONE
var _humanoid: Node3D
var _uses_humanoid := false

@onready var _capsule: MeshInstance3D = $CapsuleFallback
@onready var _label: Label3D = $Label3D


func setup(ent: Dictionary) -> void:
	entity_id = str(ent.get("id", ""))
	_kind = str(ent.get("kind", "npc"))
	var kind: String = _kind
	var src := str(ent.get("source", ""))
	var nm := str(ent.get("name", entity_id))
	if src == "core3" and kind == "player":
		_label.text = "%s [lbgemu]" % nm
	else:
		_label.text = nm
	var slot: int = absi(entity_id.hash()) % 7
	_label.position = Vector3((slot - 3) * 0.45, 2.15 + slot * 0.12, 0)
	_label.font_size = 48
	_label.outline_size = 12
	_label.modulate = Color(1, 1, 0.95)
	_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_mount_visual(ent)
	update_from_snapshot(ent)


func _mount_visual(ent: Dictionary) -> void:
	if _humanoid != null:
		_humanoid.queue_free()
		_humanoid = null
	_uses_humanoid = false
	var path := AvatarLibrary.resolve_visual_path(ent)
	var base_scene: PackedScene = load(BASE_HUMANOID_SCENE) as PackedScene
	if base_scene != null and not path.is_empty():
		_humanoid = base_scene.instantiate()
		add_child(_humanoid)
		if _humanoid.has_method("load_visual"):
			_uses_humanoid = _humanoid.call("load_visual", path, ent)
	if _uses_humanoid:
		_capsule.visible = false
	else:
		_capsule.visible = true
		_style_capsule(ent)


func _style_capsule(ent: Dictionary) -> void:
	var kind := str(ent.get("kind", "npc"))
	var src := str(ent.get("source", ""))
	var mat := StandardMaterial3D.new()
	if kind == "player":
		if src == "core3":
			mat.albedo_color = Color(0.2, 0.85, 0.75)
			mat.emission = Color(0.1, 0.45, 0.4)
		else:
			mat.albedo_color = Color(0.25, 0.55, 0.95)
			mat.emission = Color(0.15, 0.35, 0.7)
		mat.emission_enabled = true
		_capsule.scale = Vector3(1.1, 1.1, 1.1)
	else:
		mat.albedo_color = Color(0.92, 0.55, 0.22)
		mat.emission_enabled = true
		mat.emission = Color(0.15, 0.08, 0.02)
		_capsule.scale = Vector3(1.0, 1.0, 1.0)
	_capsule.material_override = mat


func update_from_snapshot(ent: Dictionary) -> void:
	global_position = GameState.display_position(ent)
	var scale_v: float = float(ent.get("scale", 1.0))
	if scale_v > 0.01:
		_base_scale = Vector3.ONE * scale_v
	if _uses_humanoid and _humanoid != null and _humanoid.has_method("set_body_scale"):
		_humanoid.call("set_body_scale", scale_v if scale_v > 0.01 else 1.0)
	else:
		_capsule.scale = _base_scale


func set_targeted(on: bool) -> void:
	if _uses_humanoid and _humanoid != null and _humanoid.has_method("set_highlight"):
		_humanoid.call("set_highlight", on)
		return
	var mat := _capsule.material_override as StandardMaterial3D
	if mat == null:
		return
	if on:
		mat.emission_enabled = true
		mat.emission = Color(0.35, 0.85, 0.35)
		_capsule.scale = _base_scale * 1.15
	else:
		if _kind == "player":
			mat.emission = Color(0.1, 0.2, 0.4)
		else:
			mat.emission_enabled = false
		_capsule.scale = _base_scale
