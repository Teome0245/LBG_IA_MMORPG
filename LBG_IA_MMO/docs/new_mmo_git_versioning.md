# Versionnement Git — `new_mmo` (PreCU + Prime)

## Contexte

Deux lignées Core3 coexistent :

| Ligne | Chemin Git | VM | Chemin runtime |
|-------|------------|-----|----------------|
| **PreCU** | `new_mmo/lbg-mmo/Core3/MMOCoreORB/` | 245 | `/opt/lbg-new-mmo/MMOCoreORB` |
| **Prime** | `new_mmo/lbg-mmo/server-core3/` + `MMOEngine/` | 246 | `/opt/lbg-antigravity/lbg-mmo/` |

Les patches **Lua / JSON** (pont IA, économie, NPC) restent dans **`LBG_IA_MMO/content/core3/`** (monorepo).

## Dépôt `new_mmo`

- Emplacement : `~/projects/new_mmo`
- **Non** inclus dans `LBG_IA_MMO` (voir ADR 0005, `third_party/README.md`)
- Tags : `deploy/245-precu`, `deploy/246-prime`

## Workflow quotidien

```bash
# 1. Modifier sources localement (ou pull si patch sur VM)
cd ~/projects/new_mmo
git status

# 2. Déployer
cd ~/projects/LBG_IA_MMORPG/LBG_IA_MMO
LBG_NEW_MMO_VM_HOST=192.168.0.245 bash infra/scripts/rsync_new_mmo_core3_orb.sh
LBG_NEW_MMO_VM_HOST=192.168.0.246 bash infra/scripts/rsync_lbg_mmo_antigravity_vm.sh

# 3. Commit
cd ~/projects/new_mmo
git add -A && git commit -m "…"
git tag -f deploy/246-prime   # après validation VM
```

## Récupération depuis VM (secours)

```bash
bash infra/scripts/pull_core3_from_vm.sh both
```

Exclut : `build/`, `bin/`, `databases/`, `.tre`, `config-local.lua`.

## Clone SWGEmu officiel

`new_mmo/Core3/` (gitignoré) = référence `github.com/swgemu/Core3`. Ne pas confondre avec `lbg-mmo/` utilisé en production LBG.
