import random

def generate_village_premium(w=50, h=40, seed=42):
    random.seed(seed)
    g = [['.' for _ in range(w)] for _ in range(h)]
    midx = w // 2
    midy = h // 2
    for x in range(1, w-1):
        g[midy][x] = 'R'
    for y in range(1, h-1):
        g[y][midx] = 'R'
    def place_block(x0, y0, x1, y1, density=0.4):
        for y in range(y0, y1):
            for x in range(x0, x1):
                if g[y][x] == '.' and random.random() < density:
                    g[y][x] = 'H'
    place_block(1, 1, midx-1, midy-1, density=0.5)
    place_block(midx+1, 1, w-1, midy-1, density=0.5)
    place_block(1, midy+1, midx-1, h-1, density=0.5)
    place_block(midx+1, midy+1, w-1, h-1, density=0.5)
    for y in range(midy-2, midy+3):
        for x in range(midx-4, midx+5):
            if 0 < x < w-1 and 0 < y < h-1:
                g[y][x] = 'R'
    gate_x = midx
    g[h-1][gate_x] = 'R'
    g[h-2][gate_x] = 'R'
    # ANTI CHEVAUCHEMENT (Buffer XXL 7x5)
    house_coords = []
    for y in range(h):
        for x in range(w):
            if g[y][x] == 'H':
                too_close = False
                for (hx, hy) in house_coords:
                    if abs(hx - x) < 7 and abs(hy - y) < 5:
                        too_close = True
                        break
                if too_close:
                    g[y][x] = '.'
                else:
                    house_coords.append((x, y))
    
    house_sizes = [(6, 4), (3, 3), (3, 3), (4, 3), (4, 3), (4, 3), (6, 5), (4, 3), (5, 4), (4, 3)]
    idx = 0
    for y in range(h):
        for x in range(w):
            if g[y][x] == 'H':
                bw, bh = house_sizes[idx % len(house_sizes)]
                mx = (x * 32 - (bw * 32) // 2 + 16 + (bw * 32) // 2 - 800) / 16
                mz = (y * 32 - (bh * 32) // 2 + 16 + (bh * 32) // 2 - 640) / 16
                print(f"House {idx}: grid=({x}, {y}) -> mx={mx}, mz={mz}, w={bw*2}, h={bh*2}")
                idx += 1

generate_village_premium()
