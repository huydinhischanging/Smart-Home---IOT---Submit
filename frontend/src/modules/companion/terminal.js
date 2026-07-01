// src/modules/companion/terminal.js
import { themeManager } from "../theme/theme.manager.js";
import { alertController } from "../alert/alert.controller.js";
import { socket } from "../../services/socket.client.js";

// Import API client for AI chat
const API_BASE = 'http://127.0.0.1:5000';
function getBearerToken() {
    // Try localStorage first
    let token = localStorage.getItem('authToken') || localStorage.getItem('batman_token');
    if (token) return token;
    // If no token, socket will handle auth via cookies
    return null;
}

async function apiCall(endpoint, method = 'POST', data = null) {
    try {
        const token = getBearerToken();
        const headers = {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        };

        // Lấy ngôn ngữ từ localStorage
        const lang = localStorage.getItem('iot_lang') || 'vi';
        headers['X-Lang'] = lang;

        const options = {
            method,
            headers,
            credentials: 'include'  // Include cookies for session auth
        };

        if (data) {
            options.body = JSON.stringify(data);
        }

        const response = await fetch(`${API_BASE}${endpoint}`, options);
        
        if (!response.ok) {
            console.error(`[API] ${endpoint} failed: ${response.status}`);
            return null;
        }

        return await response.json();
    } catch (err) {
        console.error(`[API] ${endpoint} error:`, err);
        return null;
    }
}

export class BatTerminal {

    constructor() {
        this.container = document.getElementById('terminal-container');
        this.initSocketListeners();
        // Lắng nghe sự kiện đổi ngôn ngữ để cập nhật lại giao diện nếu cần
        window.addEventListener('iot-lang-changed', (e) => {
            // Nếu cần, có thể clear hoặc reload lại giao diện AI/chatbot ở đây
            // Ví dụ: this.reloadChatMessages();
            // Hoặc gửi thông báo tới backend nếu cần
            // location.reload(); // nếu muốn reload toàn bộ giao diện
        });
    }

    // =====================================================
    // 🤖 ALFRED PROACTIVE INTELLIGENCE
    // =====================================================
    initSocketListeners() {

        socket.on("ai_advice", (data) => {

            const container = document.getElementById('diagnostic-container');

            if (container) {
                container.innerHTML = `
                    <div class="diagnostic-box active-suggest">
                        <div class="diagnostic-header">👨‍💼 ALFRED INTELLIGENCE</div>
                        <div class="diagnostic-body">${data.msg}</div>
                        <div class="diagnostic-actions" style="margin-top:10px;">
                            <button class="btn-primary"
                                style="padding:5px 10px; font-size:11px;"
                                onclick="themeManager.apply('meditation')">
                                ACCEPT ROUTINE
                            </button>

                            <button class="btn-secondary"
                                style="padding:5px 10px; font-size:11px;"
                                onclick="this.parentElement.parentElement.remove()">
                                DISMISS
                            </button>
                        </div>
                    </div>
                `;
            }

            this.addOutput("SYSTEM", `Analysis received: ${data.title}`);
        });

        // =====================================================
        // 😊 AI MOOD - AUTOMATIC THEME CHANGE
        // =====================================================
        socket.on("ai_mood", (data) => {
            const mood = data.mood ? String(data.mood).toUpperCase() : "NORMAL";
            
            // Map mood to theme
            const moodToTheme = {
                "EMERGENCY": "emergency",    // 🔴 Red alert
                "ELEVATED": "emergency",     // 🔴 Alert state
                "ACTIVE": "focus",           // 🟢 Green, active mode
                "QUIET": "stealth",          // ⚫ Quiet, dimmed
                "SLEEP": "meditation",       // 🔵 Deep blue, calm
                "REST": "meditation",        // 🔵 Blue, relaxed
                "NORMAL": "vigilant",        // 🟡 Yellow, default
                "VIGILANT": "vigilant"       // 🟡 Yellow, alert
            };
            
            const theme = moodToTheme[mood] || "vigilant";
            
            try {
                themeManager.apply(theme);
                console.log(`[ALFRED] Mood detected: ${mood} → Theme: ${theme}`);
                
                // Optional: Show mood indicator notification
                const indicator = document.getElementById('mood-indicator');
                if (indicator) {
                    const moodEmoji = {
                        "EMERGENCY": "🚨",
                        "ELEVATED": "⚠️",
                        "ACTIVE": "💪",
                        "QUIET": "🤫",
                        "SLEEP": "😴",
                        "REST": "😌",
                        "NORMAL": "🦇",
                        "VIGILANT": "🦇"
                    }[mood] || "🦇";
                    
                    indicator.innerHTML = `${moodEmoji} ${mood}`;
                    indicator.style.opacity = "1";
                    
                    setTimeout(() => {
                        indicator.style.opacity = "0.5";
                    }, 3000);
                }
            } catch (err) {
                console.error("[ALFRED] Failed to apply mood theme:", err);
            }
        });
    }

