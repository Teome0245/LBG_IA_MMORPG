extends Node3D
## Géométrie placeholder — cantina Mos Eisley (cell 1082877).
## Repère : SWG local (x, y profondeur, z) → Godot Vector3(x, z, y).

const BAR_X := 7.26
const BAR_Y := 1.15
const BAR_Z := -0.89
const GUEST_Y := 0.35
const GUEST_Z := 0.91
const DRONE_SCENE := preload("res://scenes/props/Robot01Drone.tscn")

static func swg_local_to_godot(lx: float, ly: float, lz: float) -> Vector3:
	return Vector3(lx, lz, ly)


func _ready() -> void:
	_build_room()


func _build_room() -> void:
	var floor_y: float = 0.88
	_add_box(
		"Floor",
		swg_local_to_godot(6.0, 2.0, 0.0),
		Vector3(22.0, 0.15, 18.0),
		Color(0.22, 0.18, 0.14),
		true,
	)
	_add_box(
		"FloorRing",
		swg_local_to_godot(BAR_X, BAR_Y, BAR_Z),
		Vector3(9.0, 0.12, 9.0),
		Color(0.28, 0.22, 0.16),
		true,
	)
	# Comptoir (côté staff)
	var bar_pos: Vector3 = swg_local_to_godot(BAR_X, BAR_Y, BAR_Z)
	_add_box("BarCounter", bar_pos + Vector3(0, 0.55, 0), Vector3(5.5, 1.1, 1.2), Color(0.35, 0.28, 0.2), true)
	# Zone client (face au bar)
	var guest: Vector3 = swg_local_to_godot(BAR_X, GUEST_Y, GUEST_Z)
	_add_box("ClientStrip", guest + Vector3(0, 0.02, 0), Vector3(6.0, 0.08, 2.5), Color(0.32, 0.26, 0.18), true)
	# Murs bas
	for i in range(4):
		var half: int = int(i / 2)
		var wall_pos: Vector3 = Vector3(6.0 + float(i % 2) * 12.0, floor_y + 1.8, -6.0 + float(half) * 12.0)
		_add_box("Wall%d" % i, wall_pos, Vector3(14.0, 3.6, 0.35), Color(0.15, 0.12, 0.1), true)
	# Piliers / vats décor
	_add_box("VatL", swg_local_to_godot(4.0, 2.2, -2.0), Vector3(1.2, 2.4, 1.2), Color(0.4, 0.38, 0.35), false)
	_add_box("VatR", swg_local_to_godot(10.5, 2.2, -2.0), Vector3(1.2, 2.4, 1.2), Color(0.4, 0.38, 0.35), false)
	_add_drone_decor()


func _add_drone_decor() -> void:
	if DRONE_SCENE == null:
		return
	var drone: Node3D = DRONE_SCENE.instantiate()
	drone.name = "DroneSteampunkDecor"
	drone.position = swg_local_to_godot(8.2, 3.8, -1.2)
	drone.yaw_degrees = -35.0
	add_child(drone)


func _add_box(
	node_name: String,
	pos: Vector3,
	size: Vector3,
	color: Color,
	collision: bool,
) -> void:
	var body: StaticBody3D = StaticBody3D.new()
	body.name = node_name
	body.position = pos
	var mesh_inst: MeshInstance3D = MeshInstance3D.new()
	var box: BoxMesh = BoxMesh.new()
	box.size = size
	mesh_inst.mesh = box
	var mat: StandardMaterial3D = StandardMaterial3D.new()
	mat.albedo_color = color
	mat.roughness = 0.85
	mesh_inst.material_override = mat
	body.add_child(mesh_inst)
	if collision:
		var col: CollisionShape3D = CollisionShape3D.new()
		var shape: BoxShape3D = BoxShape3D.new()
		shape.size = size
		col.shape = shape
		body.add_child(col)
	add_child(body)
