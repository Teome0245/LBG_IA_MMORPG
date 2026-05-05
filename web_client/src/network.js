/**
 * Gestion de la communication WebSocket avec le serveur mmmorpg_server.
 */
export class NetworkManager {
    constructor(onMessage, onDisconnect) {
        this.ws = null;
        this.onMessage = onMessage;
        this.onDisconnect = onDisconnect;
        this.playerId = null;
        this._manualClose = false;
        this._reconnectTimer = null;
        this._reconnectAttempt = 0;
        this._lastConnectArgs = null; // { url, playerName }
    }

    connect(url, playerName, opts = {}) {
        const {
            welcomeTimeoutMs = 6000,
            autoReconnect = false,
            reconnectMaxDelayMs = 5000,
        } = opts || {};

        this._manualClose = false;
        this._lastConnectArgs = { url, playerName, opts: { welcomeTimeoutMs, autoReconnect, reconnectMaxDelayMs } };

        return new Promise((resolve, reject) => {
            try {
                this.ws = new WebSocket(url);

                let welcomeTimer = null;
                const clearWelcomeTimer = () => {
                    if (welcomeTimer) {
                        clearTimeout(welcomeTimer);
                        welcomeTimer = null;
                    }
                };
                welcomeTimer = setTimeout(() => {
                    try {
                        clearWelcomeTimer();
                        // Si aucun welcome n'arrive, on force une fermeture pour déclencher le flux d'erreur / reconnexion.
                        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                            this.ws.close();
                        }
                        reject(new Error("Timeout: welcome non reçu"));
                    } catch (e) {
                        reject(e);
                    }
                }, welcomeTimeoutMs);
                
                this.ws.onopen = () => {
                    console.log("Connecté au serveur WebSocket");
                    let resumeToken = null;
                    try {
                        resumeToken = window.localStorage.getItem("lbg-mmo.ws.sessionToken.v1");
                    } catch (_) {
                        resumeToken = null;
                    }
                    this.send({
                        type: "hello",
                        player_name: playerName
                        ,
                        resume_token: (typeof resumeToken === "string" && resumeToken.trim()) ? resumeToken.trim() : undefined
                    });
                };

                this.ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === "welcome") {
                        this.playerId = data.player_id;
                        if (typeof data.session_token === "string" && data.session_token.trim()) {
                            try {
                                window.localStorage.setItem("lbg-mmo.ws.sessionToken.v1", data.session_token.trim());
                            } catch (_) {
                                // ignore
                            }
                        }
                        this._reconnectAttempt = 0;
                        clearWelcomeTimer();
                        resolve(data);
                    }
                    
                    this.onMessage(data);
                };

                this.ws.onerror = (err) => {
                    console.error("Erreur WebSocket:", err);
                    clearWelcomeTimer();
                    reject(err);
                };

                this.ws.onclose = () => {
                    console.log("Connexion WebSocket fermée");
                    clearWelcomeTimer();

                    if (this._manualClose) {
                        return;
                    }

                    if (autoReconnect) {
                        this._scheduleReconnect();
                        return;
                    }

                    this.onDisconnect();
                };

            } catch (err) {
                reject(err);
            }
        });
    }

    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }

    sendMove(x, y, z) {
        this.send({
            type: "move",
            x, y, z
        });
    }

    /**
     * Même position qu'un move normal + commit PNJ sans LLM (jalon interactions objets).
     * Ne pas envoyer text/world_npc_id sur le même message si le commit doit s'appliquer : le serveur les refuse avec world_commit.
     * @param {number} x
     * @param {number} y
     * @param {number} z
     * @param {{ npc_id: string, trace_id: string, flags?: Record<string, unknown> }} worldCommit
     */
    sendMoveWithWorldCommit(x, y, z, worldCommit) {
        const wc = worldCommit && typeof worldCommit === "object" ? worldCommit : null;
        if (!wc || typeof wc.npc_id !== "string" || typeof wc.trace_id !== "string") {
            console.warn("sendMoveWithWorldCommit: npc_id et trace_id requis");
            return;
        }
        const payload = {
            type: "move",
            x: Number.isFinite(x) ? x : 0,
            y: Number.isFinite(y) ? y : 0,
            z: Number.isFinite(z) ? z : 0,
            world_commit: {
                npc_id: wc.npc_id,
                trace_id: wc.trace_id,
                flags: wc.flags && typeof wc.flags === "object" ? wc.flags : undefined,
            },
        };
        this.send(payload);
    }

    sendChat(text, targetNpcId, npcName, position = null, iaContext = null) {
        // Le protocole supporte l'envoi de texte via le message 'move' (pont IA)
        // ou d'autres extensions selon docs/mmmorpg_PROTOCOL.md
        const pos = position || {};
        const payload = {
            type: "move",
            x: Number.isFinite(pos.x) ? pos.x : 0,
            y: Number.isFinite(pos.y) ? pos.y : 0,
            z: Number.isFinite(pos.z) ? pos.z : 0,
            world_npc_id: targetNpcId,
            npc_name: npcName,
            text: text
        };
        if (iaContext && typeof iaContext === "object") {
            payload.ia_context = iaContext;
        }
        this.send(payload);
    }

    sendCombatStart(targetNpcId) {
        this.send({
            type: "combat",
            action: "start",
            target_id: typeof targetNpcId === "string" ? targetNpcId : "",
        });
    }

    sendCombatStop() {
        this.send({
            type: "combat",
            action: "stop",
        });
    }

    sendTrade({ npcId, side, itemId, qty, position }) {
        const pos = position || {};
        this.send({
            type: "trade",
            npc_id: typeof npcId === "string" ? npcId : "",
            side: typeof side === "string" ? side : "",
            item_id: typeof itemId === "string" ? itemId : "",
            qty: Number.isFinite(Number(qty)) ? Number(qty) : 1,
            x: Number.isFinite(Number(pos.x)) ? Number(pos.x) : 0,
            y: Number.isFinite(Number(pos.y)) ? Number(pos.y) : 0,
            z: Number.isFinite(Number(pos.z)) ? Number(pos.z) : 0,
            trace_id: `trade-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
        });
    }

    disconnect() {
        this._manualClose = true;
        if (this._reconnectTimer) {
            clearTimeout(this._reconnectTimer);
            this._reconnectTimer = null;
        }
        if (this.ws) {
            this.ws.close();
        }
    }

    _scheduleReconnect() {
        if (!this._lastConnectArgs) {
            this.onDisconnect();
            return;
        }
        if (this._reconnectTimer) return;

        const { url, playerName, opts } = this._lastConnectArgs;
        const baseDelay = 300;
        const jitter = Math.floor(Math.random() * 200);
        const delay = Math.min((baseDelay * (2 ** this._reconnectAttempt)) + jitter, opts.reconnectMaxDelayMs || 5000);
        this._reconnectAttempt = Math.min(this._reconnectAttempt + 1, 10);

        this._reconnectTimer = setTimeout(async () => {
            this._reconnectTimer = null;
            try {
                await this.connect(url, playerName, opts);
                // Le "welcome" aura relancé _reconnectAttempt=0 + playerId.
            } catch (_) {
                this._scheduleReconnect();
            }
        }, delay);
    }
}
