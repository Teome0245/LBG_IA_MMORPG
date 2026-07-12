extends Node
## Connexion gateway Core3 Prime (lbg-ws/1). Mode Terre1 conservé en code legacy uniquement.

enum ServerMode { MMMORPG, PRIME }

const DEFAULT_HOST := "192.168.0.246"
const PORT_MMMORPG := 7733
const PORT_PRIME := 50000
const PROTO_MMMORPG := "mmmorpg-ws/1"
const PROTO_PRIME := "lbg-ws/1"

var host: String = DEFAULT_HOST
var server_mode: ServerMode = ServerMode.PRIME
var port_override: int = -1

func get_port() -> int:
	if port_override > 0:
		return port_override
	return PORT_PRIME if server_mode == ServerMode.PRIME else PORT_MMMORPG

func ws_url() -> String:
	return "ws://%s:%d" % [host.strip_edges(), get_port()]

func mode_label() -> String:
	return "Tatooine Prime" if server_mode == ServerMode.PRIME else "Terre1 (mmmorpg)"