    // =====================================================
    // 🎛 COMMAND PROCESSING
    // =====================================================
    processCommand(input) {

        const rawInput = input.trim();
        const cmd = rawInput.toLowerCase();
        const userName = localStorage.getItem('batman_user_name') || "Master";

        // Check if it's a system command
        const systemCmds = ['status', 'emergency', 'meditation', 'stealth', 'name ', 'clear', 'help'];
        const isSystemCmd = systemCmds.some(c => cmd.startsWith(c) || cmd === c);

        if (!isSystemCmd) {
            // Treat as chat message → send to AI API
            this.processChat(rawInput);
            return;
        }

        // Handle system commands
        let response = "";

        if (cmd === 'status') {

            response = `Vitals are green, ${userName}. All tactical systems operating within baseline parameters.`;

        } else if (cmd === 'emergency') {

            themeManager.apply('emergency');

            alertController.onNewAlert({
                device_code: 'BAT_MANUAL',
                message: `🚨 Emergency: Immediate override by ${userName}.`,
                level: 'CRITICAL',
                created_at: new Date()
            });

            response = "Activating Red Alert. Medical services on standby.";

        } else if (cmd === 'meditation') {

            themeManager.apply('meditation');
            response = "Meditation mode activated. Setting frequencies to alpha waves, sir.";

        } else if (cmd === 'stealth') {

            themeManager.apply('stealth');
            response = "Cloaking dashboard. System in ghost mode.";

        } else if (cmd.startsWith('name ')) {

            const newName = rawInput.split(' ').slice(1).join(' ');

            if (newName) {
                localStorage.setItem('batman_user_name', newName);
                response = `Understood. Identification updated to Master ${newName}.`;
            } else {
                response = "Please provide a valid name, sir.";
            }

        } else if (cmd === 'clear') {

            const output = document.getElementById('terminal-output');
            if (output) output.innerHTML = "";
            return;

        } else if (cmd === 'help') {

            response = "Protocols: STATUS, EMERGENCY, MEDITATION, STEALTH, NAME [val], CLEAR. Or just chat naturally!";

        } else {

            response = "I'm sorry, I didn't quite catch that sequence. Perhaps type 'HELP'?";
        }

        this.addOutput(rawInput, response);
    }

    // =====================================================
    // 💬 CHAT WITH AI (MOOD-AWARE)
    // =====================================================
    async processChat(message) {
        this.addOutput(message, "⏳ Thinking...");

        const data = {
            message: message,
            mode: 'llm'
        };

    const response = await apiCall('/api/ai/chat', 'POST', data);

        if (!response) {
            this.addOutput(message, "🚨 Network error. Please try again.");
            return;
        }

        this.onChatResponse(message, response);
    }

    // =====================================================
    // 🎨 HANDLE AI RESPONSE WITH MOOD
    // =====================================================
    onChatResponse(userMessage, apiResponse) {
        const reply = apiResponse.reply || "I'm having trouble processing that.";
        
        // Remove the "⏳ Thinking..." message
        const terminalOutput = document.getElementById('terminal-output');
        if (terminalOutput) {
            const entries = terminalOutput.querySelectorAll('.terminal-entry');
            const lastEntry = entries[entries.length - 1];
            if (lastEntry && lastEntry.textContent.includes('⏳ Thinking')) {
                lastEntry.remove();
            }
        }

        // Add actual response
        this.addOutput(userMessage, reply);

        // Handle mood detection & theme change
        if (apiResponse.mood_data) {
            this.applyMoodTheme(apiResponse.mood_data);
        }
    }

    // =====================================================
    // 😊 APPLY MOOD-BASED THEME & RECOMMENDATIONS (WITH CONFIRMATION)
    // =====================================================
    applyMoodTheme(moodData) {
        const mood = moodData.detected_mood || "normal";
        const confidence = moodData.confidence || 0;
        const suggestions = moodData.suggestions || {};
        const suggestedTheme = moodData.suggested_theme || "vigilant";

        // Mood emoji mapping
        const moodEmoji = {
            "happy": "😊",
            "sad": "😢",
            "angry": "😠",
            "anxious": "😰",
            "calm": "😌",
            "stressed": "😫",
            "normal": "🦇"
        };

        // Only show confirmation if confidence > 0.3
        if (confidence > 0.3) {
            this.showMoodConfirmation(mood, suggestions, suggestedTheme, moodEmoji[mood] || "🦇");
        }
    }

