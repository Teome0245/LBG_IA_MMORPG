extends Node3D
## Silhouette humanoïde procédurale — en attendant export SWG → GLB.

@onready var _torso: MeshInstance3D = $Torso
@onready var _head: MeshInstance3D = $Head


func _ready() -> void:
	var body_mat := StandardMaterial3D.new()
	body_mat.albedo_color = Color(0.72, 0.68, 0.62)
	body_mat.roughness = 0.8
	_torso.material_override = body_mat
	var head_mat := body_mat.duplicate() as StandardMaterial3D
	head_mat.albedo_color = Color(0.82, 0.74, 0.68)
	_head.material_override = head_mat
