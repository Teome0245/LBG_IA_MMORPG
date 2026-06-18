# Patch VM — trainer Entertainer Mos Eisley (Bige Coto)

Désactive le spawn vanilla pour éviter le doublon avec le roster IA entertainer (`npc:core3_bige_coto` / `lyra_velo` / `talen_ress`).

Fichier : `MMOCoreORB/bin/scripts/screenplays/cities/tatooine_mos_eisley.lua`  
Ligne ~332 :

```lua
-- LBG IA npc:core3_bige_coto
-- {"trainer_entertainer",0,3477.89,5,-4791.6,215,0, ""},
```

Après patch : redémarrer `core3-clean`.
