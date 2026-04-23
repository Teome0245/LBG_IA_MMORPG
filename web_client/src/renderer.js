/**
 * Moteur de rendu isométrique 2D sur Canvas.
 */
export class Renderer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.entities = [];
        this.interpolatedEntities = new Map(); // id -> {x, y, z}
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
            npc: new Image()
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

        await Promise.all([
            loadImg(this.assets.floor, '/assets/tile_floor.png'),
            loadImg(this.assets.player, '/assets/char_player.png'),
            loadImg(this.assets.npc, '/assets/char_npc.png')
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
                interpolated.y += (ent.y - interpolated.y) * smoothing;
                interpolated.z += ((ent.z || 0) - interpolated.z) * smoothing;
            }
        }
    }

    drawFloor() {
        const ctx = this.ctx;
        const range = 15; // Vue plus large
        const tw = this.tileW;
        const th = this.tileH;

        ctx.lineWidth = 1;
        ctx.strokeStyle = 'rgba(0, 242, 255, 0.15)'; // Cyan néon transparent

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
                const alpha = Math.max(0, 0.05 - dist * 0.002);
                ctx.fillStyle = `rgba(0, 242, 255, ${alpha})`;
                ctx.fill();
                
                // Ne dessiner les lignes que si on est proche du centre pour un effet de fondu
                if (dist < range - 2) {
                    ctx.stroke();
                }
            }
        }
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

            this.drawFloor();

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
