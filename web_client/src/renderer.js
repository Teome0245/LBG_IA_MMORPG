/**
 * Moteur de rendu isométrique 2D sur Canvas.
 */
export class Renderer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.entities = [];
        this.interpolatedEntities = new Map(); // id -> {x, y, z}
        this.locations = [];
        this.playerId = null;
        this.worldTime = 0;
        this.dayFraction = 0;
        
        // Paramètres isométriques
        this.tileW = 64;
        this.tileH = 32;
        this.zoom = 1.0;
        
        // Assets
        this.assets = {
            floor: new Image(),
            player: new Image(),
            npc: new Image(),
            planetMap: new Image(),
            villageMap: new Image(),
        };
        this.assetsLoaded = false;
        this.loadAssets();

        window.addEventListener('resize', () => this.resize());
        this.resize();
    }

    async loadAssets() {
        const loadImg = (img, src) => new Promise(resolve => {
            img.onload = resolve;
            img.onerror = () => {
                console.error(`Erreur de chargement de l'image: ${src}`);
                resolve(); // Ne pas bloquer indéfiniment
            };
            img.src = src;
        });

        // IMPORTANT: le client est servi sous /mmo/ en prod (base=/mmo/ au build Vite).
        // On utilise BASE_URL (vite) pour éviter les chemins absolus /assets/... qui cassent sous un sous-dossier.
        const baseRel = (import.meta && import.meta.env && import.meta.env.BASE_URL) ? String(import.meta.env.BASE_URL) : "/";
        // new URL() exige une base absolue (sinon TypeError). BASE_URL Vite est souvent "/mmo/".
        const baseAbs = new URL(baseRel.replace(/^\s+|\s+$/g, ""), window.location.origin + "/").toString();
        const asset = (p) => new URL(String(p || "").replace(/^\//, ""), baseAbs).toString();

        await Promise.all([
            loadImg(this.assets.floor, asset('assets/tile_floor.png')),
            loadImg(this.assets.player, asset('assets/char_player.png')),
            loadImg(this.assets.npc, asset('assets/char_npc.png')),
            loadImg(this.assets.planetMap, asset('assets/planet_map.png')),
            loadImg(this.assets.villageMap, asset('assets/bourg_palette_map.png')),
        ]);
        this.assetsLoaded = true;
        console.log("Assets graphiques chargés ou ignorés en cas d'erreur");
    }

    resize() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }

    updateState(entities, worldTime, dayFraction) {
        this.entities = entities;
        this.worldTime = worldTime;
        this.dayFraction = dayFraction;

        // Initialiser l'interpolation pour les nouvelles entités
        for (const ent of entities) {
            if (!this.interpolatedEntities.has(ent.id)) {
                // Convention monde (serveur WS) : x,z = plan horizontal ; y = altitude.
                // Convention renderer : x,y = plan horizontal ; z = altitude.
                this.interpolatedEntities.set(ent.id, { x: ent.x, y: (ent.z || 0), z: (ent.y || 0) });
            }
        }
    }

    updateLocations(locations) {
        this.locations = Array.isArray(locations) ? locations : [];
    }

    setPlayerId(id) {
        this.playerId = id;
    }

    worldToScreen(x, y, z = 0) {
        const screenX = (x / 2 - y / 2) * this.tileW;
        const screenY = (x / 4 + y / 4 - z / 2) * this.tileH;
        
        return {
            x: this.canvas.width / 2 + screenX,
            y: this.canvas.height / 2 + screenY
        };
    }

    interpolate() {
        const smoothing = 0.15; // Facteur d'interpolation
        for (const ent of this.entities) {
            const interpolated = this.interpolatedEntities.get(ent.id);
            if (interpolated) {
                interpolated.x += (ent.x - interpolated.x) * smoothing;
                interpolated.y += (((ent.z || 0) - interpolated.y) * smoothing);
                interpolated.z += (((ent.y || 0) - interpolated.z) * smoothing);
            }
        }
    }

    drawMaps() {
        const ctx = this.ctx;
        const w = this.canvas.width;
        const h = this.canvas.height;
        const img = this.assets.planetMap;
        if (!img || !img.width || !img.height) return;

        // Fond carte monde (semi transparent)
        const scale = Math.min(w / img.width, h / img.height) * 0.85;
        const dw = img.width * scale;
        const dh = img.height * scale;
        const dx = (w - dw) / 2;
        const dy = (h - dh) / 2;
        ctx.save();
        ctx.globalAlpha = 0.22;
        ctx.drawImage(img, dx, dy, dw, dh);
        ctx.restore();
    }

    drawLocations() {
        const ctx = this.ctx;
        const locs = Array.isArray(this.locations) ? this.locations : [];
        if (!locs.length) return;
        ctx.save();
        ctx.lineWidth = 1.0;
        ctx.strokeStyle = "rgba(255, 60, 180, 0.35)";
        ctx.fillStyle = "rgba(255, 60, 180, 0.08)";
        for (const loc of locs) {
            if (!loc || typeof loc !== "object") continue;
            const x = Number(loc.x);
            const z = Number(loc.z);
            const w = Number(loc.w || loc.width || 0);
            const d = Number(loc.h || loc.height || 0);
            if (!Number.isFinite(x) || !Number.isFinite(z) || !Number.isFinite(w) || !Number.isFinite(d) || w <= 0 || d <= 0) continue;

            const hw = w / 2.0;
            const hd = d / 2.0;
            const p1 = this.worldToScreen(x - hw, z - hd, 0);
            const p2 = this.worldToScreen(x + hw, z - hd, 0);
            const p3 = this.worldToScreen(x + hw, z + hd, 0);
            const p4 = this.worldToScreen(x - hw, z + hd, 0);

            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.lineTo(p3.x, p3.y);
            ctx.lineTo(p4.x, p4.y);
            ctx.closePath();
            ctx.fill();
            ctx.stroke();
        }
        ctx.restore();
    }

    drawFloor() {
        const ctx = this.ctx;
        const range = 15; // Vue plus large
        const tw = this.tileW;
        const th = this.tileH;

        // Rendu volontairement plus contrasté pour debug/visibilité.
        ctx.lineWidth = 1.5;
        ctx.strokeStyle = 'rgba(0, 242, 255, 0.35)'; // Cyan néon

        // Dessiner une grille isométrique stylisée
        for (let x = -range; x <= range; x++) {
            for (let y = -range; y <= range; y++) {
                const pos = this.worldToScreen(x, y, 0);
                
                ctx.beginPath();
                ctx.moveTo(pos.x, pos.y - th/2);
                ctx.lineTo(pos.x + tw/2, pos.y);
                ctx.lineTo(pos.x, pos.y + th/2);
                ctx.lineTo(pos.x - tw/2, pos.y);
                ctx.closePath();
                
                // Remplissage avec un léger dégradé pour la profondeur
                const dist = Math.sqrt(x*x + y*y);
                const alpha = Math.max(0, 0.12 - dist * 0.004);
                ctx.fillStyle = `rgba(0, 242, 255, ${alpha})`;
                ctx.fill();
                
                // Ne dessiner les lignes que si on est proche du centre pour un effet de fondu
                if (dist < range - 2) {
                    ctx.stroke();
                }
            }
        }

        // Marqueur centre (debug)
        const c = this.worldToScreen(0, 0, 0);
        ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
        ctx.beginPath();
        ctx.arc(c.x, c.y, 2.5, 0, Math.PI * 2);
        ctx.fill();
    }

    drawEntity(ent, bobbing = 0) {
        const ctx = this.ctx;
        const interp = this.interpolatedEntities.get(ent.id);
        if (!interp) return;

        const pos = this.worldToScreen(interp.x, interp.y, interp.z);
        const isMe = ent.id === this.playerId;
        const isNpc = ent.kind === "npc";

        // Ombre
        ctx.fillStyle = 'rgba(0, 0, 0, 0.6)';
        ctx.beginPath();
        ctx.ellipse(pos.x, pos.y, 14, 7, 0, 0, Math.PI * 2);
        ctx.fill();

        // Animation de flottement
        const yOffset = (ent.x + ent.y) % 1 > 0.5 ? bobbing : -bobbing;
        const drawY = pos.y - 20 + yOffset;
        
        // Couleurs Néon
        const color = isMe ? '#00f2ff' : (isNpc ? '#ffea00' : '#ff0055');
        const glowColor = isMe ? 'rgba(0, 242, 255, 0.8)' : (isNpc ? 'rgba(255, 234, 0, 0.8)' : 'rgba(255, 0, 85, 0.8)');

        // Forme géométrique premium (Losange allongé)
        ctx.shadowBlur = 15;
        ctx.shadowColor = glowColor;
        ctx.fillStyle = 'rgba(10, 10, 20, 0.8)';
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;

        ctx.beginPath();
        ctx.moveTo(pos.x, drawY - 25); // Top
        ctx.lineTo(pos.x + 12, drawY);   // Right
        ctx.lineTo(pos.x, drawY + 10);   // Bottom
        ctx.lineTo(pos.x - 12, drawY);   // Left
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        
        // Cœur lumineux
        ctx.fillStyle = color;
        ctx.shadowBlur = 20;
        ctx.beginPath();
        ctx.moveTo(pos.x, drawY - 10);
        ctx.lineTo(pos.x + 4, drawY);
        ctx.lineTo(pos.x, drawY + 5);
        ctx.lineTo(pos.x - 4, drawY);
        ctx.closePath();
        ctx.fill();
        
        ctx.shadowBlur = 0;

        // Nom de l'entité
        ctx.fillStyle = 'white';
        ctx.font = '600 11px "Inter", sans-serif';
        ctx.textAlign = 'center';
        
        // Si c'est le joueur, on le met en évidence
        if (isMe) {
            ctx.fillStyle = '#00f2ff';
            ctx.font = '800 12px "Inter", sans-serif';
        }
        
        // Ombre sous le texte pour la lisibilité
        ctx.shadowColor = 'rgba(0,0,0,0.8)';
        ctx.shadowBlur = 4;
        ctx.shadowOffsetX = 1;
        ctx.shadowOffsetY = 1;
        ctx.fillText(ent.name || "Inconnu", pos.x, drawY - 35);
        
        ctx.shadowBlur = 0;
        ctx.shadowOffsetX = 0;
        ctx.shadowOffsetY = 0;
    }


    render(bobbing = 0) {
        try {
            const ctx = this.ctx;
            ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

            if (!this.assetsLoaded) {
                ctx.fillStyle = 'white';
                ctx.textAlign = 'center';
                ctx.fillText("Chargement des assets...", this.canvas.width / 2, this.canvas.height / 2);
                return;
            }

            // Interpolation des positions
            this.interpolate();

            this.drawMaps();
            this.drawFloor();
            this.drawLocations();

            // Trier les entités par profondeur
            const sortedEntities = [...this.entities].sort((a, b) => {
                const posA = this.interpolatedEntities.get(a.id);
                const posB = this.interpolatedEntities.get(b.id);
                if (!posA || !posB) return 0;
                return (posA.x + posA.y) - (posB.x + posB.y);
            });

            for (const ent of sortedEntities) {
                this.drawEntity(ent, bobbing);
            }

            // Debug minimal si le serveur n'envoie aucune entité
            if (!sortedEntities.length) {
                ctx.fillStyle = 'rgba(255,255,255,0.8)';
                ctx.font = '600 12px "Inter", sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText("0 entité reçue (world_tick.entities vide)", this.canvas.width / 2, this.canvas.height / 2 + 18);
            }
        } catch (e) {
            const consoleLogs = document.getElementById('console-logs');
            if (consoleLogs) {
                const log = document.createElement('div');
                log.className = 'log error';
                log.textContent = `[RENDER ERROR] ${e.message}`;
                consoleLogs.appendChild(log);
            }
            throw e;
        }
    }
}
