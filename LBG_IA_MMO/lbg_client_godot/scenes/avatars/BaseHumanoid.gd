extends Node3D
## Conteneur modèle importé (GLB SWG ou placeholder) + animations.

const IDLE_ANIMS: PackedStringArray = ["idle", "Idle", "stand", "Stand"]
const WALK_ANIMS: PackedStringArray = ["walk", "Walk", "run", "Run"]

@onready var _model_root: Node3D = $ModelRoot

var _anim: AnimationPlayer
var _mesh_parts: Array[MeshInstance3D] = []
var _base_scale := Vector3.ONE
var _kind := "npc"
var _is_core3_player := false
var _current_anim := ""


func load_visual(path: String, ent: Dictionary) -> bool:
	_clear_model()
	if path.is_empty():
		return false
	var packed: Variant = load(path)
	if packed == null:
		return false
	var inst: Node
	if packed is PackedScene:
		inst = (packed as PackedScene).instantiate()
	else:
		return false
	_kind = str(ent.get("kind", "npc"))
	_is_core3_player = _kind == "player" and str(ent.get("source", "")) == "core3"
	_model_root.add_child(inst)
	_collect_mesh_parts(inst)
	_anim = _find_animation_player(inst)
	_apply_kind_tint()
	_play_first_matching(IDLE_ANIMS, "idle")
	return true


func set_body_scale(scale_v: float) -> void:
	if scale_v > 0.01:
		_base_scale = Vector3.ONE * scale_v
	else:
		_base_scale = Vector3.ONE
	scale = _base_scale


func set_highlight(on: bool) -> void:
	if not on:
		_apply_kind_tint()
	else:
		for mesh in _mesh_parts:
			var mat := mesh.material_override as StandardMaterial3D
			if mat == null:
				continue
			mat.emission_enabled = true
			mat.emission = Color(0.35, 0.85, 0.35)
	if on:
		scale = _base_scale * 1.08
	else:
		scale = _base_scale


func play_locomotion(moving: bool) -> void:
	var names: PackedStringArray = WALK_ANIMS if moving else IDLE_ANIMS
	var label := "walk" if moving else "idle"
	_play_first_matching(names, label)


func _play_first_matching(names: PackedStringArray, label: String) -> void:
	if _anim == null:
		return
	if _current_anim == label:
		return
	for n in names:
		if _anim.has_animation(n):
			_anim.play(n)
			_current_anim = label
			return


func _apply_kind_tint() -> void:
	var tint := Color(0.92, 0.55, 0.22)
	var emission := Color(0.15, 0.08, 0.02)
	if _kind == "player":
		if _is_core3_player:
			tint = Color(0.55, 0.95, 0.88)
			emission = Color(0.1, 0.45, 0.4)
		else:
			tint = Color(0.45, 0.65, 0.98)
			emission = Color(0.15, 0.35, 0.7)
	for mesh in _mesh_parts:
		var mat := StandardMaterial3D.new()
		mat.albedo_color = tint
		mat.roughness = 0.75
		mat.emission_enabled = true
		mat.emission = emission
		mesh.material_override = mat


func _collect_mesh_parts(node: Node) -> void:
	if node is MeshInstance3D:
		_mesh_parts.append(node as MeshInstance3D)
	for child in node.get_children():
		_collect_mesh_parts(child)


func _find_animation_player(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node as AnimationPlayer
	for child in node.get_children():
		var found := _find_animation_player(child)
		if found != null:
			return found
	return null


func _clear_model() -> void:
	_mesh_parts.clear()
	_anim = null
	_current_anim = ""
	for child in _model_root.get_children():
		child.queue_free()
