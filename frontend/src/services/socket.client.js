import { io } from 'socket.io-client'
import { useDeviceStore } from '../stores/device.store'
import { useAlertStore } from '../stores/alert.store'
import { useUIStore } from '../stores/ui.store'
import { alertController } from '../modules/alert/alert.controller.js'

let socket = null

// ─── SOS Recording Modal (self-contained, injected into DOM) ────────────────
let _sosRec = null   // MediaRecorder instance
let _sosChunks = []  // recorded chunks
let _sosTimer = null // countdown timer interval
let _sosSecs = 0

function _openSosModal () {
  // Remove old modal if present
  const old = document.getElementById('_sos_rec_modal')
  if (old) old.remove()

  const css = `
    #_sos_rec_modal{position:fixed;inset:0;background:rgba(0,0,0,.82);z-index:99999;display:flex;align-items:center;justify-content:center;}
    #_sos_rec_box{background:#12001a;border:2px solid #dc2626;border-radius:14px;padding:28px 30px;max-width:400px;width:92%;color:#f1f5f9;font-family:sans-serif;box-shadow:0 0 40px rgba(220,38,38,.5);}
    #_sos_rec_box h2{color:#ef4444;margin:0 0 6px;font-size:1.15rem;display:flex;align-items:center;gap:8px;}
    #_sos_rec_box p{color:#94a3b8;font-size:.82rem;margin:0 0 18px;line-height:1.5;}
    #_sos_rec_box strong{color:#fbbf24;}
    ._sos_btn{border:none;border-radius:7px;padding:9px 20px;cursor:pointer;font-weight:700;font-size:.88rem;}
    #_sos_start{background:#dc2626;color:#fff;animation:sosPulse 1.1s ease-in-out infinite;}
    #_sos_stop{background:#7f1d1d;color:#fff;display:none;}
    #_sos_send{background:#16a34a;color:#fff;flex:1;display:none;}
    #_sos_close{background:#374151;color:#ccc;}
    #_sos_timer{color:#fbbf24;font-weight:700;font-size:.9rem;display:none;}
    #_sos_audio{width:100%;margin:10px 0;display:none;}
    #_sos_status{font-size:.78rem;color:#86efac;margin-top:8px;min-height:16px;}
    ._sos_row{display:flex;gap:10px;align-items:center;margin-bottom:14px;}
    ._sos_actions{display:flex;gap:10px;flex-wrap:wrap;}
    @keyframes sosPulse{0%,100%{box-shadow:0 0 0 0 rgba(220,38,38,.7);}50%{box-shadow:0 0 0 10px rgba(220,38,38,0);}}
  `

  const modal = document.createElement('div')
  modal.id = '_sos_rec_modal'
  modal.innerHTML = `
    <style>${css}</style>
    <div id="_sos_rec_box">
      <h2>🆘 Cảnh báo khẩn cấp đã gửi!</h2>
      <p>Email đã gửi cho người thân. Nhấn <strong>GHI ÂM</strong> để đính kèm tin nhắn thoại vào email.</p>
      <div class="_sos_row">
        <button class="_sos_btn" id="_sos_start" onclick="window._sosFn.start()">🎙 GHI ÂM</button>
        <button class="_sos_btn" id="_sos_stop"  onclick="window._sosFn.stop()">⏹ Dừng</button>
        <span id="_sos_timer">0s</span>
      </div>
      <audio id="_sos_audio" controls></audio>
      <div class="_sos_actions">
        <button class="_sos_btn" id="_sos_send"  onclick="window._sosFn.send()">📧 Gửi tin nhắn thoại</button>
        <button class="_sos_btn" id="_sos_close" onclick="window._sosFn.close()">✕ Đóng</button>
      </div>
      <p id="_sos_status"></p>
    </div>
  `
  document.body.appendChild(modal)

  // Reset state
  _sosRec = null; _sosChunks = []; _sosSecs = 0
  clearInterval(_sosTimer)

  window._sosFn = {
    start: async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        _sosRec = new MediaRecorder(stream)
        _sosChunks = []
        _sosRec.ondataavailable = e => { if (e.data.size > 0) _sosChunks.push(e.data) }
        _sosRec.onstop = () => {
          const blob = new Blob(_sosChunks, { type: 'audio/webm' })
          window._sosBlob = blob
          const url = URL.createObjectURL(blob)
          const aud = document.getElementById('_sos_audio')
          aud.src = url; aud.style.display = 'block'
          document.getElementById('_sos_send').style.display = 'flex'
          stream.getTracks().forEach(t => t.stop())
        }
        _sosRec.start()
        document.getElementById('_sos_start').style.display = 'none'
        document.getElementById('_sos_stop').style.display = 'inline-block'
        const timerEl = document.getElementById('_sos_timer')
        timerEl.style.display = 'inline'; _sosSecs = 0
        _sosTimer = setInterval(() => {
          _sosSecs++; timerEl.textContent = _sosSecs + 's'
          if (_sosSecs >= 60) window._sosFn.stop()
        }, 1000)
      } catch (e) {
        document.getElementById('_sos_status').textContent = '❌ Không có quyền mic: ' + e.message
      }
    },
    stop: () => {
      clearInterval(_sosTimer)
      if (_sosRec && _sosRec.state === 'recording') _sosRec.stop()
      document.getElementById('_sos_stop').style.display = 'none'
      document.getElementById('_sos_timer').style.display = 'none'
      document.getElementById('_sos_start').style.display = 'inline-block'
    },
    send: async () => {
      const blob = window._sosBlob
      if (!blob) { document.getElementById('_sos_status').textContent = 'Chưa có bản ghi âm.'; return }
      const st = document.getElementById('_sos_status')
      st.textContent = 'Đang gửi…'
      document.getElementById('_sos_send').disabled = true
      try {
        const token = localStorage.getItem('authToken') || sessionStorage.getItem('authToken') || ''
        const form = new FormData()
        form.append('audio', blob, 'sos-voice.webm')
        form.append('note', 'Tin nhắn thoại SOS từ Alfred chat')
        const res = await fetch('/api/alerts/sos', {
          method: 'POST',
          headers: token ? { Authorization: 'Bearer ' + token } : {},
          body: form,
        })
        st.textContent = res.ok ? '✅ Đã gửi tin nhắn thoại qua email!' : '❌ Lỗi gửi: ' + res.status
      } catch (e) {
        st.textContent = '❌ ' + e.message
      }
      document.getElementById('_sos_send').disabled = false
    },
    close: () => {
      clearInterval(_sosTimer)
      if (_sosRec && _sosRec.state === 'recording') _sosRec.stop()
      const m = document.getElementById('_sos_rec_modal'); if (m) m.remove()
    },
  }
}

