/**
 * Gestion de la communication WebSocket avec le serveur mmmorpg_server.
 */
export class NetworkManager {
    constructor(onMessage, onDisconnect) {
        this.ws = null;
        this.onMessage = onMessage;
        this.onDisconnect = onDisconnect;
        this.playerId = null;
    }

    connect(url, playerName) {
        return new Promise((resolve, reject) => {
            try {
                this.ws = new WebSocket(url);
                
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
                        resolve(data);
                    }
                    
                    this.onMessage(data);
                };

                this.ws.onerror = (err) => {
                    console.error("Erreur WebSocket:", err);
                    reject(err);
                };

                this.ws.onclose = () => {
                    console.log("Connexion WebSocket fermée");
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

    sendChat(text, targetNpcId, npcName) {
        // Le protocole supporte l'envoi de texte via le message 'move' (pont IA)
        // ou d'autres extensions selon docs/mmmorpg_PROTOCOL.md
        this.send({
            type: "move",
            x: 0, y: 0, z: 0, // Placeholder position si on veut juste parler
            world_npc_id: targetNpcId,
            npc_name: npcName,
            text: text
        });
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
        }
    }
}
