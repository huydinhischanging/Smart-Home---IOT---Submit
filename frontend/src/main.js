// --- STYLES ---
import './styles/dashboard.css'
import './styles/login.css'
import './styles/theme-serene.css'
import './styles/theme-luxury.css'

// NOTE:
// This entrypoint powers the SPA/Vite frontend under src/.
// The Tactical dashboard uses frontend/index.html and its own AlertsCenter block.
// See frontend/ALERTS_ARCHITECTURE.md before changing alert behavior.

// --- PINIA STATE MANAGEMENT ---
import { pinia, useAuthStore, useDeviceStore, useAlertStore, useUIStore, initializeStores } from './stores/index.js'
import { initSocket } from './services/socket.client.js'

// --- CORE SERVICES & CONTROLLERS ---
import { initDashboardController } from './dashboard/dashboard.controller.js'
import { themeManager } from "./modules/theme/theme.manager.js"
import { alertController } from "./modules/alert/alert.controller.js"
import { sensorController } from "./modules/sensor/sensor.controller.js"

// --- SENSOR & ECG MODULE ---
import { BatECG } from "./modules/sensor/sensor.chart.js"

// --- COMPANION (ALFRED/ORACLE) MODULES ---
import { batTerminal } from "./modules/companion/terminal.js"
import { renderDiagnostic, updateWellnessIndex, setUserName } from "./modules/companion/chat.panel.js"
import { voiceController } from "./modules/companion/voice.controller.js"
import { initMapRoomSelector } from "./modules/map/map.room-selector.js"
import { clearAuthSession } from './services/auth.storage.js'

// --- SCHEDULE MODULE ---
import { initSchedulePanel, SchedulePanel } from './modules/schedule/device_schedule.panel.js'
import { initScheduleReminder } from './modules/schedule/schedule.reminder.js'

// ==========================================
// 🫀 ECG MONITOR LOGIC
// ==========================================
let ecgMonitor = null

function startECG() {
  const canvas = document.getElementById('ecg-canvas')
  if (!canvas) {
    console.warn('[ECG] canvas not found')
    return
  }

  ecgMonitor = new BatECG('ecg-canvas')

  function animateECG() {
    const currentHR =
      parseInt(document.querySelector('.elderly-value')?.innerText) || 70

    ecgMonitor.draw(currentHR)
    requestAnimationFrame(animateECG)
  }

  animateECG()
}

// ==========================================
// 📂 UI HELPERS
// ==========================================
window.toggleDeviceFolder = function () {
  const folder = document.getElementById('device-folder')
  if (!folder) {
    console.warn('[UI] device-folder not found')
    return
  }
  folder.classList.toggle('collapsed')
}

// ==========================================
// ⌨️ TERMINAL ENTER LISTENER
// ==========================================
document.addEventListener('keydown', (e) => {
    const input = document.getElementById('terminal-input');
    if (e.key === 'Enter' && document.activeElement === input) {
        batTerminal.processCommand(input.value);
        input.value = ""; 
    }
});

// ==========================================
// 🚀 APP START (DOM READY)
// ==========================================
document.addEventListener('DOMContentLoaded', async () => {
  // Initialize Pinia first
  const authStore = useAuthStore()
  const deviceStore = useDeviceStore()
  const alertStore = useAlertStore()
  const uiStore = useUIStore()

  // Check if user is authenticated
  if (!authStore.token) {
    console.warn('[App] No authentication token, redirecting to login')
    window.location.href = '/login'
    return
  }

  // Load user profile
  const userLoaded = await authStore.loadUser()
  if (!userLoaded) {
    console.error('[App] Failed to load user profile')
    alertStore.addError('Failed to load user profile')
    window.location.href = '/login'
    return
  }

  // Initialize Socket.IO
  const socket = initSocket(authStore.token)

  // Init schedule reminder popup (listens to socket events)
  initScheduleReminder(socket)

  // Load devices
  await deviceStore.fetchDevices(authStore.getAuthHeader())

  // Set initial theme
  uiStore.setTheme(uiStore.theme)

  // Khởi tạo Dashboard (giao diện + controller)
  const { initDashboard } = await import('./dashboard/index.js');
  await initDashboard();
  await alertController.init()

  // Click Listeners
  document.addEventListener('click', (e) => {
    if (e.target.id === 'toggleDevicesBtn') {
      toggleDeviceFolder()
    }
    if (e.target.closest('.folder-header')) {
      toggleDeviceFolder()
    }
    // Logout button
    if (e.target.id === 'logout-btn' || e.target.closest('#logout-btn')) {
      authStore.logout()
      window.location.href = '/login'
    }
  })

  // --- KHỞI TẠO ORACLE TERMINAL HUD ---
  const terminalContainer = document.getElementById('terminal-container')
  if (terminalContainer) {
    terminalContainer.innerHTML = batTerminal.render()
  }

  // --- KHỞI TẠO VOICE CONTROLLER ---
  voiceController.init()

  // --- KHỞI TẠO MAP ROOM SELECTOR (double-click to select room for Alfred) ---
  initMapRoomSelector('room-overlay-canvas')

  // --- KHỞI TẠO SCHEDULE PANEL ---
  initSchedulePanel().catch(err => console.warn('[Schedule] Init error:', err))

  // --- START ECG ---
  startECG()
})

// ==========================================
// 🔥 PHƠI BÀY CÔNG CỤ RA GLOBAL (WINDOW)
// ==========================================
window.BatTheme = themeManager
window.BatAlert = alertController
window.BatSensor = sensorController
window.BatVoice = voiceController

// SchedulePanel is also exposed in device_schedule.panel.js itself (window.SchedulePanel)
// and ScheduleReminder in schedule.reminder.js (window.ScheduleReminder)

window.BatDiagnostic = {
    // Gọi chẩn đoán sức khỏe (render Alfred chat)
    show: (status) => {
        const container = document.getElementById('diagnostic-container');
        if (container) container.innerHTML = renderDiagnostic(status);
    },
    // Cập nhật HUD điểm sức khỏe (Wellness Index)
    updateHUD: (data) => {
        const container = document.getElementById('wellness-container');
        if (container) container.innerHTML = updateWellnessIndex(data);
    },
    // Thiết lập tên người dùng
    setName: (name) => setUserName(name)
};

console.log("🦇 Bat-Computer: Ready (Terminal, Diagnostic, ECG, Socket online).");