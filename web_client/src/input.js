/**
 * Gestion des entrées clavier pour le mouvement.
 */
export class InputManager {
    constructor() {
        this.keys = {};
        
        window.addEventListener('keydown', (e) => {
            this.keys[e.code] = true;
        });

        window.addEventListener('keyup', (e) => {
            this.keys[e.code] = false;
        });
    }

    /**
     * Retourne le vecteur de mouvement souhaité.
     */
    getMovementVector() {
        let x = 0;
        let y = 0;

        // Mappage des touches (Support WASD et ZSQD via e.code)
        // KeyW -> Z on AZERTY, W on QWERTY
        // KeyS -> S on both
        // KeyA -> Q on AZERTY, A on QWERTY
        // KeyD -> D on both
        
        if (this.keys['KeyW'] || this.keys['ArrowUp'] || this.keys['KeyZ']) y -= 1;
        if (this.keys['KeyS'] || this.keys['ArrowDown']) y += 1;
        if (this.keys['KeyA'] || this.keys['ArrowLeft'] || this.keys['KeyQ']) x -= 1;
        if (this.keys['KeyD'] || this.keys['ArrowRight']) x += 1;

        // Normalisation (optionnelle pour un MMO simple mais recommandée pour éviter d'aller plus vite en diagonale)
        if (x !== 0 && y !== 0) {
            const length = Math.sqrt(x * x + y * y);
            x /= length;
            y /= length;
        }

        return { x, y };
    }
}
