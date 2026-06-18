# Schémas `lbg-ws`

| Fichier | Proto | Sens |
|---------|-------|------|
| `client.login.schema.json` | v1 | Login stub |
| `server.world_state.schema.json` | **v1** | Snapshots agrégés (gateway actuel) |
| `client.zone_command_v2.schema.json` | **v2** | Commandes client → zone |
| `server.zone_state_v2.schema.json` | **v2** | Deltas ZoneServer → Godot |

Spec C++ : [`../../core3_zone_bridge_spec.md`](../../core3_zone_bridge_spec.md).
