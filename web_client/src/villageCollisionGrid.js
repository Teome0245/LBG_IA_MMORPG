/**
 * Grille collisions village (`watabou_grid_v1`) — mêmes règles que le serveur :
 * tuiles `.` et `R` franchissables ; hors carte = non franchissable.
 */

const WALKABLE = new Set([".", "R"]);

export class VillageCollisionGrid {
    /**
     * @param {object} data — JSON racine `watabou_grid_v1`
     */
    constructor(data) {
        if (!data || data.kind !== "watabou_grid_v1") {
            throw new Error("attendu watabou_grid_v1");
        }
        const scale = data.scale || {};
        this.tileM = Number(scale.tile_m) || 2.0;
        if (this.tileM <= 0) throw new Error("tile_m invalide");
        this.paddingTiles = Number.isFinite(Number(scale.padding_tiles)) ? Number(scale.padding_tiles) : 0;
        if (!Number.isFinite(this.paddingTiles) || this.paddingTiles < 0) this.paddingTiles = 0;
        const b = data.bounds_world_m || {};
        this.originX = Number(b.min_x);
        this.originZ = Number(b.min_z);
        const g = data.grid || {};
        this.w = Number(g.w);
        this.h = Number(g.h);
        const rows = g.rows;
        if (!Array.isArray(rows) || rows.length !== this.h) {
            throw new Error("grid.rows invalide");
        }
        this.rows = rows;
        this.sourcePath =
            typeof data.source_path === "string"
                ? data.source_path
                : typeof data.source?.path === "string"
                  ? data.source.path
                  : "";
    }

    worldToTile(x, z) {
        const gx = Math.floor((x - this.originX) / this.tileM);
        const gz = Math.floor((z - this.originZ) / this.tileM);
        if (gx < 0 || gz < 0 || gx >= this.w || gz >= this.h) return null;
        return { gx, gz };
    }

    terrainAtWorldM(x, z) {
        const t = this.worldToTile(x, z);
        if (!t) return { ch: null, gx: null, gz: null };
        const ch = this.rows[t.gz].charAt(t.gx);
        return { ch, gx: t.gx, gz: t.gz };
    }

    isWalkableWorldM(x, z) {
        const { ch } = this.terrainAtWorldM(x, z);
        if (ch == null) return false;
        return WALKABLE.has(ch);
    }
}

/**
 * Essaie plusieurs bases HTTP (ports usuel mmo_server) pour charger la grille.
 * @param {string} host — même hôte que le WS (sans schéma)
 */
export async function loadVillageCollisionGridFromMmoServer(host) {
    const h = typeof host === "string" ? host.trim() : "";
    if (!h) return null;
    const ports = [8050, 8000, 8010, 8088, 8888];
    for (const port of ports) {
        const url = `http://${h}:${port}/v1/world/collision-grid`;
        try {
            const r = await fetch(url, { method: "GET", credentials: "omit" });
            if (!r.ok) continue;
            const j = await r.json();
            if (!j || j.loaded !== true || j.kind !== "watabou_grid_v1") continue;
            const g = new VillageCollisionGrid(j);
            console.info("[collision] grille chargée", url, `${g.w}×${g.h}`, g.tileM, "m/tuile");
            return g;
        } catch (_) {
            /* CORS, réseau, serveur arrêté */
        }
    }
    return null;
}
