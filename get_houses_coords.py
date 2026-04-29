import sys
sys.path.append('LBG_IA_MMO/mmo_server/world/tools')
from area_gen import generate_village

def find_houses():
    grid = generate_village(50, 40, seed=42)
    visited = set()
    houses = []
    
    # Same logic as village_visualizer.py
    for y in range(40):
        for x in range(50):
            if grid[y][x] == 'H' and (x, y) not in visited:
                bw, bh = 4, 3
                # Top left of building in tiles: (x-1, y-1)
                # Bottom right in tiles: (x-1+4, y-1+3) = (x+3, y+2)
                # In meters (each tile is 2x2 meters, map is centered at 0,0, w=100m, h=80m)
                # top left corner = (-50, -40)
                # Center of this building in m:
                mx = (x + 1) * 2 - 50
                mz = (y + 0.5) * 2 - 40
                
                # width/height in m
                surface = 8 * 6
                
                houses.append({"x": mx, "z": mz, "w": 8, "h": 6, "surface": surface})
                visited.add((x, y))
                
    for i, h in enumerate(houses):
        print(f"House {i}: x={h['x']}, z={h['z']}, w={h['w']}, h={h['h']}")

find_houses()
