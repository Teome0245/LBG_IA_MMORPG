extends Node3D
## Drone steampunk robot01 (Infographiste_IA / TripoSR).
## Pivot racine = projection au sol ; le mesh vole via HoverOffset.

const DEFAULT_TARGET_SPAN_M := 0.55
const DEFAULT_HOVER_HEIGHT_M := 0.75

@export var target_span_m: float = DEFAULT_TARGET_SPAN_M
@export var hover_height_m: float = DEFAULT_HOVER_HEIGHT_M
@export var yaw_degrees: float = 0.0

@onready var _hover: Node3D = $HoverOffset
@onready var _pivot: Node3D = $HoverOffset/ModelPivot


func _ready() -> void:
	_hover.position.y = hover_height_m
	_pivot.rotation_degrees.y = yaw_degrees
	await get_tree().process_frame
	_fix_materials(_pivot)
	_fit_model_to_pivot()


func _fix_materials(root: Node) -> void:
	for node in root.get_children():
		if node is MeshInstance3D:
			var mesh_inst := node as MeshInstance3D
			if mesh_inst.mesh == null:
				continue
			for si in mesh_inst.mesh.get_surface_count():
				var src: Material = mesh_inst.mesh.surface_get_material(si)
				var mat := StandardMaterial3D.new()
				if src is BaseMaterial3D:
					mat.albedo_color = (src as BaseMaterial3D).albedo_color
				if src is StandardMaterial3D:
					var s := src as StandardMaterial3D
					if s.albedo_texture:
						mat.albedo_texture = s.albedo_texture
				mat.metallic = 0.0
				mat.roughness = 0.85
				mat.cull_mode = BaseMaterial3D.CULL_DISABLED
				mat.shading_mode = BaseMaterial3D.SHADING_MODE_PER_PIXEL
				mesh_inst.set_surface_override_material(si, mat)
		_fix_materials(node)


func _fit_model_to_pivot() -> void:
	var aabb := _local_aabb_under(_pivot)
	if aabb.size.length_squared() < 1.0e-8:
		push_warning("Robot01Drone: AABB vide — ouvrir le projet dans Godot pour importer le GLB.")
		return

	var span := maxf(aabb.size.x, maxf(aabb.size.y, aabb.size.z))
	var scale_factor := target_span_m / span if span > 0.001 else 1.0
	_pivot.scale = Vector3.ONE * scale_factor

	var center := aabb.get_center()
	var bottom_y := aabb.position.y
	_pivot.position = Vector3(
		-center.x * scale_factor,
		-bottom_y * scale_factor,
		-center.z * scale_factor,
	)


func _local_aabb_under(root: Node3D) -> AABB:
	var out := AABB()
	var found := false
	var stack: Array[Node] = [root]
	while not stack.is_empty():
		var node: Node = stack.pop_back()
		if node is MeshInstance3D:
			var mesh_inst := node as MeshInstance3D
			if mesh_inst.mesh != null:
				var local_aabb := _mesh_aabb_in_node_space(mesh_inst, root)
				if not found:
					out = local_aabb
					found = true
				else:
					out = out.merge(local_aabb)
		for child in node.get_children():
			stack.append(child)
	return out


func _mesh_aabb_in_node_space(mesh_inst: MeshInstance3D, space: Node3D) -> AABB:
	var xform := space.global_transform.affine_inverse() * mesh_inst.global_transform
	return xform * mesh_inst.mesh.get_aabb()
