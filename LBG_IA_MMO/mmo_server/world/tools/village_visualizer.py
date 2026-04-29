import random
from PIL import Image, ImageDraw, ImageFilter
from area_gen import generate_village

# Configuration : On augmente la résolution pour plus de détails
TILE_SIZE = 32
GRID_W = 50
GRID_H = 40

def draw_textured_rect(draw, coords, color, noise=10):
    """Dessine un rectangle avec une légère variation de couleur."""
    r, g, b = color
    draw.rectangle(coords, fill=color)
    # Ajout de micro-bruit pour la texture
    for _ in range(5):
        nx = random.randint(coords[0], coords[2])
        ny = random.randint(coords[1], coords[3])
        nr = max(0, min(255, r + random.randint(-noise, noise)))
        ng = max(0, min(255, g + random.randint(-noise, noise)))
        nb = max(0, min(255, b + random.randint(-noise, noise)))
        draw.point((nx, ny), fill=(nr, ng, nb))

def generate_village_premium(output_path="bourg_palette_map.png", seed=42):
    # On génère la grille de base
    grid = generate_village(GRID_W, GRID_H, seed=seed)
    
    # Couleurs Palette LBG Premium
    COLORS = {
        '.': (34, 55, 34),   # Herbe profonde
        'T': (20, 40, 20),   # Forêt sombre
        'R': (70, 70, 80),   # Route pavée
        'H': (120, 50, 40),  # Toit de tuiles rouges
        'X': (220, 220, 230),# Pierre du puits
        'W': (30, 60, 100),  # Eau
    }

    img = Image.new('RGB', (GRID_W * TILE_SIZE, GRID_H * TILE_SIZE), color=(20, 20, 25))
    draw = ImageDraw.Draw(img)

    # 1. Dessin de la base (Herbe/Sol)
    for y in range(GRID_H):
        for x in range(GRID_W):
            char = grid[y][x]
            color = COLORS.get(char, COLORS['.'])
            rect = [x * TILE_SIZE, y * TILE_SIZE, (x + 1) * TILE_SIZE, (y + 1) * TILE_SIZE]
            draw_textured_rect(draw, rect, color, noise=5)

    # 2. Amélioration des routes (Bords plus doux)
    for y in range(GRID_H):
        for x in range(GRID_W):
            if grid[y][x] == 'R':
                rect = [x * TILE_SIZE, y * TILE_SIZE, (x + 1) * TILE_SIZE, (y + 1) * TILE_SIZE]
                draw.rectangle(rect, fill=(80, 80, 90), outline=(60, 60, 70))

    # 3. Dessin des Bâtiments (Tailles variables selon index)
    visited_h = set()
    house_idx = 0
    # Tailles en tuiles (largeur, hauteur) pour les 10 maisons générées par le seed 42
    house_sizes = [(6, 4), (3, 3), (3, 3), (4, 3), (4, 3), (4, 3), (6, 5), (4, 3), (5, 4), (4, 3)]
    
    for y in range(GRID_H):
        for x in range(GRID_W):
            if grid[y][x] == 'H' and (x, y) not in visited_h:
                bw, bh = house_sizes[house_idx % len(house_sizes)]
                house_idx += 1
                
                # Centrer le bâtiment sur la tuile (x, y)
                bx1 = x * TILE_SIZE - (bw * TILE_SIZE) // 2 + TILE_SIZE // 2
                by1 = y * TILE_SIZE - (bh * TILE_SIZE) // 2 + TILE_SIZE // 2
                bx2 = bx1 + bw * TILE_SIZE
                by2 = by1 + bh * TILE_SIZE
                
                # Ombre portée
                draw.rectangle([bx1+5, by1+5, bx2+5, by2+5], fill=(10, 10, 10, 100))
                
                # Corps du bâtiment
                draw.rectangle([bx1, by1, bx2, by2], fill=(100, 40, 30), outline=(60, 20, 10), width=2)
                
                # Toit (Effet de relief)
                draw.polygon([
                    (bx1, by1), (bx2, by1), 
                    (bx2 - 10, by1 + 15), (bx1 + 10, by1 + 15)
                ], fill=(130, 60, 50))
                
                visited_h.add((x, y))

    # 4. Arbres (Cercles texturés)
    for y in range(GRID_H):
        for x in range(GRID_W):
            if grid[y][x] == 'T':
                cx, cy = x * TILE_SIZE + TILE_SIZE//2, y * TILE_SIZE + TILE_SIZE//2
                r = TILE_SIZE // 2 + random.randint(2, 6)
                draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(30, 60, 30), outline=(10, 30, 10))

    # 5. Le Puits (Cercle de pierre)
    for y in range(GRID_H):
        for x in range(GRID_W):
            if grid[y][x] == 'X':
                cx, cy = x * TILE_SIZE + TILE_SIZE//2, y * TILE_SIZE + TILE_SIZE//2
                draw.ellipse([cx-15, cy-15, cx+15, cy+15], fill=(150, 150, 160), outline=(80, 80, 80), width=3)
                draw.ellipse([cx-5, cy-5, cx+5, cy+5], fill=(20, 20, 40)) # Eau au fond

    img.save(output_path)
    print(f"Image Premium générée : {output_path}")

if __name__ == "__main__":
    generate_village_premium()
