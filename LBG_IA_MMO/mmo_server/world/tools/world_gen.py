import numpy as np
from PIL import Image
import math
import noise  # pip install noise
import os

WIDTH = 2048
HEIGHT = 1024
SCALE = 256.0

SEED = 42

def fbm(x, y, octaves=5, persistence=0.5, lacunarity=2.0):
    return noise.pnoise2(
        x / SCALE,
        y / SCALE,
        octaves=octaves,
        persistence=persistence,
        lacunarity=lacunarity,
        repeatx=WIDTH,
        repeaty=HEIGHT,
        base=SEED
    )

def generate_heightmap():
    print("Génération de la heightmap...")
    h = np.zeros((HEIGHT, WIDTH), dtype=np.float32)
    for y in range(HEIGHT):
        lat = (y / (HEIGHT - 1)) * math.pi - math.pi / 2  # -pi/2..pi/2
        lat_factor = math.cos(lat)
        for x in range(WIDTH):
            n = fbm(x, y, octaves=6, persistence=0.5, lacunarity=2.1)
            n = (n + 1.0) / 2.0  # 0..1
            n *= 0.7 + 0.3 * lat_factor
            h[y, x] = n
    # normalisation
    h -= h.min()
    h /= h.max()
    return h

def generate_temperature_and_moisture(heightmap):
    print("Génération climat...")
    temp = np.zeros_like(heightmap)
    moist = np.zeros_like(heightmap)
    for y in range(HEIGHT):
        lat = (y / (HEIGHT - 1)) * math.pi - math.pi / 2
        lat_norm = 1.0 - abs(lat) / (math.pi / 2)  # 1 à l'équateur, 0 aux pôles
        for x in range(WIDTH):
            base_temp = lat_norm
            altitude = heightmap[y, x]
            t = base_temp - altitude * 0.6
            t = np.clip(t, 0.0, 1.0)
            temp[y, x] = t

            m = fbm(x + 10000, y + 10000, octaves=4, persistence=0.6, lacunarity=2.0)
            m = (m + 1.0) / 2.0
            moist[y, x] = m
    return temp, moist

def classify_biome(h, t, m):
    if h < 0.35:
        return "OCEAN"
    if h < 0.38:
        return "BEACH"
    if t < 0.2:
        if h > 0.7:
            return "SNOW_MOUNTAIN"
        return "TUNDRA"
    if m < 0.25:
        if h > 0.6:
            return "ROCKY_DESERT"
        return "DESERT"
    if m > 0.7 and t > 0.6:
        return "JUNGLE"
    if m > 0.5:
        return "FOREST"
    if m > 0.3:
        return "GRASSLAND"
    return "SAVANNA"

PALETTE = {
    "OCEAN_DEEP": (0, 40, 80),
    "OCEAN": (10, 80, 160),
    "BEACH": (232, 217, 168),
    "TUNDRA": (180, 200, 210),
    "SNOW_MOUNTAIN": (245, 245, 250),
    "ROCKY_DESERT": (170, 150, 120),
    "DESERT": (210, 190, 120),
    "JUNGLE": (31, 111, 61),
    "FOREST": (46, 139, 87),
    "GRASSLAND": (120, 180, 90),
    "SAVANNA": (201, 180, 88),
    "MOUNTAIN": (140, 140, 140),
}

def biome_to_color(biome, h):
    if biome == "OCEAN":
        if h < 0.2:
            return PALETTE["OCEAN_DEEP"]
        return PALETTE["OCEAN"]
    if biome == "BEACH":
        return PALETTE["BEACH"]
    if biome == "TUNDRA":
        return PALETTE["TUNDRA"]
    if biome == "SNOW_MOUNTAIN":
        return PALETTE["SNOW_MOUNTAIN"]
    if biome == "ROCKY_DESERT":
        return PALETTE["ROCKY_DESERT"]
    if biome == "DESERT":
        return PALETTE["DESERT"]
    if biome == "JUNGLE":
        return PALETTE["JUNGLE"]
    if biome == "FOREST":
        return PALETTE["FOREST"]
    if biome == "GRASSLAND":
        return PALETTE["GRASSLAND"]
    if biome == "SAVANNA":
        return PALETTE["SAVANNA"]
    if h > 0.75:
        return PALETTE["MOUNTAIN"]
    return (100, 100, 100)

def main():
    heightmap = generate_heightmap()
    temp, moist = generate_temperature_and_moisture(heightmap)

    color_img = Image.new("RGB", (WIDTH, HEIGHT))
    # biome_map = np.empty((HEIGHT, WIDTH), dtype=object)

    print("Classification des biomes et colorisation...")
    for y in range(HEIGHT):
        for x in range(WIDTH):
            h = heightmap[y, x]
            t = temp[y, x]
            m = moist[y, x]
            biome = classify_biome(h, t, m)
            # biome_map[y, x] = biome
            color = biome_to_color(biome, h)
            color_img.putpixel((x, y), color)

    # Sauvegarde
    print("Sauvegarde des images...")
    h_img = Image.fromarray((heightmap * 255).astype(np.uint8), mode="L")
    h_img.save("planet_heightmap.png")
    color_img.save("planet_map.png")
    print("Terminé ! planet_heightmap.png et planet_map.png générés.")

if __name__ == "__main__":
    main()
