export class ThemeManager {
    constructor() {
        const saved = localStorage.getItem('batman_theme') || 'vigilant';
        this.currentMood = saved;
        // Restore saved theme after the DOM is ready
        document.addEventListener('DOMContentLoaded', () => this.apply(this.currentMood));
    }

    apply(mode) {

        const modeName = mode.toLowerCase();
        this.currentMood = modeName;
        localStorage.setItem('batman_theme', modeName);

        // Gắn attribute để CSS phản ứng theo mode
        document.body.setAttribute('data-mode', modeName);

        // ==========================================
        // 🎛 OPERATING MODE COLOR SYSTEM
        // ==========================================
        const colors = {

            emergency: {
                main: '#FF0000',
                glow: 'rgba(255, 0, 0, 0.6)',
                background: '#1a0000'
            },

            vigilant: {
                main: '#FDB913',
                glow: 'rgba(253, 185, 19, 0.4)',
                background: '#0f172a'
            },

            stealth: {
                main: '#6B7280',
                glow: 'rgba(107, 114, 128, 0.2)',
                background: '#111111'
            },

            meditation: {
                main: '#00d4ff',
                glow: 'rgba(0, 212, 255, 0.4)',
                background: '#071c24'
            },

            focus: {
                main: '#4ade80',
                glow: 'rgba(74, 222, 128, 0.4)',
                background: '#0b1f17'
            },

            medical: {
                main: '#3b82f6',
                glow: 'rgba(59, 130, 246, 0.5)',
                background: '#0a1a2f'
            }
        };

        const config = colors[modeName] || colors.vigilant;

        // ==========================================
        // 🎨 UPDATE GLOBAL CSS VARIABLES
        // ==========================================
        document.documentElement.style.setProperty('--primary-color', config.main);
        document.documentElement.style.setProperty('--glow-color', config.glow);
        document.documentElement.style.setProperty('--bg-accent', config.background);

        console.log(`[SYSTEM]: Operating mode switched to ${modeName.toUpperCase()}`);
    }
}

export const themeManager = new ThemeManager();