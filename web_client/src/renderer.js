/**
 * Moteur de rendu top-down sur Canvas.
 *
 * Attention: le client MMO stable repose sur une caméra monde 2D, le zoom molette
 * et les cartes illustrées. Ne pas le remplacer par un rendu isométrique sans
 * revalider le front `/mmo/`.
 */
export class Renderer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.entities = [];
        this.interpolatedEntities = new Map(); // id -> {x, y, z}
        this.dialogueBubbles = new Map(); // entity id -> {text, speaker, traceId, expiresAt}
        this.selectedEntityId = null;
        this.selectedId = null; // compat historique du client stable
        this.locations = [];
        this.playerId = null;
        this.worldTime = 0;
        this.dayFraction = 0;
        this.cameraX = 0;
        this.cameraY = 0;
        this.cameraZ = 0;
        
        // Échelle top-down : pixels par mètre = 8 * zoom.
        this.tileW = 64;
        this.tileH = 32;
        this.zoom = 1.0;
        
        // Assets
        this.assets = {
            floor: new Image(),
            player: new Image(),
            npc: new Image(),
            worldMap: new Image(),
            villageMap: new Image(),
            tavern: new Image(),
            forge: new Image(),
        };
        this.assetsLoaded = false;
        this.loadAssets();

        window.addEventListener('resize', () => this.resize());
        this.resize();
        this.canvas.addEventListener('wheel', (event) => {
            event.preventDefault();
            const factor = event.deltaY < 0 ? 1.1 : 0.9;
            this.zoom = Math.min(Math.max(this.zoom * factor, 0.001), 10);
        }, { passive: false });
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
            loadImg(this.assets.worldMap, asset('assets/planet_map.png')),
            loadImg(this.assets.villageMap, asset('assets/bourg_palette_map.png')),
            loadImg(this.assets.tavern, asset('assets/tavern_floor.png')),
            loadImg(this.assets.forge, asset('assets/forge_floor.png')),
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
                this.interpolatedEntities.set(ent.id, { x: ent.x, y: ent.y, z: ent.z || 0 });
            }
        }
    }

    updateLocations(locations) {
        this.locations = Array.isArray(locations) ? locations : [];
    }

    setLocations(locations) {
        this.updateLocations(locations);
    }

    setPlayerId(id) {
        this.playerId = id;
    }

    setSelectedEntityId(entityId) {
        this.selectedEntityId = entityId || null;
        this.selectedId = entityId || null;
    }

    getEntityScreenInfo(ent) {
        if (!ent || !ent.id) return null;
        const interp = this.interpolatedEntities.get(ent.id) || {
            x: Number(ent.x || 0),
            y: Number(ent.y || 0),
            z: Number(ent.z || 0),
        };
        const pos = this.worldToScreen(interp.x, interp.z, interp.y);
        const scale = Math.max(this.zoom, 0.1);
        const drawY = pos.y - 10 * 0.25 * scale;
        return { pos, drawY, depth: interp.x + interp.z };
    }

    getNpcAtScreen(screenX, screenY) {
        const world = this.screenToWorld(screenX, screenY);
        let best = null;
        let bestDist = 3.0;
        for (const ent of Array.isArray(this.entities) ? this.entities : []) {
            if (!ent || ent.kind !== "npc") continue;
            const dx = Number(ent.x || 0) - world.x;
            const dz = Number(ent.z || 0) - world.z;
            const dist = Math.sqrt(dx * dx + dz * dz);
            if (dist < bestDist) {
                best = ent;
                bestDist = dist;
            }
        }
        return best;
    }

    setDialogueBubble(entityId, text, opts = {}) {
        if (!entityId || typeof text !== "string" || !text.trim()) return;
        const ttlMs = Number.isFinite(opts.ttlMs) ? opts.ttlMs : 9000;
        this.dialogueBubbles.set(entityId, {
            text: text.trim(),
            speaker: typeof opts.speaker === "string" ? opts.speaker.trim() : "",
            traceId: typeof opts.traceId === "string" ? opts.traceId.trim() : "",
            kind: typeof opts.kind === "string" ? opts.kind.trim() : "npc",
            expiresAt: Date.now() + ttlMs,
        });
    }

    pruneDialogueBubbles(now = Date.now()) {
        for (const [entityId, bubble] of this.dialogueBubbles.entries()) {
            if (!bubble || bubble.expiresAt <= now) {
                this.dialogueBubbles.delete(entityId);
            }
        }
    }

    wrapText(text, maxChars = 32, maxLines = 4) {
        const words = String(text || "").replace(/\s+/g, " ").trim().split(" ");
        const lines = [];
        let line = "";
        for (const word of words) {
            const candidate = line ? `${line} ${word}` : word;
            if (candidate.length > maxChars && line) {
                lines.push(line);
                line = word;
            } else {
                line = candidate;
            }
            if (lines.length >= maxLines) break;
        }
        if (line && lines.length < maxLines) lines.push(line);
        if (lines.length === maxLines && words.join(" ").length > lines.join(" ").length) {
            lines[maxLines - 1] = `${lines[maxLines - 1].replace(/[.…]+$/, "")}...`;
        }
        return lines;
    }

    drawDialogueBubble(ent, pos, drawY) {
        const bubble = this.dialogueBubbles.get(ent.id);
        if (!bubble) return;

        const ctx = this.ctx;
        const lines = this.wrapText(bubble.text);
        if (!lines.length) return;

        const title = bubble.speaker || ent.name || "PNJ";
        ctx.save();
        ctx.font = '600 12px "Inter", sans-serif';
        const maxTextWidth = Math.max(
            ctx.measureText(title).width,
            ...lines.map((line) => ctx.measureText(line).width),
        );
        const padX = 12;
        const padY = 8;
        const lineH = 15;
        const titleH = 13;
        const width = Math.min(300, Math.max(120, maxTextWidth + padX * 2));
        const height = padY * 2 + titleH + lines.length * lineH + 4;
        const x = Math.max(12, Math.min(this.canvas.width - width - 12, pos.x - width / 2));
        const y = Math.max(12, drawY - 86 - height);
        const accent = bubble.kind === "pending"
            ? "#ffea00"
            : bubble.kind === "world_event"
                ? "#7CFF6B"
                : "#00f2ff";

        ctx.shadowBlur = 18;
        ctx.shadowColor = "rgba(0, 242, 255, 0.35)";
        ctx.fillStyle = "rgba(8, 10, 22, 0.88)";
        ctx.strokeStyle = accent;
        ctx.lineWidth = 1.5;

        const radius = 12;
        ctx.beginPath();
        ctx.moveTo(x + radius, y);
        ctx.lineTo(x + width - radius, y);
        ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
        ctx.lineTo(x + width, y + height - radius);
        ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
        ctx.lineTo(x + width / 2 + 10, y + height);
        ctx.lineTo(pos.x, y + height + 10);
        ctx.lineTo(x + width / 2 - 10, y + height);
        ctx.lineTo(x + radius, y + height);
        ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
        ctx.lineTo(x, y + radius);
        ctx.quadraticCurveTo(x, y, x + radius, y);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();

        ctx.shadowBlur = 0;
        ctx.textAlign = "left";
        ctx.fillStyle = accent;
        ctx.font = '800 11px "Inter", sans-serif';
        ctx.fillText(title.toUpperCase(), x + padX, y + padY + 10);

        ctx.fillStyle = "#f4f7ff";
        ctx.font = '600 12px "Inter", sans-serif';
        lines.forEach((line, i) => {
            ctx.fillText(line, x + padX, y + padY + titleH + 8 + i * lineH);
        });
        ctx.restore();
    }

    worldToScreen(x, z, y = 0) {
        const scale = 8 * this.zoom;
        const dx = x - this.cameraX;
        const dz = z - this.cameraZ;
        return {
            x: this.canvas.width / 2 + dx * scale,
            y: this.canvas.height / 2 + dz * scale - (y - this.cameraY) * scale,
        };
    }

    screenToWorld(screenX, screenY) {
        const scale = 8 * this.zoom;
        return {
            x: this.cameraX + (screenX - this.canvas.width / 2) / scale,
            y: 0,
            z: this.cameraZ + (screenY - this.canvas.height / 2) / scale,
        };
    }

    interpolate() {
        const smoothing = 0.15;
        for (const ent of this.entities) {
            let interpolated = this.interpolatedEntities.get(ent.id);
            if (!interpolated) {
                interpolated = { x: ent.x, y: ent.y, z: ent.z || 0 };
                this.interpolatedEntities.set(ent.id, interpolated);
                continue;
            }
            let dx = ent.x - interpolated.x;
            if (dx > 102400 / 2) dx -= 102400;
            if (dx < -102400 / 2) dx += 102400;
            interpolated.x += dx * smoothing;
            interpolated.y += (ent.y - interpolated.y) * smoothing;
            interpolated.z += ((ent.z || 0) - interpolated.z) * smoothing;
            if (interpolated.x > 102400 / 2) interpolated.x -= 102400;
            if (interpolated.x < -102400 / 2) interpolated.x += 102400;
        }
    }

    updateCamera() {
        if (!this.playerId) return;
        const player = this.interpolatedEntities.get(this.playerId);
        if (!player) return;
        this.cameraX += (player.x - this.cameraX) * 0.2;
        this.cameraY += (player.y - this.cameraY) * 0.2;
        this.cameraZ += (player.z - this.cameraZ) * 0.2;
    }

    drawFloor(floorY = 0) {
        const ctx = this.ctx;
        const range = 20;
        const cell = 10 * (8 * this.zoom);
        ctx.lineWidth = 1;
        ctx.strokeStyle = "rgba(0, 242, 255, 0.1)";
        for (let x = -range; x <= range; x += 2) {
            for (let z = -range; z <= range; z += 2) {
                const pos = this.worldToScreen(x * 10, z * 10, floorY);
                ctx.beginPath();
                ctx.rect(pos.x - cell / 2, pos.y - cell / 2, cell, cell);
                ctx.fillStyle = "rgba(0, 242, 255, 0.02)";
                ctx.fill();
                ctx.stroke();
            }
        }
    }

    drawLocations(floorY = 0) {
        const ctx = this.ctx;
        const scale = 8 * this.zoom;
        for (const loc of this.locations) {
            if (!loc || loc.type === "planet" || Math.abs((loc.y || 0) - floorY) > 2) continue;
            const pos = this.worldToScreen(loc.x, loc.z, loc.y || 0);
            const w = (loc.w || 2) * scale;
            const h = (loc.h || 2) * scale;
            const color = loc.type === "room" ? "255, 150, 0" : "0, 242, 255";
            if (loc.id === "auberge_salle_commune" && this.assets.tavern.complete) {
                ctx.drawImage(this.assets.tavern, pos.x - w / 2, pos.y - h / 2, w, h);
            } else if (loc.id === "forge" && this.assets.forge.complete) {
                ctx.drawImage(this.assets.forge, pos.x - w / 2, pos.y - h / 2, w, h);
                ctx.strokeStyle = `rgba(${color}, 0.3)`;
                ctx.lineWidth = 1;
                ctx.strokeRect(pos.x - w / 2, pos.y - h / 2, w, h);
            }
            if (this.zoom > 0.01) {
                ctx.fillStyle = "rgba(255, 255, 255, 0.8)";
                ctx.font = `600 ${Math.max(10, 14 * this.zoom)}px "Inter", sans-serif`;
                ctx.textAlign = "center";
                ctx.fillText(loc.name || "", pos.x, pos.y - h / 2 - 5);
            }
        }
    }

    drawPlanetLabel() {
        const ctx = this.ctx;
        const scale = 8 * this.zoom;
        for (const loc of this.locations) {
            if (!loc || loc.type !== "planet" || this.zoom >= 0.05) continue;
            const pos = this.worldToScreen(loc.x || 0, loc.z || 0);
            ctx.fillStyle = "rgba(255, 255, 255, 0.5)";
            ctx.font = `italic 600 ${Math.round(24 * this.zoom * 20)}px "Inter", sans-serif`;
            ctx.textAlign = "center";
            ctx.fillText(loc.name || "", pos.x, pos.y - 500 * scale);
        }
    }

    drawEntity(ent, bobbing = 0) {
        const ctx = this.ctx;
        const interp = this.interpolatedEntities.get(ent.id);
        if (!interp) return;

        const isMoving = Math.sqrt((ent.vx || 0) ** 2 + (ent.vz || 0) ** 2) > 0.5;
        const bob = isMoving ? bobbing : 0;
        const pos = this.worldToScreen(interp.x, interp.z, interp.y + bob);
        const isMe = ent.id === this.playerId;
        const isNpc = ent.kind === "npc";
        const isSelected = isNpc && (ent.id === this.selectedEntityId || ent.id === this.selectedId);
        const scale = Math.max(this.zoom, 0.1);
        const spriteScale = 0.25;

        if (isSelected) {
            ctx.save();
            ctx.strokeStyle = "#ffffff";
            ctx.shadowColor = "rgba(255, 255, 255, 0.9)";
            ctx.shadowBlur = 14 * scale;
            ctx.lineWidth = 2 * scale;
            ctx.setLineDash([2 * scale, 2 * scale]);
            ctx.beginPath();
            ctx.ellipse(pos.x, pos.y, 20 * spriteScale * scale, 10 * spriteScale * scale, 0, 0, Math.PI * 2);
            ctx.stroke();
            ctx.setLineDash([]);
            ctx.restore();
        }

        ctx.fillStyle = 'rgba(0, 0, 0, 0.6)';
        ctx.beginPath();
        ctx.ellipse(pos.x, pos.y, 12 * spriteScale * scale, 6 * spriteScale * scale, 0, 0, Math.PI * 2);
        ctx.fill();
        
        const color = isMe ? '#00f2ff' : (isNpc ? '#ffea00' : '#ff0055');
        const glowColor = isMe ? 'rgba(0, 242, 255, 0.8)' : (isNpc ? 'rgba(255, 234, 0, 0.8)' : 'rgba(255, 0, 85, 0.8)');
        const yOffset = (ent.x + ent.y) % 1 > 0.5 ? 2 * scale : -2 * scale;
        const drawY = pos.y - 10 * spriteScale * scale + yOffset;

        ctx.shadowBlur = 10 * scale;
        ctx.shadowColor = glowColor;
        ctx.fillStyle = 'rgba(10, 10, 20, 0.8)';
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5 * scale;

        ctx.beginPath();
        ctx.moveTo(pos.x, drawY - 25 * spriteScale * scale);
        ctx.lineTo(pos.x + 10 * spriteScale * scale, drawY);
        ctx.lineTo(pos.x, drawY + 10 * spriteScale * scale);
        ctx.lineTo(pos.x - 10 * spriteScale * scale, drawY);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        
        ctx.fillStyle = color;
        ctx.shadowBlur = 15 * scale;
        ctx.beginPath();
        ctx.moveTo(pos.x, drawY - 10 * spriteScale * scale);
        ctx.lineTo(pos.x + 4 * spriteScale * scale, drawY);
        ctx.lineTo(pos.x, drawY + 5 * spriteScale * scale);
        ctx.lineTo(pos.x - 4 * spriteScale * scale, drawY);
        ctx.closePath();
        ctx.fill();
        
        ctx.shadowBlur = 0;
        ctx.fillStyle = isMe ? '#00f2ff' : 'white';
        ctx.font = `${isMe ? 800 : 600} ${Math.max(6, 11 * scale)}px "Inter", sans-serif`;
        ctx.textAlign = "center";
        
        ctx.shadowColor = 'rgba(0,0,0,0.8)';
        ctx.shadowBlur = 4 * scale;
        ctx.shadowOffsetX = 1 * scale;
        ctx.shadowOffsetY = 1 * scale;
        ctx.fillText(ent.name || "Inconnu", pos.x, drawY - 35 * spriteScale * scale - 5 * scale);
        
        ctx.shadowBlur = 0;
        ctx.shadowOffsetX = 0;
        ctx.shadowOffsetY = 0;

        this.drawDialogueBubble(ent, pos, drawY);
    }

    drawWorldMap() {
        if (!this.assets.worldMap.complete) return;
        const ctx = this.ctx;
        const scale = 8 * this.zoom;
        const pos = this.worldToScreen(0, 0);
        const w = 102400 * scale;
        const h = 51200 * scale;
        ctx.save();
        ctx.drawImage(this.assets.worldMap, pos.x - w / 2, pos.y - h / 2, w, h);
        ctx.restore();
    }

    drawVillageMap() {
        if (!this.assets.villageMap.complete || this.zoom < 0.005) return;
        const ctx = this.ctx;
        const scale = 8 * this.zoom;
        const pos = this.worldToScreen(0, 0);
        const w = 100 * scale;
        const h = 80 * scale;
        ctx.save();
        ctx.globalAlpha = Math.min(1, (this.zoom - 0.005) * 20);
        ctx.drawImage(this.assets.villageMap, pos.x - w / 2, pos.y - h / 2, w, h);
        ctx.restore();
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
            this.updateCamera();
            this.pruneDialogueBubbles();

            this.drawWorldMap();
            this.drawVillageMap();
            this.drawPlanetLabel();
            const player = this.interpolatedEntities.get(this.playerId);
            const floorY = Math.floor(((player && player.y) || 0) / 4) * 4;
            this.drawFloor(floorY);
            this.drawLocations(floorY);

            // Trier les entités par profondeur
            const sortedEntities = [...this.entities]
                .filter((ent) => {
                    const pos = this.interpolatedEntities.get(ent.id);
                    return pos && Math.abs(pos.y - floorY) < 2.5;
                })
                .sort((a, b) => {
                    const posA = this.interpolatedEntities.get(a.id);
                    const posB = this.interpolatedEntities.get(b.id);
                    if (!posA || !posB) return 0;
                    return (posA.x + posA.z) - (posB.x + posB.z);
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
