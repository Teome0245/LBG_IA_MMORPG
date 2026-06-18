# Core3 — God mode

## Où c’est géré

| Fichier | Rôle |
|---------|------|
| `bin/scripts/managers/player_creation_manager.lua` | `freeGodMode` (god pour **tous**), `inheritAccountAdminLevel` (copie admin compte → perso) |
| `server-core3/.../PlayerCreationManager.cpp` | Applique ces flags à la création de personnage |
| `server-core3/.../PlayerObject.idl` | `hasGodMode()` = `adminLevel > 0` **et** ability `"admin"` |
| `bin/scripts/staff/levels/admin.lua` | Niveau staff 15 (skills admin) |
| `bin/scripts/commands/getAccountInfo.lua` + `SetGodModeCommand.h` | `/getaccountinfo`, `/setGodMode` |

## Cause fréquente (Teome)

`freeGodMode = 0` sur la VM — **pas** la cause.

Compte **Teome** avec `admin_level = 15` : à chaque **nouveau** perso, le serveur appelait `updatePermissionLevel(15)` (skills staff + god).

## Désactiver en jeu (persos existants)

Sur le perso connecté (admin requis) :

```
/setGodMode self off
```

God mode off, compte reste admin 15.

Retirer tout le staff du perso :

```
/setGodMode self player
```

Réactiver les outils admin sur ce perso :

```
/setGodMode self on
```

## Nouveaux persos sans god (config)

Dans `player_creation_manager.lua` :

```lua
inheritAccountAdminLevel = 0;
```

Nécessite un **rebuild** `core3-clean` pour que le C++ lise ce flag (Lua seul ne suffit pas tant que le binaire n’est pas à jour).

## Compte admin vs gameplay

- `accounts.admin_level` : droits compte / création (si `inheritAccountAdminLevel = 1`).
- `PlayerObject.adminLevel` + ability `admin` : god mode en session.

Garder Teome à 15 en SQL pour l’UI web / gestion, avec `inheritAccountAdminLevel = 0` et `/setGodMode self on` quand tu veux staffer en jeu.
