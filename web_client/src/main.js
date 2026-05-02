import { NetworkManager } from './network.js';
import { Renderer } from './renderer.js';
import { InputManager } from './input.js';

const QUEST_LOG_STORAGE_KEY = "lbg-mmo.questLog.v1";

class App {
    constructor() {
        this.network = new NetworkManager(
            (msg) => this.handleMessage(msg),
            () => this.handleDisconnect()
        );
        this.renderer = new Renderer('game-canvas');
        this.input = new InputManager();
        
        this.playerLocalPos = { x: 0, y: 0, z: 0 };
        this.isMoving = false;
        this._lastConnect = { serverHost: null, name: null };
        this.selectedDialogueTarget = null;
        this.lastDialogueTarget = null;
        this.dialogueTargetByTrace = new Map();
        this.worldEvents = [];
        this.seenWorldEventTraceIds = new Set();
        this.questLogById = new Map();
        
        this.initUI();
    }

    initUI() {
        const connectBtn = document.getElementById('connect-btn');
        const playerNameInput = document.getElementById('player-name');
        const serverHostInput = document.getElementById('server-url');
        const chatInput = document.getElementById('chat-msg');
        const sendChatBtn = document.getElementById('send-chat-btn');
        const quickAidBtn = document.getElementById('quick-aid-btn');
        const quickQuestBtn = document.getElementById('quick-quest-btn');
        const clearQuestsBtn = document.getElementById('clear-quests-btn');

        connectBtn.addEventListener('click', () => {
            const name = playerNameInput.value.trim() || "Voyageur";
            this.connect(name);
        });

        // Entrée clavier pour la connexion
        playerNameInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') connectBtn.click();
        });
        serverHostInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') connectBtn.click();
        });

        // Bouton de reconnexion (overlay)
        const reconnectBtn = document.getElementById('reconnect-btn');
        if (reconnectBtn) {
            reconnectBtn.addEventListener('click', () => {
                const name = this._lastConnect.name || (playerNameInput.value.trim() || "Voyageur");
                this.connect(name);
            });
        }

        // Chat
        sendChatBtn.addEventListener('click', () => {
            const text = chatInput.value.trim();
            if (text) {
                this.sendDialogueToTarget(text);
                chatInput.value = "";
            }
        });

        if (quickAidBtn) {
            quickAidBtn.addEventListener('click', () => {
                this.sendDialogueToTarget(
                    "J'ai besoin d'aide maintenant. Agis concrètement pour réduire faim, soif ou fatigue, et indique l'action appliquée.",
                    { _require_action_json: true, _world_action_kind: "aid" }
                );
            });
        }

        if (quickQuestBtn) {
            quickQuestBtn.addEventListener('click', () => {
                this.sendDialogueToTarget(
                    "Propose-moi une quête simple liée à ce lieu et enregistre-la comme action de quête.",
                    { _require_action_json: true, _world_action_kind: "quest" }
                );
            });
        }

        if (clearQuestsBtn) {
            clearQuestsBtn.addEventListener('click', () => {
                this.questLogById.clear();
                this.persistQuestLog();
                this.renderQuestLog();
                this.addLog("Journal de quêtes local vidé.", "system");
            });
        }

        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendChatBtn.click();
        });

        this.renderer.canvas.addEventListener('click', (e) => this.handleCanvasClick(e));
        this.restoreQuestLog();
        this.renderQuestLog();
    }

    sendDialogueToTarget(text, iaContext = null) {
        const clean = typeof text === "string" ? text.trim() : "";
        if (!clean) return;
        const target = this.getDialogueTarget();
        this.lastDialogueTarget = target;
        this.network.sendChat(clean, target.id, target.name, this.playerLocalPos, iaContext);
        this.renderer.setDialogueBubble(target.id, "...", {
            speaker: target.name,
            kind: "pending",
            ttlMs: 120000,
        });
        this.addLog(`À ${target.name}: ${clean}`, 'player');
    }

    async connect(name) {
        try {
            const serverHost = document.getElementById('server-url').value.trim() || window.location.hostname;
            document.getElementById('login-screen').classList.add('hidden');
            document.getElementById('disconnect-screen').classList.add('hidden');
            this.addLog("Connexion au multivers...");
            
            const wsScheme = (window.location && window.location.protocol === "https:") ? "wss" : "ws";
            const wsUrl = `${wsScheme}://${serverHost}:7733`;
            this._lastConnect = { serverHost, name };
            const welcomeData = await this.network.connect(wsUrl, name, {
                welcomeTimeoutMs: 6000,
                autoReconnect: true,
                reconnectMaxDelayMs: 5000,
            });
            
            this.handleWelcome(welcomeData);
            document.getElementById('game-container').classList.remove('hidden');
            
            // Démarrer la boucle de jeu
            this.startGameLoop();
        } catch (err) {
            console.error(err);
            alert("Impossible de se connecter au serveur MMO (port 7733). Assurez-vous que le serveur est lancé.");
            document.getElementById('login-screen').classList.remove('hidden');
        }
    }

    handleWelcome(data) {
        this.addLog(`Bienvenue ${data.player_id} !`, 'system');
        this.worldEvents = [];
        this.seenWorldEventTraceIds.clear();
        this.renderWorldEvents();
        this.renderQuestLog();
        this.renderer.setPlayerId(data.player_id);
        try { this.renderer.updateLocations(data.locations || []); } catch (_) {}
        try { this.renderer.updateState(data.entities || [], data.world_time_s || 0, data.day_fraction || 0); } catch (_) {}
        
        document.getElementById('stat-name').textContent = data.player_id.split(':')[0];
        document.getElementById('stat-id').textContent = data.player_id;
        
        // Position initiale (si présente dans l'entité player)
        const me = data.entities.find(e => e.id === data.player_id);
        if (me) {
            this.playerLocalPos = { x: me.x, y: me.y, z: me.z };
        }
    }

    handleMessage(msg) {
        if (msg.type === "world_tick") {
            this.renderer.updateState(msg.entities, msg.world_time_s, msg.day_fraction);
            if (msg.locations) {
                try { this.renderer.updateLocations(msg.locations); } catch (_) {}
            }
            this.updateHUD(msg);
            
            // Gérer les répliques PNJ (pont IA)
            if (msg.npc_reply) {
                const target = this.resolveDialogueTarget(msg.trace_id);
                this.renderer.setDialogueBubble(target.id, msg.npc_reply, {
                    speaker: target.name,
                    traceId: msg.trace_id || "",
                    kind: "npc",
                });
                this.addLog(`${target.name}: ${msg.npc_reply}`, 'npc');
            }
            if (msg.world_event) {
                this.handleWorldEvent(msg.world_event, msg.trace_id);
            }
        } else if (msg.type === "error") {
            this.addLog(`Erreur: ${msg.message}`, 'error');
        }
    }

    handleWorldEvent(event, traceId) {
        if (!event || event.type !== "dialogue_commit") {
            return;
        }
        const target = this.resolveDialogueTarget(event.trace_id || traceId);
        const summary = typeof event.summary === "string" && event.summary.trim()
            ? event.summary.trim()
            : "Action monde appliquée.";
        this.renderer.setDialogueBubble(target.id, summary, {
            speaker: "Action",
            traceId: event.trace_id || traceId || "",
            kind: "world_event",
            ttlMs: 7000,
        });
        this.recordWorldEvent(event, target, summary);
        this.addLog(`Action monde (${target.name}): ${summary}`, 'system');
    }

    recordWorldEvent(event, target, summary) {
        const tid = typeof event.trace_id === "string" ? event.trace_id.trim() : "";
        if (tid && this.seenWorldEventTraceIds.has(tid)) {
            return;
        }
        if (tid) {
            this.seenWorldEventTraceIds.add(tid);
        }
        const flags = event && typeof event.flags === "object" && event.flags ? event.flags : {};
        const kind = typeof flags.quest_id === "string" && flags.quest_id.trim() ? "quest" : "aid";
        this.worldEvents.unshift({
            traceId: tid,
            npcName: target && target.name ? target.name : "PNJ",
            summary,
            kind,
            questId: kind === "quest" ? flags.quest_id.trim() : "",
            time: new Date(),
        });
        if (this.worldEvents.length > 6) {
            this.worldEvents.length = 6;
        }
        if (kind === "quest") {
            this.recordQuest(flags, target);
        }
        this.renderWorldEvents();
    }

    recordQuest(flags, target) {
        const questId = typeof flags.quest_id === "string" ? flags.quest_id.trim() : "";
        if (!questId) return;
        const step = Number.isFinite(Number(flags.quest_step)) ? Number(flags.quest_step) : 0;
        const accepted = typeof flags.quest_accepted === "boolean" ? flags.quest_accepted : true;
        this.questLogById.set(questId, {
            questId,
            step,
            accepted,
            npcName: target && target.name ? target.name : "PNJ",
            time: new Date(),
        });
        this.persistQuestLog();
        this.renderQuestLog();
    }

    restoreQuestLog() {
        try {
            const raw = window.localStorage.getItem(QUEST_LOG_STORAGE_KEY);
            if (!raw) return;
            const rows = JSON.parse(raw);
            if (!Array.isArray(rows)) return;
            for (const row of rows) {
                if (!row || typeof row.questId !== "string" || !row.questId.trim()) continue;
                this.questLogById.set(row.questId.trim(), {
                    questId: row.questId.trim(),
                    step: Number.isFinite(Number(row.step)) ? Number(row.step) : 0,
                    accepted: typeof row.accepted === "boolean" ? row.accepted : true,
                    npcName: typeof row.npcName === "string" && row.npcName.trim() ? row.npcName.trim() : "PNJ",
                    time: row.time ? new Date(row.time) : new Date(),
                });
            }
        } catch (_) {
            this.questLogById.clear();
        }
    }

    persistQuestLog() {
        try {
            const rows = Array.from(this.questLogById.values())
                .sort((a, b) => b.time.getTime() - a.time.getTime())
                .slice(0, 20)
                .map((row) => ({
                    ...row,
                    time: row.time.toISOString(),
                }));
            window.localStorage.setItem(QUEST_LOG_STORAGE_KEY, JSON.stringify(rows));
        } catch (_) {}
    }

    renderWorldEvents() {
        const feed = document.getElementById('world-event-feed');
        if (!feed) return;
        feed.innerHTML = "";
        if (!this.worldEvents.length) {
            const empty = document.createElement('div');
            empty.className = 'world-event empty';
            empty.textContent = 'Aucune action monde.';
            feed.appendChild(empty);
            return;
        }
        for (const item of this.worldEvents) {
            const row = document.createElement('div');
            row.className = `world-event ${item.kind === "quest" ? "quest" : "aid"}`;
            const label = item.kind === "quest" ? "Quête" : "Aide";
            row.textContent = `${label}: ${item.summary}`;
            const meta = document.createElement('span');
            meta.className = 'meta';
            const hhmmss = item.time.toLocaleTimeString();
            const quest = item.questId ? ` · ${item.questId}` : "";
            meta.textContent = `${item.npcName} · ${hhmmss}${quest}`;
            row.appendChild(meta);
            feed.appendChild(row);
        }
    }

    renderQuestLog() {
        const feed = document.getElementById('quest-log-feed');
        if (!feed) return;
        feed.innerHTML = "";
        const quests = Array.from(this.questLogById.values())
            .sort((a, b) => b.time.getTime() - a.time.getTime())
            .slice(0, 5);
        if (!quests.length) {
            const empty = document.createElement('div');
            empty.className = 'world-event empty';
            empty.textContent = 'Aucune quête active.';
            feed.appendChild(empty);
            return;
        }
        for (const quest of quests) {
            const row = document.createElement('div');
            row.className = 'world-event quest';
            row.textContent = quest.accepted
                ? `Acceptée: ${quest.questId}`
                : `Mise à jour: ${quest.questId}`;
            const meta = document.createElement('span');
            meta.className = 'meta';
            meta.textContent = `${quest.npcName} · étape ${quest.step} · ${quest.time.toLocaleTimeString()}`;
            row.appendChild(meta);
            feed.appendChild(row);
        }
    }

    handleDisconnect() {
        document.getElementById('disconnect-screen').classList.remove('hidden');
        // L'auto-reconnect est géré par NetworkManager; ici on affiche juste l'état.
        this.addLog("Connexion perdue. Tentative de reconnexion...", 'error');
    }

    updateHUD(msg) {
        document.getElementById('world-time').textContent = this.formatTime(msg.world_time_s);
        
        const me = msg.entities.find(e => e.id === this.network.playerId);
        if (me) {
            document.getElementById('pos-x').textContent = Math.round(me.x);
            // Y (serveur) = altitude. On affiche plutôt Z (plan) dans le HUD.
            document.getElementById('pos-y').textContent = Math.round(me.z);
            this.playerLocalPos = { x: me.x, y: me.y, z: me.z };
        }
        this.updateDialogueTargetHUD();
        this.updateNpcWorldStateHUD();
    }

    getDialogueTarget() {
        if (this.selectedDialogueTarget && this.entityExists(this.selectedDialogueTarget.id)) {
            return this.selectedDialogueTarget;
        }

        const entities = Array.isArray(this.renderer.entities) ? this.renderer.entities : [];
        const npcs = entities.filter((ent) => ent && ent.kind === "npc" && typeof ent.id === "string");
        if (!npcs.length) {
            return { id: "npc:merchant", name: "Marchand" };
        }

        const nearest = npcs
            .map((ent) => {
                const dx = Number(ent.x || 0) - Number(this.playerLocalPos.x || 0);
                const dz = Number(ent.z || 0) - Number(this.playerLocalPos.z || 0);
                return { ent, dist2: dx * dx + dz * dz };
            })
            .sort((a, b) => a.dist2 - b.dist2)[0].ent;

        return { id: nearest.id, name: nearest.name || nearest.id };
    }

    entityExists(entityId) {
        const entities = Array.isArray(this.renderer.entities) ? this.renderer.entities : [];
        return entities.some((ent) => ent && ent.id === entityId);
    }

    handleCanvasClick(event) {
        const rect = this.renderer.canvas.getBoundingClientRect();
        const scaleX = this.renderer.canvas.width / rect.width;
        const scaleY = this.renderer.canvas.height / rect.height;
        const x = (event.clientX - rect.left) * scaleX;
        const y = (event.clientY - rect.top) * scaleY;
        const npc = this.renderer.getNpcAtScreen(x, y);

        if (!npc) {
            return;
        }

        this.selectedDialogueTarget = { id: npc.id, name: npc.name || npc.id };
        this.lastDialogueTarget = this.selectedDialogueTarget;
        this.renderer.setSelectedEntityId(npc.id);
        this.updateDialogueTargetHUD();
        this.addLog(`Cible sélectionnée: ${this.selectedDialogueTarget.name}`, 'system');
    }

    resolveDialogueTarget(traceId) {
        const tid = typeof traceId === "string" ? traceId.trim() : "";
        if (tid && this.dialogueTargetByTrace.has(tid)) {
            return this.dialogueTargetByTrace.get(tid);
        }

        const target = this.lastDialogueTarget || this.getDialogueTarget();
        if (tid) {
            this.dialogueTargetByTrace.set(tid, target);
        }
        return target;
    }

    updateDialogueTargetHUD() {
        const targetEl = document.getElementById('dialogue-target');
        if (!targetEl) return;
        const target = this.getDialogueTarget();
        const selected = this.selectedDialogueTarget && this.selectedDialogueTarget.id === target.id;
        targetEl.textContent = selected ? `${target.name} (sélectionné)` : target.name;
    }

    updateNpcWorldStateHUD() {
        const el = document.getElementById('npc-world-state');
        if (!el) return;
        const target = this.getDialogueTarget();
        const entities = Array.isArray(this.renderer.entities) ? this.renderer.entities : [];
        const npc = entities.find((ent) => ent && ent.id === target.id && ent.kind === "npc");
        const state = npc && typeof npc.world_state === "object" && npc.world_state ? npc.world_state : null;
        if (!state) {
            el.innerHTML = '<span class="muted">État PNJ non disponible.</span>';
            return;
        }
        const gauges = typeof state.gauges === "object" && state.gauges ? state.gauges : {};
        const flags = typeof state.flags === "object" && state.flags ? state.flags : {};
        const pct = (value) => `${Math.round(Math.max(0, Math.min(1, Number(value || 0))) * 100)}%`;
        const rep = Number.isFinite(Number(state.reputation)) ? Number(state.reputation) : 0;
        const repClass = rep > 0 ? "good" : rep < 0 ? "warn" : "muted";
        const quest = typeof flags.quest_id === "string" && flags.quest_id.trim()
            ? `<br>Quête: <span class="warn">${flags.quest_id.trim()}</span>`
            : "";
        el.innerHTML = [
            `Réputation: <span class="${repClass}">${rep}</span>`,
            `Faim: <span>${pct(gauges.hunger)}</span>`,
            `Soif: <span>${pct(gauges.thirst)}</span>`,
            `Fatigue: <span>${pct(gauges.fatigue)}</span>${quest}`,
        ].join("<br>");
    }

    formatTime(seconds) {
        const hours = Math.floor((seconds % 86400) / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        return `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}`;
    }

    addLog(text, type = 'system') {
        const consoleLogs = document.getElementById('console-logs');
        const log = document.createElement('div');
        log.className = `log ${type}`;
        log.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
        consoleLogs.appendChild(log);
        consoleLogs.scrollTop = consoleLogs.scrollHeight;
    }

    startGameLoop() {
        let lastMoveSent = 0;
        const loop = (time) => {
            try {
                const now = performance.now();
                
                // Throttle des messages move à environ 20Hz (50ms) pour correspondre au serveur
                if (now - lastMoveSent > 50) {
                    this.update();
                    lastMoveSent = now;
                }
                
                // Rendu à 60fps avec facteur d'animation
                const bobbing = Math.sin((time || now) / 150) * 2;
                this.renderer.render(bobbing);
            } catch(e) {
                const consoleLogs = document.getElementById('console-logs');
                if (consoleLogs) {
                    const log = document.createElement('div');
                    log.className = 'log error';
                    log.textContent = `[LOOP ERR] ${e.message}`;
                    consoleLogs.appendChild(log);
                }
            } finally {
                requestAnimationFrame(loop);
            }
        };
        requestAnimationFrame(loop);
    }

    update() {
        // Gestion du mouvement local et envoi au serveur
        const move = this.input.getMovementVector();
        if (move.x !== 0 || move.y !== 0) {
            const speed = 0.2;
            const newX = this.playerLocalPos.x + move.x * speed;
            const newZ = this.playerLocalPos.z + move.y * speed;
            
            // Note: On pourrait faire de la prédiction côté client, 
            // mais ici on envoie juste l'intention au serveur.
            this.network.sendMove(newX, 0, newZ);
        }
    }
}

// Lancer l'application
new App();
