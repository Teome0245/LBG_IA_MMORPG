import { NetworkManager } from './network.js';
import { Renderer } from './renderer.js';
import { InputManager } from './input.js';
import { loadRaceDisplayMap } from './worldCatalog.js';
import { loadVillageCollisionGridFromMmoServer } from './villageCollisionGrid.js';

const QUEST_LOG_STORAGE_KEY = "lbg-mmo.questLog.v1";
const ACTIVE_QUEST_STORAGE_KEY = "lbg-mmo.activeQuest.v1";

/** Objet « ramassage » déterministe (stub gameplay) — même canal que Pilot / LLM (flags player_item_*). */
const STUB_PICKUP = {
    itemId: "item:brindille",
    label: "Brindille",
    qty: 1,
    maxDistance: 12,
};

function escapeHtml(s) {
    if (s == null || s === undefined) return "";
    return String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function formatSheetId(id) {
    const s = String(id || "");
    if (s.length <= 22) return s;
    return `${s.slice(0, 10)}…${s.slice(-8)}`;
}

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
        this.isAttacking = false;
        this._lastConnect = { serverHost: null, name: null };
        this.selectedDialogueTarget = null;
        this.lastDialogueTarget = null;
        this.dialogueTargetByTrace = new Map();
        this.worldEvents = [];
        this.seenWorldEventTraceIds = new Set();
        /** @type {Map<string, Array<{role: string, content: string}>>} */
        this.dialogueHistoryByNpcId = new Map();
        /** @type {Map<string, string>} dernier trace_id PNJ déjà enregistré dans l'historique (placeholder → remplace) */
        this._lastDialogueTraceByNpcId = new Map();
        /** Fusion journal : même trace_id = placeholder puis réplique finale → une seule ligne */
        this._npcLogRowByTraceId = new Map();
        this.questLogById = new Map();
        this.activeQuestId = "";
        this.raceDisplayById = Object.create(null);
        /** @type {import('./villageCollisionGrid.js').VillageCollisionGrid | null} */
        this.collisionGrid = null;
        this.gameData = { quests: [], recipes: [] };
        this.selectedQuestId = "";
        // Valeurs calibrées pour Pixie Seat : on corrige le PNG Watabou (fond “joli”) pour qu'il colle à la grille collisions.
        this._villageMapPrettyFlipZ = true;
        this._villageMapPrettyScale = 1 / 1.4;
        // Debug overlay : calque “moche” par-dessus.
        this._villageMapOverlayFlipZ = false;
        this._villageMapOverlay = false;
        this._villageMapOverlayAlpha = 0.55;
        this._villageMapDx = 0.0;
        this._villageMapDz = 0.0;
        this._villageMapOverlayScale = 1.0;
        
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
        const quickQuestCompleteBtn = document.getElementById('quick-quest-complete-btn');
        const stubPickupBtn = document.getElementById('stub-pickup-btn');
        const questAcceptBtn = document.getElementById('quest-accept-btn');
        const questTurninBtn = document.getElementById('quest-turnin-btn');
        const jobGatherBtn = document.getElementById('job-gather-btn');
        const jobCraftBtn = document.getElementById('job-craft-btn');
        const tradeBuyBtn = document.getElementById('trade-buy-btn');
        const tradeSellBtn = document.getElementById('trade-sell-btn');
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

        if (quickQuestCompleteBtn) {
            quickQuestCompleteBtn.addEventListener('click', () => {
                const qid = (this.activeQuestId || "").trim();
                const ctx = {
                    _require_action_json: true,
                    _world_action_kind: "quest",
                };
                if (qid) ctx._active_quest_id = qid;
                this.sendDialogueToTarget(
                    "Je confirme avoir accompli les objectifs : enregistre la clôture (ACTION_JSON quest avec quest_completed=true et le quest_id correct).",
                    ctx
                );
            });
        }

        if (stubPickupBtn) {
            stubPickupBtn.addEventListener('click', () => this.tryStubPickupFromNpc());
        }
        if (questAcceptBtn) questAcceptBtn.addEventListener("click", () => this.tryQuestAccept());
        if (questTurninBtn) questTurninBtn.addEventListener("click", () => this.tryQuestTurnin());
        if (jobGatherBtn) jobGatherBtn.addEventListener("click", () => this.tryGather());
        if (jobCraftBtn) jobCraftBtn.addEventListener("click", () => this.network.sendJob({ action: "craft", recipeId: "recipe:iron_ingot" }));

        if (tradeBuyBtn) {
            tradeBuyBtn.addEventListener("click", () => this.tryTrade("buy"));
        }
        if (tradeSellBtn) {
            tradeSellBtn.addEventListener("click", () => this.tryTrade("sell"));
        }

        this._onKeyAttack = (e) => {
            if (!e || e.code !== "KeyA" || e.repeat) return;
            const gameEl = document.getElementById("game-container");
            if (!gameEl || gameEl.classList.contains("hidden")) return;
            const chatEl = document.getElementById("chat-msg");
            if (document.activeElement === chatEl) return;
            e.preventDefault();
            this.toggleAttackOnTarget();
        };
        window.addEventListener("keydown", this._onKeyAttack);

        this._onKeyPickup = (e) => {
            if (!e || e.code !== "KeyE" || e.repeat) return;
            const gameEl = document.getElementById("game-container");
            if (!gameEl || gameEl.classList.contains("hidden")) return;
            const chatEl = document.getElementById("chat-msg");
            if (document.activeElement === chatEl) return;
            e.preventDefault();
            this.tryStubPickupFromNpc();
        };
        window.addEventListener("keydown", this._onKeyPickup);

        this._onKeyDoor = (e) => {
            if (!e || e.code !== "KeyF" || e.repeat) return;
            const gameEl = document.getElementById("game-container");
            if (!gameEl || gameEl.classList.contains("hidden")) return;
            const chatEl = document.getElementById("chat-msg");
            if (document.activeElement === chatEl) return;
            e.preventDefault();
            this.tryUseDoor();
        };
        window.addEventListener("keydown", this._onKeyDoor);

        this._onKeyTrade = (e) => {
            if (!e || e.repeat) return;
            const gameEl = document.getElementById("game-container");
            if (!gameEl || gameEl.classList.contains("hidden")) return;
            const chatEl = document.getElementById("chat-msg");
            if (document.activeElement === chatEl) return;
            if (e.code === "KeyB") {
                e.preventDefault();
                this.tryTrade("buy");
            } else if (e.code === "KeyV") {
                e.preventDefault();
                this.tryTrade("sell");
            }
        };
        window.addEventListener("keydown", this._onKeyTrade);

        this._onKeyQuest = (e) => {
            if (!e || e.repeat) return;
            const gameEl = document.getElementById("game-container");
            if (!gameEl || gameEl.classList.contains("hidden")) return;
            const chatEl = document.getElementById("chat-msg");
            if (document.activeElement === chatEl) return;
            if (e.code === "KeyQ") {
                e.preventDefault();
                this.tryQuestAccept();
            } else if (e.code === "KeyT") {
                e.preventDefault();
                this.tryQuestTurnin();
            } else if (e.code === "KeyG") {
                e.preventDefault();
                this.tryGather();
            } else if (e.code === "KeyC") {
                e.preventDefault();
                this.network.sendJob({ action: "craft", recipeId: "recipe:iron_ingot" });
            }
        };
        window.addEventListener("keydown", this._onKeyQuest);

        if (clearQuestsBtn) {
            clearQuestsBtn.addEventListener('click', () => {
                this.questLogById.clear();
                this.setActiveQuest("", { silent: true });
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
        this.updateActiveQuestHUD();
    }

    _dialogueHistoryLimit() {
        return 24;
    }

    _historySnapshotForNpc(npcId) {
        const id = String(npcId || "").trim();
        if (!id) return [];
        const arr = this.dialogueHistoryByNpcId.get(id);
        return Array.isArray(arr) ? arr.map((x) => ({ role: x.role, content: x.content })) : [];
    }

    recordNpcDialogueAssistant(npcId, text, traceId) {
        const id = String(npcId || "").trim();
        const t = typeof text === "string" ? text.trim() : "";
        if (!id || !t) return;
        const tid = typeof traceId === "string" ? traceId.trim() : "";
        const lim = this._dialogueHistoryLimit();
        const cap = 1800;
        const chunk = t.length > cap ? `${t.slice(0, cap)}…` : t;
        let arr = this.dialogueHistoryByNpcId.get(id);
        if (!Array.isArray(arr)) arr = [];
        const prevTrace = tid ? this._lastDialogueTraceByNpcId.get(id) : null;
        if (tid && prevTrace === tid && arr.length && arr[arr.length - 1].role === "assistant") {
            arr[arr.length - 1].content = chunk;
        } else {
            arr.push({ role: "assistant", content: chunk });
            while (arr.length > lim) arr.shift();
        }
        if (tid) this._lastDialogueTraceByNpcId.set(id, tid);
        this.dialogueHistoryByNpcId.set(id, arr);
    }

    appendNpcDialogueUser(npcId, text) {
        const id = String(npcId || "").trim();
        const t = typeof text === "string" ? text.trim() : "";
        if (!id || !t) return;
        const lim = this._dialogueHistoryLimit();
        const cap = 1800;
        const chunk = t.length > cap ? `${t.slice(0, cap)}…` : t;
        let arr = this.dialogueHistoryByNpcId.get(id);
        if (!Array.isArray(arr)) arr = [];
        arr.push({ role: "user", content: chunk });
        while (arr.length > lim) arr.shift();
        this.dialogueHistoryByNpcId.set(id, arr);
    }

    tryStubPickupFromNpc() {
        const target = this.getDialogueTarget();
        if (!target || !target.id) {
            this.addLog("Ramasser : aucune cible PNJ.", "system");
            return;
        }
        const entities = Array.isArray(this.renderer.entities) ? this.renderer.entities : [];
        const npc = entities.find((ent) => ent && ent.id === target.id && ent.kind === "npc");
        if (!npc) {
            this.addLog("Ramasser : PNJ introuvable sur la carte.", "system");
            return;
        }
        const px = Number(this.playerLocalPos.x || 0);
        const pz = Number(this.playerLocalPos.z || 0);
        const nx = Number(npc.x || 0);
        const nz = Number(npc.z || 0);
        const dx = px - nx;
        const dz = pz - nz;
        const maxD = STUB_PICKUP.maxDistance;
        if (dx * dx + dz * dz > maxD * maxD) {
            this.addLog(`Trop loin de ${target.name} pour ramasser (≤ ${maxD} m). Approchez-vous.`, "system");
            return;
        }
        const traceId = `pickup-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
        const p = this.playerLocalPos;
        this.network.sendMoveWithWorldCommit(p.x, p.y, p.z, {
            npc_id: target.id,
            trace_id: traceId,
            flags: {
                player_item_id: STUB_PICKUP.itemId,
                player_item_qty_delta: STUB_PICKUP.qty,
                player_item_label: STUB_PICKUP.label,
            },
        });
        this.addLog(`Ramassage (stub) près de ${target.name} : +${STUB_PICKUP.qty} ${STUB_PICKUP.label}`, "player");
    }

    sendDialogueToTarget(text, iaContext = null) {
        const clean = typeof text === "string" ? text.trim() : "";
        if (!clean) return;
        const target = this.getDialogueTarget();
        this.lastDialogueTarget = target;
        const merged = {};
        if (iaContext && typeof iaContext === "object") {
            Object.assign(merged, iaContext);
        }
        const qid = (this.activeQuestId || "").trim();
        if (qid && !Object.prototype.hasOwnProperty.call(merged, "_active_quest_id")) {
            merged._active_quest_id = qid;
        }
        const summary = {};
        if (qid) summary.tracked_quest = qid.slice(0, 80);
        const tn = target && target.name ? String(target.name).trim() : "";
        if (tn) summary.last_npc = tn.slice(0, 80);
        if (Object.keys(summary).length) {
            merged.session_summary = summary;
        }
        const priorHist = this._historySnapshotForNpc(target.id);
        if (priorHist.length) {
            merged.history = priorHist;
        }
        this.appendNpcDialogueUser(target.id, clean);
        const outCtx = Object.keys(merged).length ? merged : null;
        this.network.sendChat(clean, target.id, target.name, this.playerLocalPos, outCtx);
        const echo = clean.length > 120 ? `${clean.slice(0, 117)}…` : clean;
        this.renderer.setDialogueBubble(target.id, "Réponse en cours…", {
            speaker: target.name,
            kind: "pending",
            ttlMs: 120000,
            subtitle: this._formatRoleSubtitle(target),
            playerEcho: echo,
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
            // Toggle manuel pour aligner le calque “moche” : ajouter ?flipz=1 à l'URL, ou stocker via localStorage.
            try {
                const qs = new URLSearchParams(window.location.search || "");
                // flipz agit sur l'overlay (debug) ; pflipz sur le fond Watabou.
                const qv = (qs.get("flipz") || "").trim();
                if (qv === "1" || qv.toLowerCase() === "true") this._villageMapOverlayFlipZ = true;
                const pqv = (qs.get("pflipz") || "").trim();
                if (pqv === "0" || pqv.toLowerCase() === "false") this._villageMapPrettyFlipZ = false;
                if (pqv === "1" || pqv.toLowerCase() === "true") this._villageMapPrettyFlipZ = true;
                const ov = (qs.get("overlay") || "").trim();
                const oa = (qs.get("alpha") || "").trim();
                if (ov === "1" || ov.toLowerCase() === "true") {
                    this._villageMapOverlay = true;
                }
                if (oa) {
                    this._villageMapOverlayAlpha = Number(oa);
                }
                const dx = (qs.get("dx") || "").trim();
                const dz = (qs.get("dz") || "").trim();
                if (dx) this._villageMapDx = Number(dx);
                if (dz) this._villageMapDz = Number(dz);
                const os = (qs.get("os") || "").trim();
                if (os) this._villageMapOverlayScale = Number(os);
                const ps = (qs.get("ps") || "").trim();
                if (ps) this._villageMapPrettyScale = Number(ps);
                const ls = (window.localStorage && window.localStorage.getItem("lbg-mmo.villageMap.flipZ")) || "";
                if (String(ls).trim() === "1") this._villageMapOverlayFlipZ = true;
            } catch (_) {}
            this.raceDisplayById = Object.create(null);
            const catalogPromise = loadRaceDisplayMap(serverHost).then((m) => {
                if (m) Object.assign(this.raceDisplayById, m);
                return m ? Object.keys(m).length : 0;
            });

            const welcomeData = await this.network.connect(wsUrl, name, {
                welcomeTimeoutMs: 6000,
                autoReconnect: true,
                reconnectMaxDelayMs: 5000,
            });

            this.handleWelcome(welcomeData);
            document.getElementById('game-container').classList.remove('hidden');

            this.startGameLoop();

            catalogPromise
                .then((nRaceLabels) => {
                    if (nRaceLabels) {
                        this.addLog(`Catalogue races : ${nRaceLabels} libellés.`, "system");
                    }
                    this.refreshRaceLabelsOnSheets();
                })
                .catch(() => {});
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
        this.dialogueHistoryByNpcId.clear();
        this._lastDialogueTraceByNpcId.clear();
        this._npcLogRowByTraceId.clear();
        this.renderWorldEvents();
        this.renderQuestLog();
        this.renderer.setPlayerId(data.player_id);
        try { this.renderer.updateLocations(data.locations || []); } catch (_) {}
        try { this.renderer.updateState(data.entities || [], data.world_time_s || 0, data.day_fraction || 0); } catch (_) {}
        this.syncPlayerQuestFromServer(data.entities || [], data.player_id);
        
        document.getElementById('stat-id').textContent = data.player_id;

        // Position initiale (si présente dans l'entité player)
        const me = data.entities.find(e => e.id === data.player_id);
        if (me && me.name) {
            document.getElementById('stat-name').textContent = me.name;
        } else {
            document.getElementById('stat-name').textContent = data.player_id.split(":")[0];
        }
        if (me) {
            this.playerLocalPos = { x: me.x, y: me.y, z: me.z };
        }
        this.renderPlayerSheet(me || null);
        this.updateNpcWorldStateHUD();

        const host = this._lastConnect && this._lastConnect.serverHost ? String(this._lastConnect.serverHost).trim() : "";
        if (host) {
            loadVillageCollisionGridFromMmoServer(host)
                .then((g) => {
                    this.collisionGrid = g;
                    if (g) {
                        // La grille collisions inclut souvent un padding (tuiles) autour de l'earth Watabou.
                        // L'image Watabou exportée est généralement cadrée sur l'earth (sans padding) :
                        // on retire donc `padding_tiles * tile_m` sur chaque bord pour caler le fond.
                        const padM = (Number(g.paddingTiles) || 0) * (Number(g.tileM) || 2.0);
                        this.renderer.setVillageMapBounds({
                            min_x: g.originX + padM,
                            min_z: g.originZ + padM,
                            max_x: g.originX + g.w * g.tileM - padM,
                            max_z: g.originZ + g.h * g.tileM - padM,
                        });
                        this.renderer.setVillageMapOverlayFlipZ(this._villageMapOverlayFlipZ);
                        this.renderer.setVillageMapOverlay(this._villageMapOverlay, this._villageMapOverlayAlpha);
                        this.renderer.setVillageMapOverlayScale(this._villageMapOverlayScale);
                        this.renderer.setVillageMapOverlayOffset(this._villageMapDx, this._villageMapDz);
                        this.renderer.setVillageMapPrettyTransform({
                            flipZ: this._villageMapPrettyFlipZ,
                            scale: this._villageMapPrettyScale,
                        });
                        this.addLog("Grille collisions village chargée (prédiction client alignée serveur).", "system");
                    }
                })
                .catch(() => {});
        }
    }

    handleMessage(msg) {
        if (msg.type === "welcome" && msg.game_data) {
            if (msg.game_data && typeof msg.game_data === "object") {
                this.gameData = msg.game_data;
            }
        }
        if (msg.type === "world_tick") {
            this.renderer.updateState(msg.entities, msg.world_time_s, msg.day_fraction);
            this.syncPlayerQuestFromServer(msg.entities || [], this.network.playerId);
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
                    subtitle: this._formatRoleSubtitle(target),
                });
                this.recordNpcDialogueAssistant(target.id, msg.npc_reply, msg.trace_id || "");
                this.addNpcJournalLine(target.name, msg.npc_reply, msg.trace_id || "");
            }
            if (msg.world_event) {
                this.handleWorldEvent(msg.world_event, msg.trace_id);
            }
        } else if (msg.type === "error") {
            this.addLog(`Erreur: ${msg.message}`, 'error');
        }
    }

    handleWorldEvent(event, traceId) {
        if (!event || typeof event.type !== "string") {
            return;
        }
        if (event.type === "combat_hit" || event.type === "combat_kill") {
            this.handleCombatEvent(event);
            return;
        }
        if (event.type === "loot" || event.type === "trade") {
            this.handleEconEvent(event);
            return;
        }
        if (event.type === "quest_update" || event.type === "quest_complete") {
            this.handleQuestEvent(event);
            return;
        }
        if (event.type === "job") {
            this.handleJobEvent(event);
            return;
        }
        if (event.type === "door") {
            const status = typeof event.status === "string" ? event.status : "";
            const loc = typeof event.for_location_id === "string" ? event.for_location_id : "";
            this.addLog(`Porte : ${status || "ok"}${loc ? ` (${loc})` : ""}.`, "system");
            return;
        }
        if (event.type !== "dialogue_commit") {
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
            subtitle: this._formatRoleSubtitle(target),
        });
        this.recordWorldEvent(event, target, summary);
        this.addLog(`Action monde (${target.name}): ${summary}`, 'system');
    }

    handleCombatEvent(event) {
        const type = event.type;
        const targetId = typeof event.target_id === "string" ? event.target_id : "";
        const entities = Array.isArray(this.renderer.entities) ? this.renderer.entities : [];
        const tgt = entities.find((e) => e && e.id === targetId);
        const targetName = tgt && tgt.name ? tgt.name : (targetId || "cible");
        if (type === "combat_hit") {
            const amt = Number.isFinite(Number(event.amount)) ? Number(event.amount) : 0;
            const hpLeft = Number.isFinite(Number(event.hp_left)) ? Number(event.hp_left) : null;
            const hpMax = Number.isFinite(Number(event.hp_max)) ? Number(event.hp_max) : null;
            const hpTxt = (hpLeft != null && hpMax != null) ? ` (${hpLeft}/${hpMax})` : "";
            const summary = `Coup sur ${targetName} : -${amt} HP${hpTxt}`;
            this.addLog(summary, "system");
            if (targetId) {
                this.renderer.setDialogueBubble(targetId, `-${amt} HP`, {
                    speaker: "Combat",
                    traceId: "",
                    kind: "world_event",
                    ttlMs: 1200,
                    subtitle: this._formatRoleSubtitle({ id: targetId }),
                });
            }
        } else if (type === "combat_kill") {
            const summary = `${targetName} est vaincu.`;
            this.addLog(summary, "system");
            if (targetId) {
                this.renderer.setDialogueBubble(targetId, "Vaincu", {
                    speaker: "Combat",
                    traceId: "",
                    kind: "world_event",
                    ttlMs: 2200,
                    subtitle: this._formatRoleSubtitle({ id: targetId }),
                });
            }
            this.isAttacking = false;
        }
    }

    handleEconEvent(event) {
        if (!event || typeof event.type !== "string") return;
        if (event.type === "loot") {
            const coins = Number.isFinite(Number(event.coins)) ? Number(event.coins) : 0;
            if (coins > 0) {
                this.addLog(`Butin : +${coins} bronze.`, "system");
            }
            return;
        }
        if (event.type === "trade") {
            const status = typeof event.status === "string" ? event.status : "";
            const itemId = typeof event.item_id === "string" ? event.item_id : "";
            const qty = Number.isFinite(Number(event.qty)) ? Number(event.qty) : 0;
            const total = Number.isFinite(Number(event.total)) ? Number(event.total) : null;
            const verb = status === "sold" ? "Vendu" : "Acheté";
            const money = total != null ? ` (${total} bronze)` : "";
            this.addLog(`${verb} : ${qty}× ${itemId}${money}`, "system");
        }
    }

    handleQuestEvent(event) {
        const type = event.type;
        const qid = typeof event.quest_id === "string" ? event.quest_id : "";
        const title = typeof event.title === "string" ? event.title : "";
        if (type === "quest_update") {
            const status = typeof event.status === "string" ? event.status : "";
            this.addLog(`Quête ${status}: ${title || qid}`, "system");
        } else if (type === "quest_complete") {
            this.addLog(`Quête accomplie: ${title || qid}`, "system");
        }
    }

    handleJobEvent(event) {
        const kind = typeof event.kind === "string" ? event.kind : "";
        if (kind === "gather") {
            this.addLog("Récolte: +1 brindille.", "system");
        } else if (kind === "craft") {
            this.addLog("Craft: recette exécutée.", "system");
        }
    }

    tryQuestAccept() {
        const target = this.getDialogueTarget();
        const npcId = target && target.id ? target.id : "";
        const p = this.playerLocalPos;
        const avail = this._availableQuestsForNpc(npcId);
        const sel = String(this.selectedQuestId || "").trim();
        let questId = sel && avail.some((q) => q && q.id === sel) ? sel : "";
        if (!questId && avail.length) {
            questId = typeof avail[0]?.id === "string" ? avail[0].id : "";
        }
        if (!questId) {
            this.addLog("Quête : aucune quête disponible pour ce PNJ.", "system");
            return;
        }
        this.network.sendQuest({ action: "accept", questId, npcId, position: p });
    }

    tryQuestTurnin() {
        const target = this.getDialogueTarget();
        const npcId = target && target.id ? target.id : "";
        const p = this.playerLocalPos;
        this.network.sendQuest({ action: "turnin", questId: "", npcId, position: p });
    }

    _availableQuestsForNpc(npcId) {
        const id = String(npcId || "").trim();
        const all = Array.isArray(this.gameData.quests) ? this.gameData.quests : [];
        const byNpc = all.filter((q) => q && q.giver_npc_id === id);
        if (!byNpc.length) return [];

        // Ordre déterministe : champ "order" si présent, sinon par id.
        byNpc.sort((a, b) => {
            const ao = Number.isFinite(Number(a.order)) ? Number(a.order) : 0;
            const bo = Number.isFinite(Number(b.order)) ? Number(b.order) : 0;
            if (ao !== bo) return ao - bo;
            const aid = typeof a.id === "string" ? a.id : "";
            const bid = typeof b.id === "string" ? b.id : "";
            return aid.localeCompare(bid);
        });

        // Règle : un PNJ ne propose qu'une quête à la fois.
        // On renvoie la première quête de la chaîne qui n'est pas encore complétée.
        for (const q of byNpc) {
            const qid = typeof q.id === "string" ? q.id.trim() : "";
            if (!qid) continue;
            const log = this.questLogById.get(qid);
            if (!log || !log.completed) {
                return [q];
            }
        }
        // Toutes les quêtes de ce PNJ sont complétées : rien à proposer.
        return [];
    }

    _pickNearestResourceId() {
        const locs = Array.isArray(this.renderer.locations) ? this.renderer.locations : [];
        const px = Number(this.playerLocalPos.x || 0);
        const pz = Number(this.playerLocalPos.z || 0);
        let best = null;
        for (const loc of locs) {
            if (!loc || loc.type !== "resource") continue;
            const dx = px - Number(loc.x || 0);
            const dz = pz - Number(loc.z || 0);
            const d2 = dx * dx + dz * dz;
            if (!best || d2 < best.d2) best = { id: loc.id, d2 };
        }
        return best ? best.id : "";
    }

    // Override gather button to be positionnel
    tryGather() {
        const rid = this._pickNearestResourceId();
        const p = this.playerLocalPos;
        this.network.sendJob({ action: "gather", kind: "brindille", resourceId: rid, position: p });
    }

    _pickNearestDoorId(maxDistanceM = 10.0) {
        const locs = Array.isArray(this.renderer.locations) ? this.renderer.locations : [];
        const px = Number(this.playerLocalPos.x || 0);
        const pz = Number(this.playerLocalPos.z || 0);
        const max = Number(maxDistanceM);
        const max2 = Number.isFinite(max) && max > 0 ? max * max : 100;
        let best = null;
        for (const loc of locs) {
            if (!loc || loc.type !== "door") continue;
            const dx = px - Number(loc.x || 0);
            const dz = pz - Number(loc.z || 0);
            const d2 = dx * dx + dz * dz;
            if (d2 > max2) continue;
            if (!best || d2 < best.d2) best = { id: loc.id, d2 };
        }
        return best ? best.id : "";
    }

    tryUseDoor() {
        const did = this._pickNearestDoorId(10.0);
        if (!did) {
            this.addLog("Porte : aucune porte à proximité (≤ 10 m).", "system");
            return;
        }
        this.network.sendDoorUse({ doorId: did, position: this.playerLocalPos });
        this.addLog(`Porte : passage via ${did}.`, "system");
    }

    tryTrade(side) {
        const target = this.getDialogueTarget();
        if (!target || !target.id) {
            this.addLog("Commerce : aucune cible PNJ.", "system");
            return;
        }
        let itemId = "";
        let qty = 1;
        if (side === "buy") {
            if (target.id === "npc:merchant") itemId = "item:rations";
            else if (target.id === "npc:innkeeper") itemId = "item:rations";
            else if (target.id === "npc:smith") itemId = "item:iron_ingot";
            else itemId = "item:rations";
        } else {
            if (target.id === "npc:merchant") itemId = "item:brindille";
            else if (target.id === "npc:smith") itemId = "item:iron_ingot";
            else itemId = "item:brindille";
        }
        const p = this.playerLocalPos;
        this.network.sendTrade({
            npcId: target.id,
            side,
            itemId,
            qty,
            position: p,
        });
    }

    toggleAttackOnTarget() {
        const target = this.getDialogueTarget();
        if (!target || !target.id) {
            this.addLog("Combat : aucune cible PNJ.", "system");
            return;
        }
        if (this.isAttacking) {
            this.network.sendCombatStop();
            this.isAttacking = false;
            this.addLog("Combat : arrêt.", "system");
            return;
        }
        this.network.sendCombatStart(target.id);
        this.isAttacking = true;
        this.addLog(`Combat : attaque sur ${target.name}.`, "system");
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
        const completed = flags.quest_completed === true;
        this.questLogById.set(questId, {
            questId,
            step,
            accepted,
            completed,
            npcName: target && target.name ? target.name : "PNJ",
            time: new Date(),
        });
        if (completed && this.activeQuestId === questId) {
            this.setActiveQuest("", { silent: true });
        } else if (
            !completed
            && (!this.activeQuestId || !this.questLogById.has(this.activeQuestId))
        ) {
            this.setActiveQuest(questId, { silent: true });
        }
        this.persistQuestLog();
        this.renderQuestLog();
    }

    /**
     * Alignement client sur l'état quête session serveur (Entity.stats.quest_state).
     */
    syncPlayerQuestFromServer(entities, playerId) {
        const pid = typeof playerId === "string" ? playerId.trim() : "";
        if (!pid || !Array.isArray(entities)) return;
        const me = entities.find((e) => e && e.id === pid && e.kind === "player");
        if (!me || !me.stats || typeof me.stats !== "object") return;
        const qs = me.stats.quest_state;
        if (!qs || typeof qs !== "object") return;
        const questId = typeof qs.quest_id === "string" ? qs.quest_id.trim() : "";
        if (!questId) return;
        const step = Number.isFinite(Number(qs.quest_step)) ? Number(qs.quest_step) : 0;
        const accepted = typeof qs.quest_accepted === "boolean" ? qs.quest_accepted : true;
        const completed = qs.quest_completed === true;
        const prev = this.questLogById.get(questId);
        if (
            prev
            && prev.step === step
            && prev.accepted === accepted
            && prev.completed === completed
        ) {
            return;
        }
        const npcName = prev && prev.npcName ? prev.npcName : "Serveur";
        this.questLogById.set(questId, {
            questId,
            step,
            accepted,
            completed,
            npcName,
            time: prev && prev.time instanceof Date ? prev.time : new Date(),
        });
        if (completed && this.activeQuestId === questId) {
            this.setActiveQuest("", { silent: true });
        } else if (!completed && (!this.activeQuestId || !this.questLogById.has(this.activeQuestId))) {
            this.setActiveQuest(questId, { silent: true });
        } else {
            this.renderQuestLog();
            this.updateActiveQuestHUD();
        }
        this.persistQuestLog();
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
                    completed: typeof row.completed === "boolean" ? row.completed : false,
                    npcName: typeof row.npcName === "string" && row.npcName.trim() ? row.npcName.trim() : "PNJ",
                    time: row.time ? new Date(row.time) : new Date(),
                });
            }
            const activeQuestId = window.localStorage.getItem(ACTIVE_QUEST_STORAGE_KEY) || "";
            if (activeQuestId && this.questLogById.has(activeQuestId)) {
                this.activeQuestId = activeQuestId;
            }
        } catch (_) {
            this.questLogById.clear();
            this.activeQuestId = "";
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

    setActiveQuest(questId, options = {}) {
        const id = typeof questId === "string" ? questId.trim() : "";
        this.activeQuestId = id && this.questLogById.has(id) ? id : "";
        try {
            if (this.activeQuestId) {
                window.localStorage.setItem(ACTIVE_QUEST_STORAGE_KEY, this.activeQuestId);
            } else {
                window.localStorage.removeItem(ACTIVE_QUEST_STORAGE_KEY);
            }
        } catch (_) {}
        this.renderQuestLog();
        this.updateActiveQuestHUD();
        if (!options.silent && this.activeQuestId) {
            this.addLog(`Quête suivie: ${this.activeQuestId}`, "system");
        }
    }

    updateActiveQuestHUD() {
        const el = document.getElementById('active-quest-summary');
        if (!el) return;
        const quest = this.activeQuestId ? this.questLogById.get(this.activeQuestId) : null;
        if (!quest) {
            el.textContent = "Quête suivie : aucune";
            el.classList.add("empty");
            return;
        }
        el.classList.remove("empty");
        const done = Boolean(quest.completed);
        el.textContent = done
            ? `Quête suivie : ${quest.questId} · terminée · ${quest.npcName}`
            : `Quête suivie : ${quest.questId} · étape ${quest.step} · ${quest.npcName}`;
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
            this.updateActiveQuestHUD();
            return;
        }
        for (const quest of quests) {
            const row = document.createElement('div');
            row.className = `world-event quest quest-row ${quest.questId === this.activeQuestId ? "active" : ""} ${quest.completed ? "quest-done" : ""}`;
            row.setAttribute("role", "button");
            row.tabIndex = 0;
            let headline;
            if (quest.completed) headline = `Terminée: ${quest.questId}`;
            else if (quest.accepted) headline = `Acceptée: ${quest.questId}`;
            else headline = `Mise à jour: ${quest.questId}`;
            row.textContent = headline;
            const followQuest = () => this.setActiveQuest(quest.questId);
            row.addEventListener('click', followQuest);
            row.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    followQuest();
                }
            });
            const meta = document.createElement('span');
            meta.className = 'meta';
            meta.textContent = `${quest.npcName} · étape ${quest.step} · ${quest.time.toLocaleTimeString()}`;
            row.appendChild(meta);
            feed.appendChild(row);
        }
        this.updateActiveQuestHUD();
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
            if (me.name) {
                document.getElementById('stat-name').textContent = me.name;
            }
        }
        this.renderPlayerSheet(me || null);
        this.updateDialogueTargetHUD();
        this.updateNpcWorldStateHUD();
    }

    formatRaceSheetHtml(raceIdRaw) {
        const rid = typeof raceIdRaw === "string" ? raceIdRaw.trim() : "";
        if (!rid) return "—";
        const label = this.raceDisplayById[rid];
        if (label && label !== rid) {
            return `${escapeHtml(label)} <span class="muted">(${escapeHtml(rid)})</span>`;
        }
        return escapeHtml(label || rid);
    }

    refreshRaceLabelsOnSheets() {
        const pid = this.network.playerId;
        const entities = Array.isArray(this.renderer.entities) ? this.renderer.entities : [];
        const me = pid ? entities.find((e) => e && e.id === pid && e.kind === "player") : null;
        this.renderPlayerSheet(me || null);
        this.updateNpcWorldStateHUD();
    }

    renderPlayerSheet(me) {
        const el = document.getElementById("player-sheet-body");
        if (!el) return;
        if (!me) {
            el.innerHTML = '<span class="muted">En attente de synchronisation…</span>';
            return;
        }
        const stats = me.stats && typeof me.stats === "object" ? me.stats : {};
        const qs = stats.quest_state && typeof stats.quest_state === "object" ? stats.quest_state : null;
        const raceRaw = typeof me.race_id === "string" ? me.race_id.trim() : "";
        const raceHtml = this.formatRaceSheetHtml(raceRaw);
        const roleRaw = typeof me.role === "string" ? me.role.trim() : "";
        const roleHtml = roleRaw ? escapeHtml(roleRaw) : "—";
        const nid = formatSheetId(me.id);
        const idTitle = escapeHtml(me.id || "");

        let sacBlock =
            '<div class="sheet-section"><div class="sheet-row muted" style="margin-bottom:0.35rem">Sac (session)</div>' +
            '<span class="muted">Vide</span></div>';
        const invRaw = stats.inventory;
        if (Array.isArray(invRaw) && invRaw.length) {
            const lines = invRaw.slice(0, 24).map((row) => {
                if (!row || typeof row !== "object") return null;
                const label =
                    typeof row.label === "string" && row.label.trim()
                        ? row.label.trim()
                        : typeof row.item_id === "string" && row.item_id.trim()
                          ? row.item_id.trim()
                          : "?";
                let qty = row.qty;
                if (!Number.isFinite(Number(qty))) qty = 1;
                else qty = Math.max(0, Math.round(Number(qty)));
                return `<div class="sheet-row"><span class="label">${escapeHtml(label)}</span> <span class="sheet-val">×${qty}</span></div>`;
            }).filter(Boolean);
            if (lines.length) {
                sacBlock = `<div class="sheet-section"><div class="sheet-row muted" style="margin-bottom:0.35rem">Sac (session)</div>${lines.join("")}</div>`;
            }
        }

        let questBlock = '<div class="sheet-row"><span class="label">Quête</span> <span class="muted">aucune (session)</span></div>';
        if (qs && typeof qs.quest_id === "string" && qs.quest_id.trim()) {
            const qid = qs.quest_id.trim();
            const done = qs.quest_completed === true;
            const step = Number.isFinite(Number(qs.quest_step)) ? Number(qs.quest_step) : 0;
            const acc = qs.quest_accepted !== false;
            const qsCls = done ? "good" : "warn";
            questBlock = [
                `<div class="sheet-row"><span class="label">Quête</span> <span class="${qsCls}">${escapeHtml(qid)}</span></div>`,
                `<div class="sheet-row"><span class="label">Étape</span> <span>${step}</span></div>`,
                `<div class="sheet-row"><span class="label">Statut</span> <span>${done ? "terminée" : acc ? "en cours" : "non acceptée"}</span></div>`,
            ].join("");
        }

        const extraKeys = Object.keys(stats).filter((k) => k !== "quest_state" && k !== "inventory");
        let extraBlock = "";
        if (extraKeys.length) {
            const lines = extraKeys.slice(0, 8).map((k) => {
                const v = stats[k];
                let disp;
                if (v === null || v === undefined) disp = "—";
                else if (typeof v === "object") {
                    try {
                        disp = JSON.stringify(v);
                    } catch (_) {
                        disp = String(v);
                    }
                } else disp = String(v);
                if (disp.length > 96) disp = `${disp.slice(0, 93)}…`;
                return `${escapeHtml(k)}: <span class="sheet-val">${escapeHtml(disp)}</span>`;
            });
            extraBlock = `<div class="sheet-section sheet-sub">${lines.join("<br>")}</div>`;
        }

        el.innerHTML = [
            '<div class="sheet-section sheet-identity">',
            `<div class="sheet-row"><span class="label">Nom</span> <span>${escapeHtml(me.name || "—")}</span></div>`,
            `<div class="sheet-row"><span class="label">Rôle</span> <span>${roleHtml}</span></div>`,
            `<div class="sheet-row"><span class="label">Race</span> <span>${raceHtml}</span></div>`,
            `<div class="sheet-row"><span class="label">Id</span> <span class="sheet-mono" title="${idTitle}">${escapeHtml(nid)}</span></div>`,
            "</div>",
            `<div class="sheet-section">${questBlock}</div>`,
            sacBlock,
            extraBlock,
        ].join("");
    }

    renderNpcSheet(npc, target) {
        const el = document.getElementById("npc-sheet-body");
        if (!el) return;
        const tname = target && target.name ? target.name : "";
        const tid = target && target.id ? target.id : "";
        const label = escapeHtml(tname || tid || "PNJ");

        if (!npc) {
            el.innerHTML = `<div class="sheet-section"><span class="muted">Aucune fiche : « ${label} » est absent du monde synchronisé. Approchez-vous ou sélectionnez un PNJ sur la carte.</span></div>`;
            return;
        }

        const raceRaw = typeof npc.race_id === "string" ? npc.race_id.trim() : "";
        const raceHtml = this.formatRaceSheetHtml(raceRaw);
        const roleRaw = typeof npc.role === "string" ? npc.role.trim() : "";
        const roleHtml = roleRaw ? escapeHtml(roleRaw) : "—";
        const nid = formatSheetId(npc.id);
        const idTitle = escapeHtml(npc.id || "");

        const identity = [
            '<div class="sheet-section sheet-identity">',
            `<div class="sheet-row"><span class="label">Nom</span> <span>${escapeHtml(npc.name || "—")}</span></div>`,
            `<div class="sheet-row"><span class="label">Rôle</span> <span>${roleHtml}</span></div>`,
            `<div class="sheet-row"><span class="label">Race</span> <span>${raceHtml}</span></div>`,
            `<div class="sheet-row"><span class="label">Id</span> <span class="sheet-mono" title="${idTitle}">${escapeHtml(nid)}</span></div>`,
            "</div>",
        ].join("");

        const state = npc.world_state && typeof npc.world_state === "object" ? npc.world_state : null;
        let stateHtml;
        if (!state) {
            stateHtml = '<div class="sheet-section muted">État monde : non exposé pour ce PNJ.</div>';
        } else {
            const gauges = typeof state.gauges === "object" && state.gauges ? state.gauges : {};
            const flags = typeof state.flags === "object" && state.flags ? state.flags : {};
            const pct = (value) => `${Math.round(Math.max(0, Math.min(1, Number(value || 0))) * 100)}%`;
            const rep = Number.isFinite(Number(state.reputation)) ? Number(state.reputation) : 0;
            const repClass = rep > 0 ? "good" : rep < 0 ? "warn" : "muted";
            const qdone = flags.quest_completed === true;
            const quest = typeof flags.quest_id === "string" && flags.quest_id.trim()
                ? `<div class="sheet-row"><span class="label">Quête PNJ</span> <span class="warn">${escapeHtml(flags.quest_id.trim())}${
                    qdone ? ' <span class="good">(terminée)</span>' : ""
                }</span></div>`
                : "";
            stateHtml = [
                '<div class="sheet-section">',
                '<div class="sheet-row muted" style="margin-bottom:0.4rem">État monde (serveur)</div>',
                `<div class="sheet-row"><span class="label">Réputation</span> <span class="${repClass}">${rep}</span></div>`,
                `<div class="sheet-row"><span class="label">Faim</span> <span>${pct(gauges.hunger)}</span></div>`,
                `<div class="sheet-row"><span class="label">Soif</span> <span>${pct(gauges.thirst)}</span></div>`,
                `<div class="sheet-row"><span class="label">Fatigue</span> <span>${pct(gauges.fatigue)}</span></div>`,
                quest,
                "</div>",
            ].join("");
        }

        const pstats = npc.stats && typeof npc.stats === "object" ? npc.stats : {};
        const pstatKeys = Object.keys(pstats);
        let statsExtra = "";
        if (pstatKeys.length) {
            const lines = pstatKeys.slice(0, 8).map((k) => {
                const v = pstats[k];
                let disp;
                if (v === null || v === undefined) disp = "—";
                else if (typeof v === "object") {
                    try {
                        disp = JSON.stringify(v);
                    } catch (_) {
                        disp = String(v);
                    }
                } else disp = String(v);
                if (disp.length > 96) disp = `${disp.slice(0, 93)}…`;
                return `${escapeHtml(k)}: <span class="sheet-val">${escapeHtml(disp)}</span>`;
            });
            statsExtra = `<div class="sheet-section sheet-sub"><span class="muted">Stats (serveur)</span><br>${lines.join("<br>")}</div>`;
        }

        el.innerHTML = identity + stateHtml + statsExtra + '<div id="npc-quests-ui"></div>';
        this.renderNpcQuestUi(tid);
    }

    renderNpcQuestUi(npcId) {
        const root = document.getElementById("npc-quests-ui");
        if (!root) return;
        root.innerHTML = "";

        const nid = String(npcId || "").trim();
        if (!nid) return;

        const qs = this._availableQuestsForNpc(nid);
        if (!qs.length) {
            const empty = document.createElement("div");
            empty.className = "sheet-section muted";
            empty.textContent = "Quêtes disponibles : aucune.";
            root.appendChild(empty);
            return;
        }

        const wrap = document.createElement("div");
        wrap.className = "sheet-section";

        const title = document.createElement("div");
        title.className = "sheet-row muted";
        title.style.marginBottom = "0.4rem";
        title.textContent = "Quêtes disponibles";
        wrap.appendChild(title);

        for (const q of qs.slice(0, 6)) {
            const qid = typeof q?.id === "string" ? q.id.trim() : "";
            if (!qid) continue;
            const qtitle = typeof q?.title === "string" && q.title.trim() ? q.title.trim() : qid;

            const row = document.createElement("div");
            row.className = "sheet-row";
            row.style.justifyContent = "space-between";
            row.style.gap = "0.5rem";

            const left = document.createElement("span");
            left.innerHTML = `<span class="label">${escapeHtml(qtitle)}</span> <span class="muted">(${escapeHtml(qid)})</span>`;

            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "mini-action-btn";
            btn.textContent = "Accepter";
            btn.addEventListener("click", () => {
                this.selectedQuestId = qid;
                this.tryQuestAccept();
            });

            row.appendChild(left);
            row.appendChild(btn);
            wrap.appendChild(row);
        }
        root.appendChild(wrap);
    }

    _formatRoleSubtitle(target) {
        if (!target || typeof target.role !== "string") return "";
        const r = target.role.trim();
        if (!r || r === "civil" || r === "player") return "";
        return r.replace(/_/g, " ");
    }

    getDialogueTarget() {
        if (this.selectedDialogueTarget && this.entityExists(this.selectedDialogueTarget.id)) {
            const sel = this.selectedDialogueTarget;
            const ent = (Array.isArray(this.renderer.entities) ? this.renderer.entities : []).find(
                (e) => e && e.id === sel.id
            );
            const role = typeof ent?.role === "string" ? ent.role : sel.role;
            return {
                id: sel.id,
                name: sel.name,
                role: typeof role === "string" ? role : "",
            };
        }

        const entities = Array.isArray(this.renderer.entities) ? this.renderer.entities : [];
        const npcs = entities.filter((ent) => ent && ent.kind === "npc" && typeof ent.id === "string");
        if (!npcs.length) {
            return { id: "npc:merchant", name: "Marchand", role: "merchant" };
        }

        const nearest = npcs
            .map((ent) => {
                const dx = Number(ent.x || 0) - Number(this.playerLocalPos.x || 0);
                const dz = Number(ent.z || 0) - Number(this.playerLocalPos.z || 0);
                return { ent, dist2: dx * dx + dz * dz };
            })
            .sort((a, b) => a.dist2 - b.dist2)[0].ent;

        return {
            id: nearest.id,
            name: nearest.name || nearest.id,
            role: typeof nearest.role === "string" ? nearest.role : "",
        };
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

        this.selectedDialogueTarget = {
            id: npc.id,
            name: npc.name || npc.id,
            role: typeof npc.role === "string" ? npc.role : "",
        };
        this.lastDialogueTarget = this.selectedDialogueTarget;
        this.renderer.setSelectedEntityId(npc.id);
        this.updateDialogueTargetHUD();
        this.updateNpcWorldStateHUD();
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
        const target = this.getDialogueTarget();
        const entities = Array.isArray(this.renderer.entities) ? this.renderer.entities : [];
        const npc = entities.find((ent) => ent && ent.id === target.id && ent.kind === "npc");
        this.renderNpcSheet(npc || null, target);
    }

    /**
     * Une ligne de journal par tour de dialogue WS : le placeholder et la réplique finale partagent le même trace_id,
     * on met à jour la même ligne au lieu de dupliquer.
     */
    addNpcJournalLine(npcName, text, traceId) {
        const label = String(npcName || "PNJ").trim();
        const body = String(text || "").trim();
        if (!body) return;
        const tid = String(traceId || "").trim();
        const consoleLogs = document.getElementById("console-logs");
        if (!consoleLogs) return;
        const stamp = `[${new Date().toLocaleTimeString()}]`;
        const full = `${stamp} ${label}: ${body}`;
        if (tid && this._npcLogRowByTraceId.has(tid)) {
            const row = this._npcLogRowByTraceId.get(tid);
            row.textContent = full;
            this._npcLogRowByTraceId.delete(tid);
            consoleLogs.scrollTop = consoleLogs.scrollHeight;
            return;
        }
        const row = document.createElement("div");
        row.className = "log npc";
        row.textContent = full;
        consoleLogs.appendChild(row);
        consoleLogs.scrollTop = consoleLogs.scrollHeight;
        if (tid) this._npcLogRowByTraceId.set(tid, row);
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
                const bobbing = Math.sin((time || now) / 220) * 0.85;
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
            let newX = this.playerLocalPos.x + move.x * speed;
            let newZ = this.playerLocalPos.z + move.y * speed;
            if (this.collisionGrid && !this.collisionGrid.isWalkableWorldM(newX, newZ)) {
                newX = this.playerLocalPos.x;
                newZ = this.playerLocalPos.z;
            }
            this.network.sendMove(newX, 0, newZ);
        }
    }
}

// Lancer l'application
new App();
