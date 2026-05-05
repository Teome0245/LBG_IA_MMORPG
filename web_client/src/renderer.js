/**
 * Moteur de rendu top-down sur Canvas.
 *
 * Attention: le client MMO stable repose sur une caméra monde 2D, le zoom molette
 * et les cartes illustrées. Ne pas le remplacer par un rendu isométrique sans
 * revalider le front `/mmo/`.
 */
export class Renderer {
    /** Limite d’affichage du corps de bulle (lignes visibles) — tronque les répliques extrêmement longues. */
    static MAX_BUBBLE_BODY_LINES = 26;

    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.entities = [];
        this.interpolatedEntities = new Map(); // id -> {x, y, z}
        /** @type {Map<string, object>} entity id -> bulle (texte, interlocuteur, sous-titre rôle, écho joueur en attente, etc.) */
        this.dialogueBubbles = new Map();
        this.selectedEntityId = null;
        this.selectedId = null; // compat historique du client stable
        this.locations = [];
        this.playerId = null;
        this.worldTime = 0;
        this.dayFraction = 0;
        this.cameraX = 0;
        this.cameraY = 0;
        this.cameraZ = 0;
        // BBox monde (m) de la carte village, si connue (depuis collision-grid).
        this.villageMapBounds = null;
        // Correction orientation/échelle du fond Watabou (image “jolie”) pour coller à la grille collisions.
        this.villageMapPrettyFlipZ = false;
        this.villageMapPrettyScale = 1.0;
        // Debug overlay (calque “moche” / grille)
        this.villageMapOverlayFlipZ = false;
        // Debug : superposition de deux fonds (joli + grille) pour mesurer un décalage.
        this.villageMapOverlayEnabled = false;
        this.villageMapOverlayAlpha = 0.5;
        this.villageMapOverlayScale = 1.0;
        // Décalage manuel (m) du calque overlay uniquement (debug alignement).
        this.villageMapOverlayOffsetX = 0.0;
        this.villageMapOverlayOffsetZ = 0.0;
        
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
            // villageMapPretty: rendu “joli” (Watabou PNG), villageMapGrid: rendu “moche” (premium/grille)
            villageMapPretty: new Image(),
            villageMapGrid: new Image(),
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

        const loadImgOk = (img, src) =>
            new Promise((resolve) => {
                img.onload = () => resolve(true);
                img.onerror = () => {
                    console.error(`Erreur de chargement de l'image: ${src}`);
                    resolve(false);
                };
                img.src = src;
            });

