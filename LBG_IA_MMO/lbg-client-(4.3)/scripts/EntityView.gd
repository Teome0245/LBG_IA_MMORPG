extends Node3D
## Vue entité (capsule + nom). Pas de class_name : compat Godot 4.3.

var entity_id: String = ""
var _kind: String = "npc"
var _base_scale := Vector3.ONE

func setup(ent: Dictionary) -> void:
	entity_id = str(ent.get("id", ""))
	_kind = str(ent.get("kind", "npc"))
	var kind: String = _kind
	var mesh: MeshInstance3D = $Mesh
	var label: Label3D = $Label3D
	label.text = str(ent.get("name", entity_id))
	label.font_size = 48
	label.outline_size = 12
	if "modulate" in label:
		label.modulate = Color(1, 1, 0.95)
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	var mat := StandardMaterial3D.new()
	if kind == "player":
		mat.albedo_color = Color(0.25, 0.55, 0.95)
		mat.emission_enabled = true
		mat.emission = Color(0.1, 0.2, 0.4)
	else:
		mat.albedo_color = Color(0.9, 0.6, 0.25)
	mesh.material_override = mat
	update_from_snapshot(ent)

func update_from_snapshot(ent: Dictionary) -> void:
	global_position = GameState.display_position(ent)
	var scale_v: float = float(ent.get("scale", 1.0))
	if scale_v > 0.01:
		_base_scale = Vector3.ONE * scale_v
		$Mesh.scale = _base_scale

func set_targeted(on: bool) -> void:
	var mesh: MeshInstance3D = $Mesh
	var mat := mesh.material_override as StandardMaterial3D
	if mat == null:
		return
	if on:
		mat.emission_enabled = true
		mat.emission = Color(0.35, 0.85, 0.35)
		$Mesh.scale = _base_scale * 1.15
	else:
		if _kind == "player":
			mat.emission = Color(0.1, 0.2, 0.4)
		else:
			mat.emission_enabled = false
		$Mesh.scale = _base_scale
