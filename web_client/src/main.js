import { NetworkManager } from './network.js';
import { Renderer } from './renderer.js';
import { InputManager } from './input.js';

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
        
        this.initUI();
    }

    initUI() {
        const connectBtn = document.getElementById('connect-btn');
        const playerNameInput = document.getElementById('player-name');
        const chatInput = document.getElementById('chat-msg');
        const sendChatBtn = document.getElementById('send-chat-btn');

        connectBtn.addEventListener('click', () => {
            const name = playerNameInput.value.trim() || "Voyageur";
            this.connect(name);
        });

        // Entrée clavier pour la connexion
        playerNameInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') connectBtn.click();
        });

        // Chat
        sendChatBtn.addEventListener('click', () => {
            const text = chatInput.value.trim();
            if (text) {
                // Pour simplifier, on envoie le chat au dernier PNJ vu ou un PNJ par défaut
                this.network.sendChat(text, "npc:merchant", "Marchand");
                this.addLog(`To Merchant: ${text}`, 'player');
                chatInput.value = "";
            }
        });

        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendChatBtn.click();
        });
    }

    async connect(name) {
        try {
            const serverHost = document.getElementById('server-url').value.trim() || window.location.hostname;
            document.getElementById('login-screen').classList.add('hidden');
            this.addLog("Connexion au multivers...");
            
            const wsUrl = `ws://${serverHost}:7733`;
            const welcomeData = await this.network.connect(wsUrl, name);
            
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
        this.renderer.setPlayerId(data.player_id);
        
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
            this.updateHUD(msg);
            
            // Gérer les répliques PNJ (pont IA)
            if (msg.npc_reply) {
                this.addLog(`Marchand: ${msg.npc_reply}`, 'npc');
            }
        } else if (msg.type === "error") {
            this.addLog(`Erreur: ${msg.message}`, 'error');
        }
    }

    handleDisconnect() {
        document.getElementById('disconnect-screen').classList.remove('hidden');
    }

    updateHUD(msg) {
        document.getElementById('world-time').textContent = this.formatTime(msg.world_time_s);
        
        const me = msg.entities.find(e => e.id === this.network.playerId);
        if (me) {
            document.getElementById('pos-x').textContent = Math.round(me.x);
            document.getElementById('pos-y').textContent = Math.round(me.y);
            this.playerLocalPos = { x: me.x, y: me.y, z: me.z };
        }
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
            const newY = this.playerLocalPos.y + move.y * speed;
            
            // Note: On pourrait faire de la prédiction côté client, 
            // mais ici on envoie juste l'intention au serveur.
            this.network.sendMove(newX, newY, this.playerLocalPos.z);
        }
    }
}

// Lancer l'application
new App();
