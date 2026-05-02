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
                    this.send({
                        type: "hello",
                        player_name: playerName
                    });
                };

                this.ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === "welcome") {
                        this.playerId = data.player_id;
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