    // =====================================================
    // ✅ SHOW MOOD CONFIRMATION DIALOG
    // =====================================================
    showMoodConfirmation(mood, suggestions, suggestedTheme, emoji) {
        // Create modal background
        const modalOverlay = document.createElement('div');
        modalOverlay.id = 'mood-confirmation-modal';
        modalOverlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
        `;

        // Create modal content
        const modalContent = document.createElement('div');
        modalContent.style.cssText = `
            background: rgba(20, 20, 20, 0.95);
            border: 2px solid var(--primary-color);
            border-radius: 8px;
            padding: 24px;
            max-width: 400px;
            color: var(--primary-color);
            font-family: monospace;
            box-shadow: 0 0 20px rgba(253, 185, 19, 0.3);
        `;

        const moodName = mood.charAt(0).toUpperCase() + mood.slice(1);
        const moodMessage = suggestions.message_vn || suggestions.suggestion || `Mood detected: ${moodName}`;
        const musicSuggestion = suggestions.music ? `🎵 ${suggestions.music}` : "";

        modalContent.innerHTML = `
            <div style="text-align: center; margin-bottom: 16px;">
                <div style="font-size: 48px; margin-bottom: 8px;">
                    ${emoji}
                </div>
                <div style="font-size: 18px; font-weight: bold; margin-bottom: 8px;">
                    ${moodName} Mood Detected
                </div>
                <div style="font-size: 13px; opacity: 0.8; margin-bottom: 12px;">
                    ${moodMessage}
                </div>
                ${musicSuggestion ? `<div style="font-size: 12px; opacity: 0.7; margin-bottom: 12px;">${musicSuggestion}</div>` : ""}
            </div>

            <div style="background: rgba(253, 185, 19, 0.1); 
                        border-left: 3px solid var(--primary-color);
                        padding: 12px;
                        margin-bottom: 16px;
                        border-radius: 4px;
                        font-size: 12px;">
                <div style="font-weight: bold; margin-bottom: 6px;">
                    🎨 Theme: <span style="color: #4ade80;">${suggestions.theme}</span>
                </div>
                <div style="opacity: 0.8;">
                    Nền sẽ thay đổi để hỗ trợ tâm trạng của bạn
                </div>
            </div>

            <div style="display: flex; gap: 8px; justify-content: center;">
                <button id="mood-ok-btn" 
                        style="flex: 1;
                               padding: 10px;
                               background: linear-gradient(135deg, var(--primary-color), rgba(253, 185, 19, 0.6));
                               border: 1px solid var(--primary-color);
                               color: #000;
                               font-weight: bold;
                               border-radius: 4px;
                               cursor: pointer;
                               font-family: monospace;
                               font-size: 12px;
                               transition: all 0.2s;">
                    ✅ OK - ÁP DỤNG
                </button>
                <button id="mood-cancel-btn" 
                        style="flex: 1;
                               padding: 10px;
                               background: rgba(255, 255, 255, 0.1);
                               border: 1px solid rgba(255, 255, 255, 0.3);
                               color: var(--primary-color);
                               border-radius: 4px;
                               cursor: pointer;
                               font-family: monospace;
                               font-size: 12px;
                               transition: all 0.2s;">
                    ❌ CANCEL
                </button>
            </div>
        `;

        modalOverlay.appendChild(modalContent);
        document.body.appendChild(modalOverlay);

        // Button handlers
        const okBtn = document.getElementById('mood-ok-btn');
        const cancelBtn = document.getElementById('mood-cancel-btn');

        const closeModal = () => {
            if (modalOverlay && modalOverlay.parentNode) {
                modalOverlay.parentNode.removeChild(modalOverlay);
            }
        };

        okBtn.addEventListener('click', () => {
            try {
                themeManager.apply(suggestedTheme);
                console.log(`[ALFRED] Theme applied: ${suggestedTheme}`);
                this.addOutput("SYSTEM", `✅ Theme changed to ${suggestedTheme.toUpperCase()}`);
            } catch (err) {
                console.error("[ALFRED] Failed to apply theme:", err);
            }
            closeModal();
        });

        cancelBtn.addEventListener('click', () => {
            this.addOutput("SYSTEM", "❌ Theme change cancelled");
            closeModal();
        });

        // Hover effects
        okBtn.addEventListener('mouseover', () => {
            okBtn.style.opacity = '0.9';
            okBtn.style.transform = 'scale(1.02)';
        });
        okBtn.addEventListener('mouseout', () => {
            okBtn.style.opacity = '1';
            okBtn.style.transform = 'scale(1)';
        });

        cancelBtn.addEventListener('mouseover', () => {
            cancelBtn.style.opacity = '0.8';
        });
        cancelBtn.addEventListener('mouseout', () => {
            cancelBtn.style.opacity = '1';
        });

        // Auto-close after 15 seconds if no action
        setTimeout(() => {
            closeModal();
        }, 15000);
    }

    // =====================================================
    // 🎵 SHOW RECOMMENDATIONS
    // =====================================================
    showRecommendations(mood, suggestions, emoji) {
        if (!suggestions) return;

        // Map suggestions to display message
        const recommendationBox = document.getElementById('mood-recommendations');
        if (!recommendationBox) return;

        const action = suggestions.action || "";
        const message_vn = suggestions.message_vn || suggestions.suggestion || "";
        const music = suggestions.music || "";

        let html = `
            <div style="background:rgba(253,185,19,0.1); 
                        border-left:3px solid var(--primary-color);
                        border-radius:4px;
                        padding:10px;
                        margin-top:8px;
                        font-size:12px;
                        color:var(--primary-color);">
                <div style="font-weight:bold; margin-bottom:5px;">
                    ${emoji} ${mood.toUpperCase()} Mood Detected
                </div>
                <div style="font-size:11px; opacity:0.9;">
                    ${message_vn}
                </div>
        `;

        if (music) {
            html += `<div style="margin-top:5px; opacity:0.8;">🎵 ${music}</div>`;
        }

        html += `</div>`;

        recommendationBox.innerHTML = html;
        recommendationBox.style.display = "block";

        // Auto-hide after 8 seconds
        setTimeout(() => {
            recommendationBox.style.display = "none";
        }, 8000);
    }

    // =====================================================
    // 🖥 TERMINAL OUTPUT
    // =====================================================
    addOutput(input, output) {

        const terminalOutput = document.getElementById('terminal-output');
        if (!terminalOutput) return;

        const entry = `
            <div class="terminal-entry" style="margin-bottom:8px;">
                <div class="terminal-user" style="opacity:0.4; font-size:11px;">
                    > ${input.toUpperCase()}
                </div>
                <div class="terminal-alfred" style="color:#4ade80;">
                    👨‍💼 [ALFRED]: ${output}
                </div>
            </div>
        `;

        terminalOutput.insertAdjacentHTML('beforeend', entry);
        terminalOutput.scrollTop = terminalOutput.scrollHeight;
    }

    // =====================================================
    // 🎨 RENDER
    // =====================================================
    render() {
        return `
            <div class="terminal-box"
                 style="border:1px solid rgba(253,185,19,0.2);
                        border-radius:8px;
                        overflow:hidden;">

                <div class="terminal-header"
                     style="background:rgba(0,0,0,0.5);
                            color:var(--bat-yellow);
                            font-family:'Russo One';
                            font-size:10px;
                            padding:8px;
                            letter-spacing:1px;">
                    🛡️ ALFRED COMMAND INTERFACE
                </div>

                <div id="terminal-output"
                     class="terminal-screen"
                     style="height:140px;
                            overflow-y:auto;
                            background:rgba(0,0,0,0.4);
                            padding:12px;
                            font-family:monospace;
                            font-size:13px;
                            line-height:1.5;">
                </div>

                <div id="mood-recommendations"
                     style="display:none;
                            padding:10px 12px;
                            background:rgba(0,0,0,0.3);
                            border-top:1px solid rgba(253,185,19,0.1);
                            font-size:12px;">
                </div>

                <div style="display:flex;
                            align-items:center;
                            background:rgba(20,20,20,0.9);
                            padding:8px 12px;
                            border-top:1px solid #222;">

                    <span style="color:var(--bat-yellow);
                                 margin-right:10px;
                                 font-weight:bold;">
                        >
                    </span>

                    <input id="terminal-input"
                           placeholder="Chat with Alfred or type a command..."
                           autocomplete="off"
                           style="flex:1;
                                  background:transparent;
                                  border:none;
                                  color:var(--bat-yellow);
                                  font-family:monospace;
                                  outline:none;
                                  font-size:14px;">
                </div>
            </div>
        `;
    }
}

export const batTerminal = new BatTerminal();