import argparse
import json
import math
import random
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter
from area_gen import generate_village

# Configuration : On augmente la résolution pour plus de détails
TILE_SIZE = 32
GRID_W = 50
GRID_H = 40
TILE_M = 2.0  # 1 tuile = 2m (cf docs/area_generation.md)

# Si défini : grille importée (ex. Watabou via `watabou_import`) remplace `generate_village`.
VILLAGE_GRID_OVERRIDE: list[list[str]] | None = None


def reset_village_to_procedural_defaults() -> None:
    """Revient au village procédural 50×40 (comportement historique)."""
    global VILLAGE_GRID_OVERRIDE, GRID_W, GRID_H, TILE_SIZE
    VILLAGE_GRID_OVERRIDE = None
    GRID_W = 50
    GRID_H = 40
    TILE_SIZE = 32


def configure_village_from_watabou_json(
    watabou_json: Path,
    *,
    tile_m: float = 2.0,
    unit_m: float = 1.0,
    padding_tiles: int = 2,
    max_image_px: int = 1680,
) -> None:
    """
    Charge une carte Watabou (JSON) comme grille de village (collisions / rendu).
    Ajuste dynamiquement GRID_W/H et TILE_SIZE pour garder une image raisonnable.
    """
    global VILLAGE_GRID_OVERRIDE, GRID_W, GRID_H, TILE_SIZE
    from watabou_import import build_grid_from_watabou

    if not watabou_json.exists():
        raise FileNotFoundError(str(watabou_json))
    g = build_grid_from_watabou(
        watabou_json_path=watabou_json.resolve(),
        tile_m=tile_m,
        unit_m=unit_m,
        padding_tiles=padding_tiles,
    )
    GRID_W = int(g["grid"]["w"])
    GRID_H = int(g["grid"]["h"])
    VILLAGE_GRID_OVERRIDE = [list(row) for row in g["grid"]["rows"]]
    m = max(GRID_W, GRID_H)
    TILE_SIZE = max(4, min(32, int(max_image_px) // max(m, 1)))


def _village_grid(seed: int) -> list[list[str]]:
    if VILLAGE_GRID_OVERRIDE is not None:
        return VILLAGE_GRID_OVERRIDE
    return generate_village(GRID_W, GRID_H, seed=seed)


def _house_sizes_for_render() -> list[tuple[int, int]]:
    """Grille Watabou : bâtiments déjà « remplis » en H ; on dessine 1×1 tuile pour éviter les empilements."""
    if VILLAGE_GRID_OVERRIDE is not None:
        return [(1, 1)]
    return [(6, 4), (3, 3), (3, 3), (4, 3), (4, 3), (4, 3), (6, 5), (4, 3), (5, 4), (4, 3)]


def _default_pixie_seat_json() -> Path:
    # .../LBG_IA_MMO/mmo_server/world/tools/village_visualizer.py -> parents[4] = racine LBG_IA_MMORPG
    return Path(__file__).resolve().parents[4] / "Boite à idées" / "pixie_seat.json"


def _px_per_m() -> float:
    return float(TILE_SIZE) / float(TILE_M)


def _origin_px() -> tuple[float, float]:
    return (float(GRID_W * TILE_SIZE) / 2.0, float(GRID_H * TILE_SIZE) / 2.0)


def _tile_center_world_m(gx: int, gy: int) -> tuple[float, float]:
    """Centre d'une tuile (gx,gy) -> monde (x,z) en mètres, origine au centre image."""
    ox, oy = _origin_px()
    cx = gx * TILE_SIZE + TILE_SIZE / 2.0
    cy = gy * TILE_SIZE + TILE_SIZE / 2.0
    ppm = _px_per_m()
    return ((cx - ox) / ppm, (cy - oy) / ppm)


def _px_rect_to_world_m(x1: float, y1: float, x2: float, y2: float) -> dict:
    """Rectangle image(px) -> monde(m) avec origine au centre."""
    ox, oy = _origin_px()
    ppm = _px_per_m()
    return {
        "x": float((x1 - ox) / ppm),
        "z": float((y1 - oy) / ppm),
        "w": float((x2 - x1) / ppm),
        "h": float((y2 - y1) / ppm),
    }


def export_layout_and_masks(
    *,
    grid: list[list[str]],
    seed: int,
    style: str,
    output_layout_path: str,
    output_masks_dir: str,
) -> None:
    """
    Exporte :
    - `layout.json` (objets en coordonnées **monde (m)**)
    - masks PNG (roads/buildings/trees) en coordonnées **image (px)**.
    """
    out_dir = Path(output_masks_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    w_px, h_px = GRID_W * TILE_SIZE, GRID_H * TILE_SIZE
    roads = Image.new("L", (w_px, h_px), 0)
    buildings = Image.new("L", (w_px, h_px), 0)
    trees = Image.new("L", (w_px, h_px), 0)
    dr = ImageDraw.Draw(roads)
    db = ImageDraw.Draw(buildings)
    dt = ImageDraw.Draw(trees)

    # Roads + trees masks from tile grid
    for gy in range(GRID_H):
        for gx in range(GRID_W):
            ch = grid[gy][gx]
            x1 = gx * TILE_SIZE
            y1 = gy * TILE_SIZE
            x2 = x1 + TILE_SIZE
            y2 = y1 + TILE_SIZE
            if ch == "R":
                dr.rectangle([x1, y1, x2, y2], fill=255)
            elif ch == "T":
                cx = x1 + TILE_SIZE // 2
                cy = y1 + TILE_SIZE // 2
                tr = max(2, min(8, TILE_SIZE // 2))
                dt.ellipse([cx - tr, cy - tr, cx + tr, cy + tr], fill=255)

    # Buildings mask + layout rectangles (mêmes tailles que le rendu)
    visited_h: set[tuple[int, int]] = set()
    house_idx = 0
    house_sizes = _house_sizes_for_render()
    buildings_out: list[dict] = []

    for gy in range(GRID_H):
        for gx in range(GRID_W):
            if grid[gy][gx] != "H" or (gx, gy) in visited_h:
                continue
            bw, bh = house_sizes[house_idx % len(house_sizes)]
            house_idx += 1

            bx1 = gx * TILE_SIZE - (bw * TILE_SIZE) // 2 + TILE_SIZE // 2
            by1 = gy * TILE_SIZE - (bh * TILE_SIZE) // 2 + TILE_SIZE // 2
            bx2 = bx1 + bw * TILE_SIZE
            by2 = by1 + bh * TILE_SIZE

            db.rounded_rectangle([bx1, by1, bx2, by2], radius=10, fill=255)
            buildings_out.append(
                {
                    "id": f"b_{house_idx:02d}",
                    "type": "building",
                    "rect_world_m": _px_rect_to_world_m(bx1, by1, bx2, by2),
                    "rect_image_px": {"x1": float(bx1), "y1": float(by1), "x2": float(bx2), "y2": float(by2)},
                }
            )
            visited_h.add((gx, gy))

    roads2 = roads.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(2.0))
    buildings2 = buildings.filter(ImageFilter.GaussianBlur(0.8))
    trees2 = trees.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(1.2))

    roads_path = str(out_dir / "roads.png")
    buildings_path = str(out_dir / "buildings.png")
    trees_path = str(out_dir / "trees.png")
    roads2.save(roads_path)
    buildings2.save(buildings_path)
    trees2.save(trees_path)

    layout: dict = {
        "kind": "village_layout_v1",
        "village_source": "watabou" if VILLAGE_GRID_OVERRIDE is not None else "procedural",
        "seed": int(seed),
        "style": str(style),
        "scale": {
            "tile_m": float(TILE_M),
            "tile_px": int(TILE_SIZE),
            "px_per_m": float(_px_per_m()),
            "origin_px": {"x": float(_origin_px()[0]), "y": float(_origin_px()[1])},
        },
        "grid": {"w": int(GRID_W), "h": int(GRID_H)},
        "image_px": {"w": int(w_px), "h": int(h_px)},
        "world_m": {"w": float(GRID_W * TILE_M), "h": float(GRID_H * TILE_M)},
        "masks": {"roads": roads_path, "buildings": buildings_path, "trees": trees_path},
        "objects": {
            "roads": [],
            "trees": [],
            "buildings": buildings_out,
        },
    }

    for gy in range(GRID_H):
        for gx in range(GRID_W):
            if grid[gy][gx] == "R":
                x_m, z_m = _tile_center_world_m(gx, gy)
                layout["objects"]["roads"].append({"x": float(x_m), "z": float(z_m)})
            elif grid[gy][gx] == "T":
                x_m, z_m = _tile_center_world_m(gx, gy)
                layout["objects"]["trees"].append({"x": float(x_m), "z": float(z_m)})

    with open(output_layout_path, "w", encoding="utf-8") as f:
        json.dump(layout, f, ensure_ascii=False, indent=2)


def write_render_meta(*, output_image_path: str, output_meta_path: str, seed: int, style: str) -> None:
    """
    Export d'un metadata minimal pour verrouiller l'échelle et l'alignement:
    - px_per_m = TILE_SIZE / TILE_M
    - world_m = GRID_* * TILE_M
    - image_px = GRID_* * TILE_SIZE

    Convention d'axes (rendu top-down):
    - x augmente vers la droite (est)
    - z augmente vers le bas (sud)
    - origine (0,0) au centre de l'image
    """
    px_per_m = float(TILE_SIZE) / float(TILE_M)
    meta = {
        "kind": "village_render_meta_v1",
        "seed": int(seed),
        "style": str(style),
        "tile_m": float(TILE_M),
        "tile_px": int(TILE_SIZE),
        "px_per_m": px_per_m,
        "grid": {"w": int(GRID_W), "h": int(GRID_H)},
        "image_px": {"w": int(GRID_W * TILE_SIZE), "h": int(GRID_H * TILE_SIZE)},
        "world_m": {"w": float(GRID_W * TILE_M), "h": float(GRID_H * TILE_M)},
        "origin": {
            "world_m": {"x": 0.0, "z": 0.0},
            "image_px": {"x": float(GRID_W * TILE_SIZE) / 2.0, "y": float(GRID_H * TILE_SIZE) / 2.0},
        },
        "axis": {
            "world": {"x_right": True, "z_down": True},
            "image": {"x_right": True, "y_down": True},
        },
        "mapping": {
            # world(m) -> image(px)
            "image_px_x": "origin.image_px.x + world_m.x * px_per_m",
            "image_px_y": "origin.image_px.y + world_m.z * px_per_m",
        },
        "output": {"image": output_image_path, "meta": output_meta_path},
    }
    with open(output_meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


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

def _paper_texture(size: tuple[int, int], *, seed: int) -> Image.Image:
    """Texture de papier/illustration légère (procédurale, sans assets externes)."""
    random.seed(seed + 1337)
    w, h = size
    base = Image.new("RGB", (w, h), (230, 224, 210))
    n = Image.new("L", (w, h), 0)
    px = n.load()
    for y in range(h):
        for x in range(w):
            # bruit fin + variation douce (évite un rendu trop “plat”)
            v = 128 + random.randint(-12, 12)
            if (x + y) % 11 == 0:
                v += random.randint(-20, 20)
            px[x, y] = max(0, min(255, v))
    n = n.filter(ImageFilter.GaussianBlur(radius=1.2))
    # Teinte “papier”
    tint = Image.new("RGB", (w, h), (245, 238, 224))
    out = ImageChops.multiply(base, tint)
    out = ImageChops.overlay(out, Image.merge("RGB", (n, n, n)))
    return out


def _draw_stone_path(img: Image.Image, *, mask: Image.Image, seed: int) -> None:
    """Dessine une route pavée “organique” à partir d'un masque binaire."""
    random.seed(seed + 4242)
    w, h = img.size
    stones = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(stones)

    # Dallage : petites dalles irrégulières
    for _ in range(int(w * h / 9000)):
        cx = random.randint(0, w - 1)
        cy = random.randint(0, h - 1)
        if mask.getpixel((cx, cy)) < 10:
            continue
        rw = random.randint(8, 18)
        rh = random.randint(6, 14)
        col = (188 + random.randint(-18, 18), 180 + random.randint(-18, 18), 165 + random.randint(-18, 18), 255)
        d.rounded_rectangle([cx - rw, cy - rh, cx + rw, cy + rh], radius=random.randint(2, 6), fill=col)

    stones = stones.filter(ImageFilter.GaussianBlur(radius=0.7))

    # Bordures + poussière
    edge = mask.filter(ImageFilter.MaxFilter(7))
    edge2 = mask.filter(ImageFilter.MinFilter(7))
    border = ImageChops.subtract(edge, edge2).filter(ImageFilter.GaussianBlur(2.0))
    border_rgba = Image.merge("RGBA", (border, border, border, border))
    border_rgba = ImageEnhance.Brightness(border_rgba).enhance(0.65)
    dust = Image.new("RGBA", (w, h), (210, 200, 175, 0))
    dd = ImageDraw.Draw(dust)
    for _ in range(int(w * h / 12000)):
        x = random.randint(0, w - 1)
        y = random.randint(0, h - 1)
        if mask.getpixel((x, y)) < 10:
            continue
        a = random.randint(10, 30)
        dd.ellipse([x - 3, y - 2, x + 3, y + 2], fill=(220, 210, 190, a))
    dust = dust.filter(ImageFilter.GaussianBlur(1.0))

    img.alpha_composite(stones)
    img.alpha_composite(border_rgba)
    img.alpha_composite(dust)


def generate_village_premium(output_path="bourg_palette_map.png", seed=42):
    # On génère la grille de base
    grid = _village_grid(seed)
    
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

    # 3. Dessin des Bâtiments (Tailles variables selon index ; Watabou = 1×1)
    visited_h = set()
    house_idx = 0
    house_sizes = _house_sizes_for_render()

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


def generate_village_illustrated(output_path="bourg_illustrated.png", seed=42):
    """
    V2 : rendu illustré “plus proche d’une map peinte”.
    - routes plus organiques + pavés
    - herbe texturée et palette chaude
    - bâtiments avec ombres douces + toits “tuiles”
    """
    grid = _village_grid(seed)
    w, h = GRID_W * TILE_SIZE, GRID_H * TILE_SIZE

    # Base papier + couche herbe
    base = _paper_texture((w, h), seed=seed).convert("RGBA")
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    img.alpha_composite(base)

    grass = Image.new("RGBA", (w, h), (76, 105, 66, 255))
    gd = ImageDraw.Draw(grass)
    random.seed(seed)
    for _ in range(int(w * h / 600)):
        x = random.randint(0, w - 1)
        y = random.randint(0, h - 1)
        a = random.randint(10, 35)
        col = (70 + random.randint(-8, 12), 110 + random.randint(-12, 10), 60 + random.randint(-10, 12), a)
        gd.ellipse([x - 2, y - 2, x + 2, y + 2], fill=col)
    grass = grass.filter(ImageFilter.GaussianBlur(1.2))
    img.alpha_composite(grass)

    # Masque route (on élargit un peu autour des tuiles 'R' + on “arrondit”)
    road_mask = Image.new("L", (w, h), 0)
    rm = ImageDraw.Draw(road_mask)
    for y in range(GRID_H):
        for x in range(GRID_W):
            if grid[y][x] == "R":
                x1 = x * TILE_SIZE
                y1 = y * TILE_SIZE
                rm.rectangle([x1, y1, x1 + TILE_SIZE, y1 + TILE_SIZE], fill=255)
    road_mask = road_mask.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(2.2))
    _draw_stone_path(img, mask=road_mask, seed=seed)

    draw = ImageDraw.Draw(img)

    # Bâtiments : ombre douce + corps + toit + petites annexes
    visited_h = set()
    house_idx = 0
    house_sizes = _house_sizes_for_render()
    random.seed(seed + 7)

    for gy in range(GRID_H):
        for gx in range(GRID_W):
            if grid[gy][gx] != "H" or (gx, gy) in visited_h:
                continue

            bw, bh = house_sizes[house_idx % len(house_sizes)]
            house_idx += 1

            bx1 = gx * TILE_SIZE - (bw * TILE_SIZE) // 2 + TILE_SIZE // 2
            by1 = gy * TILE_SIZE - (bh * TILE_SIZE) // 2 + TILE_SIZE // 2
            bx2 = bx1 + bw * TILE_SIZE
            by2 = by1 + bh * TILE_SIZE

            # Shadow (couche séparée + blur)
            shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            sd = ImageDraw.Draw(shadow)
            sd.rounded_rectangle([bx1 + 10, by1 + 12, bx2 + 12, by2 + 14], radius=10, fill=(10, 10, 10, 120))
            shadow = shadow.filter(ImageFilter.GaussianBlur(6.0))
            img.alpha_composite(shadow)

            # Base maison (murs)
            wall = (190, 176, 150, 255)
            outline = (95, 78, 62, 255)
            draw.rounded_rectangle([bx1, by1, bx2, by2], radius=10, fill=wall, outline=outline, width=3)

            # Toit (tuile chaude) + reflets
            roof = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            rd = ImageDraw.Draw(roof)
            rx1, ry1, rx2, ry2 = bx1 - 4, by1 - 10, bx2 + 4, by1 + (bh * TILE_SIZE) // 2
            rd.rounded_rectangle([rx1, ry1, rx2, ry2], radius=12, fill=(164, 88, 66, 255), outline=(92, 46, 34, 255), width=3)
            # Stries tuiles
            for k in range(ry1 + 10, ry2 - 4, 10):
                rd.line([rx1 + 10, k, rx2 - 10, k], fill=(190, 120, 98, 80), width=2)
            roof = roof.filter(ImageFilter.GaussianBlur(0.3))
            img.alpha_composite(roof)

            visited_h.add((gx, gy))

    # Arbres : canopées “douces” + ombre au sol
    random.seed(seed + 99)
    for gy in range(GRID_H):
        for gx in range(GRID_W):
            if grid[gy][gx] != "T":
                continue
            cx = gx * TILE_SIZE + TILE_SIZE // 2 + random.randint(-4, 4)
            cy = gy * TILE_SIZE + TILE_SIZE // 2 + random.randint(-4, 4)
            r = TILE_SIZE // 2 + random.randint(4, 10)

            sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            sd = ImageDraw.Draw(sh)
            sd.ellipse([cx - r + 10, cy - r + 12, cx + r + 10, cy + r + 12], fill=(0, 0, 0, 70))
            sh = sh.filter(ImageFilter.GaussianBlur(6))
            img.alpha_composite(sh)

            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(53, 92, 52, 255), outline=(28, 52, 28, 255), width=2)
            draw.ellipse([cx - r + 6, cy - r + 4, cx + r - 2, cy + r - 2], fill=(70, 120, 65, 120))

    # Puits / place (X)
    for gy in range(GRID_H):
        for gx in range(GRID_W):
            if grid[gy][gx] != "X":
                continue
            cx = gx * TILE_SIZE + TILE_SIZE // 2
            cy = gy * TILE_SIZE + TILE_SIZE // 2
            draw.ellipse([cx - 20, cy - 20, cx + 20, cy + 20], fill=(175, 175, 180, 255), outline=(80, 80, 85, 255), width=3)
            draw.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=(45, 55, 70, 255))

    # Final : léger “color grading” chaud
    out = img.convert("RGB")
    out = ImageEnhance.Color(out).enhance(1.08)
    out = ImageEnhance.Contrast(out).enhance(1.06)
    out.save(output_path)
    print(f"Image Illustrated générée : {output_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=str, default="bourg_palette_map.png")
    ap.add_argument("--meta-out", type=str, default="")
    ap.add_argument("--layout-out", type=str, default="")
    ap.add_argument("--masks-dir", type=str, default="")
    ap.add_argument("--style", type=str, default="premium", choices=["premium", "illustrated"])
    ap.add_argument(
        "--procedural",
        action="store_true",
        help="Forcer le village procédural interne (50×40) au lieu de Watabou.",
    )
    ap.add_argument(
        "--watabou-json",
        type=str,
        default="",
        help="Export JSON Watabou (FeatureCollection). Vide = essayer Boite à idées/pixie_seat.json à la racine du dépôt.",
    )
    ap.add_argument(
        "--max-image-px",
        type=int,
        default=1680,
        help="Taille max (px) du plus grand côté du PNG ; TILE_SIZE est réduit pour les grandes grilles.",
    )
    args = ap.parse_args()

    reset_village_to_procedural_defaults()
    if not args.procedural:
        wb = Path(args.watabou_json).expanduser() if str(args.watabou_json).strip() else _default_pixie_seat_json()
        if wb.exists():
            configure_village_from_watabou_json(wb, max_image_px=int(args.max_image_px))
            print(f"Village Watabou: {wb}  →  grille {GRID_W}×{GRID_H}, TILE_SIZE={TILE_SIZE}px")
        else:
            reset_village_to_procedural_defaults()
            print("Watabou JSON introuvable → village procédural 50×40")
    else:
        print("Village procédural (--procedural)")

    if args.style == "premium":
        generate_village_premium(output_path=args.out, seed=args.seed)
    else:
        generate_village_illustrated(output_path=args.out, seed=args.seed)

    meta_out = args.meta_out.strip() if isinstance(args.meta_out, str) else ""
    if not meta_out:
        meta_out = f"{args.out}.meta.json"
    write_render_meta(output_image_path=args.out, output_meta_path=meta_out, seed=args.seed, style=args.style)
    print(f"Meta exporté : {meta_out}")

    layout_out = args.layout_out.strip() if isinstance(args.layout_out, str) else ""
    if not layout_out:
        layout_out = f"{args.out}.layout.json"
    masks_dir = args.masks_dir.strip() if isinstance(args.masks_dir, str) else ""
    if not masks_dir:
        masks_dir = f"{args.out}.masks"
    # On regénère la grille pour exporter le plan (source de vérité gameplay).
    grid = _village_grid(args.seed)
    export_layout_and_masks(grid=grid, seed=args.seed, style=args.style, output_layout_path=layout_out, output_masks_dir=masks_dir)
    print(f"Layout exporté : {layout_out}")
    print(f"Masks exportés : {masks_dir}/(roads|buildings|trees).png")