/**
 * Initialize Socket.IO connection and integrate with Pinia stores
 * @param {string} token JWT authentication token
 * @returns {object} Socket instance
 */
export function initSocket(token) {
  if (socket?.connected) {
    console.warn('[Socket] Already connected')
    return socket
  }

  const deviceStore = useDeviceStore()
  const alertStore = useAlertStore()
  const uiStore = useUIStore()

  uiStore.setConnectionStatus('connecting')

  socket = io('/', {
    auth: { token },
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    reconnectionAttempts: 5,
  })

  // ============= DEVICE EVENTS =============

  /**
   * Device state changed (from MQTT/backend)
   * Payload: { device_code, state }
   */
  socket.on('device_state_changed', (data) => {
    const { device_code, state } = data
    deviceStore.updateDeviceState(device_code, state)
  })

  /**
   * Device added (by another user or admin)
   */
  socket.on('device_added', (data) => {
    deviceStore.addDevice(data)
    alertStore.addInfo(`Device added: ${data.name}`)
  })

  /**
   * Device deleted
   */
  socket.on('device_deleted', (data) => {
    const { device_code } = data
    deviceStore.devices.delete(device_code)
    alertStore.addInfo(`Device deleted: ${device_code}`)
  })

  /**
   * Device updated
   */
  socket.on('device_updated', (data) => {
    const { code } = data
    const device = deviceStore.getDevice(code)
    if (device) {
      Object.assign(device, data)
    }
  })

  // ============= ALERT/NOTIFICATION EVENTS =============

  /**
   * Alert received from backend
   * Payload: { type: 'success'|'error'|'warning'|'info', message }
   */
  socket.on('alert', (data) => {
    const { type, message } = data

    // Render in dashboard alert panel (supports actionable suggestion payloads).
    const normalizedLevel = String(data?.level || type || 'info').toLowerCase()
    alertController.onNewAlert({
      ...data,
      level: normalizedLevel,
      created_at: data?.created_at || new Date().toISOString(),
    })

    switch (type) {
      case 'success':
        alertStore.addSuccess(message)
        break
      case 'error':
        alertStore.addError(message)
        break
      case 'warning':
        alertStore.addWarning(message)
        break
      case 'info':
        alertStore.addInfo(message)
        break
      default:
        alertStore.addInfo(message)
    }
  })

  /**
   * SOS alert received (emergency) — inject & show recording modal
   */
  socket.on('sos_alert', (data) => {
    const { user_name, note } = data
    alertStore.addError(`🚨 SOS từ ${user_name}: ${note}`, 0)
    console.error('[Socket] SOS Alert:', data)
    if (window.openSosPopup) window.openSosPopup()
  })

  /**
   * Medicine reminder
   */
  socket.on('medicine_reminder', (data) => {
    const { medicine_name, time } = data
    alertStore.addWarning(`💊 Medicine reminder: ${medicine_name} at ${time}`, 0)
  })

  /**
   * Anomaly detected
   */
  socket.on('anomaly_detected', (data) => {
    const { type, message, severity } = data
    if (severity === 'high') {
      alertStore.addError(`⚠️ Anomaly: ${message}`)
    } else {
      alertStore.addWarning(`ℹ️ Anomaly: ${message}`)
    }
  })

  // ============= CONNECTION EVENTS =============

  socket.on('connect', () => {
    console.log('[Socket] Connected')
    uiStore.setConnectionStatus('connected')
  })

  socket.on('disconnect', () => {
    console.log('[Socket] Disconnected')
    uiStore.setConnectionStatus('disconnected')
  })

  socket.on('connect_error', (error) => {
    console.error('[Socket] Connection error:', error)
    uiStore.setConnectionStatus('disconnected')
    alertStore.addError('Connection lost')
  })

  socket.on('error', (error) => {
    console.error('[Socket] Error:', error)
    alertStore.addError(`Connection error: ${error}`)
  })

  // ============= SCHEDULE REMINDER =============

  /**
   * Fired when a remind_only schedule reaches its scheduled time.
   * Payload: { schedule_id, label, device_code, device_name, is_on, value }
   */
  socket.on('schedule_reminder', (data) => {
    // Delegate to the reminder module if initialised, else fall back to alert
    if (window.ScheduleReminder) {
      // The reminder module receives the raw data via initScheduleReminder(socket),
      // so we only need to handle the case where the module is not loaded.
      return
    }
    const { label, device_name, is_on } = data
    const action = is_on ? 'bật' : 'tắt'
    alertStore.addWarning(`⏰ Lịch hẹn: ${label || device_name} — Đến giờ ${action} thiết bị!`)
  })

  // ============= CUSTOM EVENTS =============

  /**
   * Broadcast from backend (general messages)
   */
  socket.on('broadcast', (data) => {
    const { title, message } = data
    console.log(`[Socket] Broadcast: ${title}`)
    alertStore.addInfo(`${title}: ${message}`)
  })

  return socket
}

