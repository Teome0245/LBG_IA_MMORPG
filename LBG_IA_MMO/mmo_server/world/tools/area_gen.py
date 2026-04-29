import random

def empty_grid(w, h, fill='.'):
    return [[fill for _ in range(w)] for _ in range(h)]

def print_grid(grid):
    for row in grid:
        print(''.join(row))
    print()

# -------------------------
# 1) Générateur de VILLE
# -------------------------

def generate_city(w=80, h=60, seed=None):
    if seed is not None:
        random.seed(seed)
    g = empty_grid(w, h, '.')

    # Mur extérieur
    for x in range(w):
        g[0][x] = '#'
        g[h-1][x] = '#'
    for y in range(h):
        g[y][0] = '#'
        g[y][w-1] = '#'

    # Routes principales (croix)
    midx, midy = w // 2, h // 2
    for x in range(1, w-1):
        g[midy][x] = 'R'
    for y in range(1, h-1):
        g[y][midx] = 'R'

    # Quartiers : on place des blocs de maisons autour des routes
    def place_block(x0, y0, x1, y1, density=0.4):
        for y in range(y0, y1):
            for x in range(x0, x1):
                if g[y][x] == '.' and random.random() < density:
                    g[y][x] = 'H'

    # 4 quartiers
    place_block(1, 1, midx-1, midy-1, density=0.5)
    place_block(midx+1, 1, w-1, midy-1, density=0.5)
    place_block(1, midy+1, midx-1, h-1, density=0.5)
    place_block(midx+1, midy+1, w-1, h-1, density=0.5)

    # Place centrale
    for y in range(midy-2, midy+3):
        for x in range(midx-4, midx+5):
            if 0 < x < w-1 and 0 < y < h-1:
                g[y][x] = 'R'

    # Porte de la ville
    gate_x = midx
    g[h-1][gate_x] = 'R'
    g[h-2][gate_x] = 'R'

    return g

# -------------------------
# 2) Générateur de VILLAGE
# -------------------------

def generate_village(w=50, h=40, seed=None):
    if seed is not None:
        random.seed(seed)
    g = empty_grid(w, h, '.')

    # Chemin principal horizontal
    midy = h // 2
    for x in range(0, w):
        g[midy][x] = 'R'

    # Quelques maisons autour du chemin
    def place_house_near_road():
        for _ in range(15):
            x = random.randint(3, w-4)
            offset = random.choice([-2, -3, 2, 3])
            y = midy + offset
            if 1 < y < h-1:
                # Buffer XXL : On vérifie une zone de 7x5 autour pour être sûr
                can_place = True
                for dy in range(-2, 3):
                    for dx in range(-3, 4):
                        if 0 <= y+dy < h and 0 <= x+dx < w:
                            if g[y+dy][x+dx] in ('H', 'X'):
                                can_place = False
                if can_place:
                    g[y][x] = 'H'

    place_house_near_road()

    # Petit puits au centre
    g[midy][w//2] = 'X'  # puits / place

    # Quelques arbres autour
    for _ in range(80):
        x = random.randint(0, w-1)
        y = random.randint(0, h-1)
        if g[y][x] == '.':
            # Zone d'exclusion arbres encore plus large
            near_house = False
            for dy in range(-3, 4):
                for dx in range(-4, 5):
                    if 0 <= y+dy < h and 0 <= x+dx < w:
                        if g[y+dy][x+dx] in ('H', 'X'):
                            near_house = True
            if not near_house:
                g[y][x] = 'T'

    return g

# -------------------------
# 3) Générateurs de ZONES LOCALES
# -------------------------

def generate_zone_forest(w=60, h=40, seed=None):
    if seed is not None:
        random.seed(seed)
    g = empty_grid(w, h, '.')

    for y in range(h):
        for x in range(w):
            if random.random() < 0.55:
                g[y][x] = 'T'

    for _ in range(5):
        cx = random.randint(5, w-6)
        cy = random.randint(5, h-6)
        r = random.randint(3, 6)
        for y in range(cy-r, cy+r+1):
            for x in range(cx-r, cx+r+1):
                if 0 <= x < w and 0 <= y < h:
                    if (x-cx)**2 + (y-cy)**2 <= r*r:
                        g[y][x] = '.'

    x, y = 0, h // 2
    for _ in range(w*2):
        if 0 <= x < w and 0 <= y < h:
            g[y][x] = 'R'
        x += 1
        y += random.choice([-1, 0, 1])
        if x >= w: break
    return g

def generate_zone_marsh(w=60, h=40, seed=None):
    if seed is not None:
        random.seed(seed)
    g = empty_grid(w, h, '.')

    for y in range(h):
        for x in range(w):
            r = random.random()
            if r < 0.35: g[y][x] = 'W'
            elif r < 0.55: g[y][x] = 'T'

    for _ in range(6):
        cx = random.randint(5, w-6)
        cy = random.randint(5, h-6)
        r = random.randint(2, 4)
        for y in range(cy-r, cy+r+1):
            for x in range(cx-r, cx+r+1):
                if 0 <= x < w and 0 <= y < h:
                    if (x-cx)**2 + (y-cy)**2 <= r*r: g[y][x] = '.'
    return g

def generate_zone_ruins(w=60, h=40, seed=None):
    if seed is not None:
        random.seed(seed)
    g = empty_grid(w, h, '.')

    for _ in range(4):
        x0, y0 = random.randint(5, w-15), random.randint(5, h-15)
        x1, y1 = x0 + random.randint(5, 12), y0 + random.randint(5, 10)
        for x in range(x0, x1):
            g[y0][x] = '#'
            g[y1][x] = '#'
        for y in range(y0, y1):
            g[y][x0] = '#'
            g[y][x1] = '#'
        for _ in range(3):
            hx, hy = random.randint(x0+1, x1-1), random.choice([y0, y1])
            g[hy][hx] = '.'
        for _ in range(10):
            rx, ry = random.randint(x0+1, x1-1), random.randint(y0+1, y1-1)
            g[ry][rx] = 'X'
    return g

# -------------------------
# 4) Donjon extérieur
# -------------------------

def generate_outdoor_dungeon(w=60, h=40, seed=None):
    if seed is not None:
        random.seed(seed)
    g = empty_grid(w, h, '.')

    for y in range(0, h//3):
        for x in range(w):
            if random.random() < 0.7: g[y][x] = '#'

    ex, ey = w // 2, h // 3
    g[ey][ex] = 'G'
    g[ey+1][ex] = 'R'
    g[ey+2][ex] = 'R'

    x, y = ex, ey+2
    for _ in range(30):
        if 0 <= x < w and 0 <= y < h: g[y][x] = 'R'
        y += 1
        x += random.choice([-1, 0, 1])
        if y >= h: break

    for _ in range(80):
        x, y = random.randint(0, w-1), random.randint(h//3, h-1)
        if g[y][x] == '.': g[y][x] = random.choice(['T', 'X'])
    return g

if __name__ == "__main__":
    print("Test rapide des générateurs...")
    print_grid(generate_village(seed=42))
