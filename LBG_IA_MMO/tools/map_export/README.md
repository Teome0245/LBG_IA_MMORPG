# Map export — M4 Tatooine Godot

## Export carte + POI

```bash
cd LBG_IA_MMO
PRIME_CLIENT=~/projects/new_mmo/prime-client \
  python3 tools/map_export/export_tatooine_for_godot.py
```

## Export bâtiments .ws (M4.4)

Extraire `snapshot/tatooine.ws` depuis les TRE serveur, puis :

```bash
python3 tools/map_export/ws_to_json.py /chemin/tatooine.ws \
  -o ~/projects/new_mmo/prime-client/assets/maps/mos_eisley_ws.json \
  --godot-port 12345 --godot-host 172.x.x.x
```

Sans fichier `.ws` : le sample `mos_eisley_ws.json` suffit pour Godot.

## Godot

| Touche | Couche |
|--------|--------|
| Ctrl+M | Carte Tatooine |
| Ctrl+W | Eau |
| Ctrl+C | Collision |
| Ctrl+B | Bâtiments .ws |

## Tests

```bash
python3 tools/map_export/test_ws_to_json.py -v
```