/**
 * Disconnect socket
 */
export function disconnectSocket() {
  if (socket?.connected) {
    socket.disconnect()
    socket = null
    console.log('[Socket] Disconnected')
  }
}

/**
 * Get socket instance
 */
export function getSocket() {
  return socket
}

/**
 * Check if socket is connected
 */
export function isSocketConnected() {
  return socket?.connected || false
}

/**
 * Emit event through socket
 * @param {string} event Event name
 * @param {*} data Event data
 */
export function emit(event, data) {
  if (!socket?.connected) {
    console.warn('[Socket] Not connected, cannot emit:', event)
    return false
  }

  socket.emit(event, data)
  console.log(`[Socket] Emitted: ${event}`, data)
  return true
}

/**
 * Send device control command
 * @param {string} deviceCode Device code
 * @param {string} action Action: 'ON', 'OFF', 'TOGGLE'
 */
export function controlDeviceViaSocket(deviceCode, action) {
  return emit('control_device', {
    device_code: deviceCode,
    action,
  })
}

/**
 * Request device status update
 */
export function requestDeviceStatus(deviceCode) {
  return emit('request_device_status', {
    device_code: deviceCode,
  })
}

/**
 * Send chat message (Alfred AI)
 */
export function sendChatMessage(message, userId) {
  return emit('chat_message', {
    message,
    user_id: userId,
  })
}

/**
 * Subscribe to device updates
 */
export function subscribeToDevice(deviceCode) {
  return emit('subscribe_device', {
    device_code: deviceCode,
  })
}

/**
 * Unsubscribe from device updates
 */
export function unsubscribeFromDevice(deviceCode) {
  return emit('unsubscribe_device', {
    device_code: deviceCode,
  })
}

export { _openSosModal }