        // IMPORTANT: le client est servi sous /mmo/ en prod (base=/mmo/ au build Vite).
        // On utilise BASE_URL (vite) pour éviter les chemins absolus /assets/... qui cassent sous un sous-dossier.
        const baseRel = (import.meta && import.meta.env && import.meta.env.BASE_URL) ? String(import.meta.env.BASE_URL) : "/";
        // new URL() exige une base absolue (sinon TypeError). BASE_URL Vite est souvent "/mmo/".
        const baseAbs = new URL(baseRel.replace(/^\s+|\s+$/g, ""), window.location.origin + "/").toString();
        const asset = (p) => new URL(String(p || "").replace(/^\//, ""), baseAbs).toString();

        // On préfère une version “clean” sans cartouche (sinon le flip du fond l'affiche à l'envers).
        const okPretty = await loadImgOk(this.assets.villageMapPretty, asset("assets/pixie_seat_clean.png"));
        const okGrid = await loadImgOk(this.assets.villageMapGrid, asset("assets/bourg_palette_map.png"));

        await Promise.all([
            loadImg(this.assets.floor, asset("assets/tile_floor.png")),
            loadImg(this.assets.player, asset("assets/char_player.png")),
            loadImg(this.assets.npc, asset("assets/char_npc.png")),
            loadImg(this.assets.worldMap, asset("assets/planet_map.png")),
            okPretty ? Promise.resolve() : loadImg(this.assets.villageMapPretty, asset("assets/bourg_palette_map.png")),
            okGrid ? Promise.resolve() : Promise.resolve(),
            loadImg(this.assets.tavern, asset("assets/tavern_floor.png")),
            loadImg(this.assets.forge, asset("assets/forge_floor.png")),
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

    /**
     * @param {{min_x:number,min_z:number,max_x:number,max_z:number}|null} bounds
     */
    setVillageMapBounds(bounds) {
        if (!bounds) {
            this.villageMapBounds = null;
            return;
        }
        const b = bounds;
        const nums = [b.min_x, b.min_z, b.max_x, b.max_z].map((v) => Number(v));
        if (nums.some((v) => !Number.isFinite(v))) {
            this.villageMapBounds = null;
            return;
        }
        this.villageMapBounds = {
            min_x: nums[0],
            min_z: nums[1],
            max_x: nums[2],
            max_z: nums[3],
        };
    }

    setVillageMapOverlayFlipZ(enabled) {
        this.villageMapOverlayFlipZ = enabled === true;
    }

    setVillageMapPrettyTransform({ flipZ = false, scale = 1.0 } = {}) {
        this.villageMapPrettyFlipZ = flipZ === true;
        const s = Number(scale);
        this.villageMapPrettyScale = Number.isFinite(s) ? Math.max(0.2, Math.min(5.0, s)) : 1.0;
    }

    setVillageMapOverlay(enabled, alpha = 0.5) {
        this.villageMapOverlayEnabled = enabled === true;
        const a = Number(alpha);
        this.villageMapOverlayAlpha = Number.isFinite(a) ? Math.max(0, Math.min(1, a)) : 0.5;
    }

    setVillageMapOverlayScale(scale = 1.0) {
        const s = Number(scale);
        this.villageMapOverlayScale = Number.isFinite(s) ? Math.max(0.2, Math.min(5.0, s)) : 1.0;
    }

    setVillageMapOverlayOffset(dx = 0.0, dz = 0.0) {
        const x = Number(dx);
        const z = Number(dz);
        this.villageMapOverlayOffsetX = Number.isFinite(x) ? x : 0.0;
        this.villageMapOverlayOffsetZ = Number.isFinite(z) ? z : 0.0;
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
            const interp = this.interpolatedEntities.get(ent.id);
            const ex = interp ? Number(interp.x || 0) : Number(ent.x || 0);
            const ez = interp ? Number(interp.z || 0) : Number(ent.z || 0);
            const dx = ex - world.x;
            const dz = ez - world.z;
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
        const kind = typeof opts.kind === "string" ? opts.kind.trim() : "npc";
        let defaultChars = 48;
        let defaultLines = 18;
        if (kind === "pending") {
            defaultChars = 34;
            defaultLines = 6;
        } else if (kind === "world_event") {
            defaultChars = 34;
            defaultLines = 5;
        }
        const maxChars = Number.isFinite(opts.maxChars) ? opts.maxChars : defaultChars;
        const maxLines = Number.isFinite(opts.maxLines) ? opts.maxLines : defaultLines;
        this.dialogueBubbles.set(entityId, {
            text: text.trim(),
            speaker: typeof opts.speaker === "string" ? opts.speaker.trim() : "",
            subtitle: typeof opts.subtitle === "string" ? opts.subtitle.trim() : "",
            playerEcho: typeof opts.playerEcho === "string" ? opts.playerEcho.trim() : "",
            traceId: typeof opts.traceId === "string" ? opts.traceId.trim() : "",
            kind,
            maxChars,
            maxLines,
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
        const words = String(text || "").replace(/\s+/g, " ").trim().split(/\s+/).filter(Boolean);
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
        if (lines.length === maxLines && words.join(" ").length > lines.join(" ").length + 1) {
            lines[maxLines - 1] = `${lines[maxLines - 1].replace(/[.…]+$/, "")}…`;
        }
        return lines;
    }

    /**
     * Lignes affichées dans la bulle (corps), selon le kind.
     */
    dialogueBodyLines(bubble) {
        const maxC = bubble.maxChars ?? 32;
        const maxL = bubble.maxLines ?? 4;
        if (bubble.kind === "pending" && bubble.playerEcho) {
            const status = (bubble.text || "Réponse en cours…").trim();
            const echoLines = this.wrapText(bubble.playerEcho, Math.min(maxC, 36), Math.min(maxL, 6));
            const out = [status];
            if (echoLines.length) {
                out.push("");
                out.push("Vous");
                out.push(...echoLines);
            }
            return out;
        }
        return this.wrapText(bubble.text, maxC, maxL);
    }

    /**
     * Coupe le tableau de lignes au besoin pour garder la bulle lisible à l’écran.
     */
    clampBubbleBodyLines(lines) {
        const max = Renderer.MAX_BUBBLE_BODY_LINES;
        if (!Array.isArray(lines) || lines.length <= max) return lines;
        const out = lines.slice(0, max);
        let last = String(out[max - 1] || "").trimEnd();
        if (last.length > 80) last = last.slice(0, 77).trimEnd();
        out[max - 1] = `${last.replace(/[.…]+$/u, "")}…`;
        return out;
    }

    drawDialogueBubble(ent, pos, drawY) {
        const bubble = this.dialogueBubbles.get(ent.id);
        if (!bubble) return;

        const ctx = this.ctx;
        const lines = this.clampBubbleBodyLines(this.dialogueBodyLines(bubble));
        if (!lines.length) return;

        const title = bubble.speaker || ent.name || "PNJ";
        const subtitle = (bubble.subtitle || "").trim();
        ctx.save();
        ctx.font = '800 11px "Inter", sans-serif';
        const titleW = ctx.measureText(title.toUpperCase()).width;
        ctx.font = '500 10px "Inter", sans-serif';
        const subtitleW = subtitle ? ctx.measureText(subtitle).width : 0;
        ctx.font = '600 12px "Inter", sans-serif';
        const bodyWidths = lines.map((line) => ctx.measureText(line).width);
        const maxTextWidth = Math.max(titleW, subtitleW, ...bodyWidths);
        const padX = 12;
        const padY = 8;
        const lineH = 15;
        const titleBlockH = 16;
        const subtitleBlockH = subtitle ? 13 : 0;
        const width = Math.min(380, Math.max(120, maxTextWidth + padX * 2));
        const height = padY * 2 + titleBlockH + subtitleBlockH + lines.length * lineH + 8;
        const bubbleLift = 86 + Math.max(0, (lines.length - 4) * 10 + (subtitle ? 6 : 0));
        const x = Math.max(12, Math.min(this.canvas.width - width - 12, pos.x - width / 2));
        const y = Math.max(12, drawY - bubbleLift - height);
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

        let bodyY0 = y + padY + titleBlockH + 8;
        if (subtitle) {
            ctx.fillStyle = "rgba(244, 247, 255, 0.62)";
            ctx.font = '500 10px "Inter", sans-serif';
            ctx.fillText(subtitle, x + padX, y + padY + titleBlockH + 8);
            bodyY0 = y + padY + titleBlockH + subtitleBlockH + 10;
        }

        ctx.fillStyle = "#f4f7ff";
        ctx.font = '600 12px "Inter", sans-serif';
        lines.forEach((line, i) => {
            const isEchoLabel = bubble.kind === "pending" && line === "Vous";
            const isEchoBody = bubble.kind === "pending"
                && bubble.playerEcho
                && i > 0
                && lines[i - 1] === "Vous";
            if (isEchoLabel) {
                ctx.fillStyle = "rgba(255, 234, 0, 0.85)";
                ctx.font = '700 11px "Inter", sans-serif';
            } else if (isEchoBody) {
                ctx.fillStyle = "rgba(244, 247, 255, 0.82)";
                ctx.font = '600 11px "Inter", sans-serif';
            } else {
                ctx.fillStyle = "#f4f7ff";
                ctx.font = '600 12px "Inter", sans-serif';
            }
            ctx.fillText(line, x + padX, bodyY0 + i * lineH);
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
        const smoothing = 0.24;
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
        this.cameraX += (player.x - this.cameraX) * 0.18;
        this.cameraY += (player.y - this.cameraY) * 0.18;
        this.cameraZ += (player.z - this.cameraZ) * 0.18;
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
            const rot = Number.isFinite(Number(loc.rotation_rad)) ? Number(loc.rotation_rad) : 0;
            const color = loc.type === "room" ? "255, 150, 0" : "0, 242, 255";
            if (loc.id === "auberge_salle_commune" && this.assets.tavern.complete) {
                ctx.save();
                ctx.translate(pos.x, pos.y);
                if (rot) ctx.rotate(rot);
                ctx.drawImage(this.assets.tavern, -w / 2, -h / 2, w, h);
                ctx.restore();
            } else if (loc.id === "forge" && this.assets.forge.complete) {
                ctx.save();
                ctx.translate(pos.x, pos.y);
                if (rot) ctx.rotate(rot);
                ctx.drawImage(this.assets.forge, -w / 2, -h / 2, w, h);
                ctx.restore();
                ctx.strokeStyle = `rgba(${color}, 0.3)`;
                ctx.lineWidth = 1;
                ctx.strokeRect(pos.x - w / 2, pos.y - h / 2, w, h);
            } else if (loc.type === "resource") {
                ctx.save();
                ctx.strokeStyle = "rgba(0, 242, 255, 0.55)";
                ctx.fillStyle = "rgba(0, 242, 255, 0.08)";
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.ellipse(pos.x, pos.y, Math.max(6, w / 2), Math.max(6, h / 2), 0, 0, Math.PI * 2);
                ctx.fill();
                ctx.stroke();
                ctx.restore();
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

        const isMoving = Math.sqrt((ent.vx || 0) ** 2 + (ent.vz || 0) ** 2) > 0.35;
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
        let yOffset = 0;
        if (ent.id) {
            let h = 0;
            for (let i = 0; i < ent.id.length; i++) h = (h + ent.id.charCodeAt(i)) | 0;
            yOffset = ((h % 5) - 2) * 0.35 * scale;
        }
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
        if (!this.assets.villageMapPretty.complete || this.zoom < 0.005) return;
        const ctx = this.ctx;
        const scale = 8 * this.zoom;
        let cx = 0;
        let cz = 0;
        let wM = 100;
        let hM = 80;
        const b = this.villageMapBounds;
        if (b) {
            cx = (b.min_x + b.max_x) / 2;
            cz = (b.min_z + b.max_z) / 2;
            wM = Math.max(1, b.max_x - b.min_x);
            hM = Math.max(1, b.max_z - b.min_z);
        }
        const pos = this.worldToScreen(cx, cz);
        const w = wM * scale;
        const h = hM * scale;
        ctx.save();
        ctx.globalAlpha = Math.min(1, (this.zoom - 0.005) * 20);
        const baseAlpha = ctx.globalAlpha;

        const drawImg = (img, alphaMul, flipZ = false, offsetX = 0.0, offsetZ = 0.0, scaleMul = 1.0) => {
            if (!img || !img.complete) return;
            const pos2 = (offsetX || offsetZ) ? this.worldToScreen(cx + offsetX, cz + offsetZ) : pos;
            ctx.globalAlpha = baseAlpha * alphaMul;
            const ww = w * scaleMul;
            const hh = h * scaleMul;
            if (flipZ) {
                ctx.save();
                ctx.translate(pos2.x, pos2.y);
                ctx.scale(1, -1);
                ctx.drawImage(img, -ww / 2, -hh / 2, ww, hh);
                ctx.restore();
            } else {
                ctx.drawImage(img, pos2.x - ww / 2, pos2.y - hh / 2, ww, hh);
            }
        };

        drawImg(
            this.assets.villageMapPretty,
            1.0,
            this.villageMapPrettyFlipZ,
            0.0,
            0.0,
            this.villageMapPrettyScale
        );
        if (this.villageMapOverlayEnabled) {
            drawImg(
                this.assets.villageMapGrid,
                this.villageMapOverlayAlpha,
                this.villageMapOverlayFlipZ,
                this.villageMapOverlayOffsetX,
                this.villageMapOverlayOffsetZ,
                this.villageMapOverlayScale
            );
        }
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
