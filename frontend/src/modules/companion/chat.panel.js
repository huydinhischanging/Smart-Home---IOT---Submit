// src/modules/companion/chat.panel.js
// ==========================================
// 🗨️ Chat Panel for Alfred AI
// ==========================================

import { AIApi } from '../../services/api/ai.api.js'

// ─── SOS recording modal (inline, no external dependencies) ──────────────────
function openSosRecordModal () {
  const old = document.getElementById('_sos_rec_modal')
  if (old) old.remove()

  const modal = document.createElement('div')
  modal.id = '_sos_rec_modal'
  modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:99999;display:flex;align-items:center;justify-content:center;'

  modal.innerHTML = `
    <style>
      #_srbox{background:#12001a;border:2px solid #dc2626;border-radius:14px;padding:28px 30px;max-width:420px;width:92%;color:#f1f5f9;font-family:sans-serif;box-shadow:0 0 40px rgba(220,38,38,.5);}
      #_srbox h2{color:#ef4444;margin:0 0 8px;font-size:1.1rem;}
      #_srbox p{color:#94a3b8;font-size:.82rem;margin:0 0 18px;line-height:1.5;}
      #_srbox strong{color:#fbbf24;}
      .srbtn{border:none;border-radius:7px;padding:10px 20px;cursor:pointer;font-weight:700;font-size:.88rem;margin-right:8px;}
      #_srstart{background:#dc2626;color:#fff;animation:srPulse 1.1s ease-in-out infinite;}
      #_srstop{background:#7f1d1d;color:#fff;display:none;}
      #_srsend{background:#16a34a;color:#fff;display:none;margin-top:10px;width:100%;}
      #_srclose{background:#374151;color:#ccc;}
      #_srtimer{color:#fbbf24;font-weight:700;margin-left:8px;display:none;}
      #_sraud{width:100%;margin:10px 0;display:none;}
      #_srst{font-size:.78rem;color:#86efac;margin-top:8px;min-height:16px;}
      @keyframes srPulse{0%,100%{box-shadow:0 0 0 0 rgba(220,38,38,.7);}50%{box-shadow:0 0 0 10px rgba(220,38,38,0);}}
    </style>
    <div id="_srbox">
      <h2>🆘 Cảnh báo khẩn cấp đã gửi!</h2>
      <p>Email đã gửi cho người thân. Nhấn <strong>GHI ÂM</strong> bên dưới để đính kèm tin nhắn thoại.</p>
      <div>
        <button class="srbtn" id="_srstart">🎙 GHI ÂM</button>
        <button class="srbtn" id="_srstop">⏹ Dừng</button>
        <span id="_srtimer">0s</span>
      </div>
      <audio id="_sraud" controls></audio>
      <button class="srbtn" id="_srsend">📧 Gửi tin nhắn thoại qua email</button>
      <div style="margin-top:12px;">
        <button class="srbtn" id="_srclose">✕ Đóng</button>
      </div>
      <p id="_srst"></p>
    </div>
  `
  document.body.appendChild(modal)

  let rec = null, chunks = [], blob = null, timer = null, secs = 0

  document.getElementById('_srstart').onclick = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      rec = new MediaRecorder(stream)
      chunks = []
      rec.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data) }
      rec.onstop = () => {
        blob = new Blob(chunks, { type: 'audio/webm' })
        const url = URL.createObjectURL(blob)
        const aud = document.getElementById('_sraud')
        aud.src = url; aud.style.display = 'block'
        document.getElementById('_srsend').style.display = 'block'
        stream.getTracks().forEach(t => t.stop())
      }
      rec.start()
      document.getElementById('_srstart').style.display = 'none'
      document.getElementById('_srstop').style.display = 'inline-block'
      document.getElementById('_srtimer').style.display = 'inline'
      secs = 0
      timer = setInterval(() => {
        secs++
        document.getElementById('_srtimer').textContent = secs + 's'
        if (secs >= 60) document.getElementById('_srstop').click()
      }, 1000)
    } catch (e) {
      document.getElementById('_srst').textContent = '❌ Không có quyền mic: ' + e.message
    }
  }

  document.getElementById('_srstop').onclick = () => {
    clearInterval(timer)
    if (rec && rec.state === 'recording') rec.stop()
    document.getElementById('_srstop').style.display = 'none'
    document.getElementById('_srtimer').style.display = 'none'
    document.getElementById('_srstart').style.display = 'inline-block'
  }

  document.getElementById('_srsend').onclick = async () => {
    if (!blob) { document.getElementById('_srst').textContent = 'Chưa có bản ghi âm.'; return }
    const st = document.getElementById('_srst')
    st.textContent = 'Đang gửi…'
    document.getElementById('_srsend').disabled = true
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
      st.textContent = res.ok ? '✅ Đã gửi tin nhắn thoại qua email!' : '❌ Lỗi: ' + res.status
    } catch (e) {
      st.textContent = '❌ ' + e.message
    }
    document.getElementById('_srsend').disabled = false
  }

  document.getElementById('_srclose').onclick = () => {
    clearInterval(timer)
    if (rec && rec.state === 'recording') rec.stop()
    modal.remove()
  }

  modal.addEventListener('click', e => { if (e.target === modal) modal.remove() })
}

let chatContext = {
  rooms: [],
  floors: [],
  owner_room: null  // { id, name } when user selects a room
}

const state = {
  mode: 'rule',
  currentRoomId: null,
  currentRoomName: null
}

function _renderMessage(aligned, text) {
  return `<div class="chat-line ${aligned}"><div class="chat-bubble">${text}</div></div>`
}

function _scrollBottom(container) {
  container.scrollTop = container.scrollHeight
}

export function setChatContext(context = {}) {
  chatContext.rooms = context.rooms || []
  chatContext.floors = context.floors || []
  // Preserve owner_room if already set
  if (context.owner_room) {
    chatContext.owner_room = context.owner_room
  }
}

export function setCurrentRoom(roomId, roomName) {
  state.currentRoomId = roomId
  state.currentRoomName = roomName
  chatContext.owner_room = roomId && roomName ? { id: roomId, name: roomName } : null
  console.log('[Chat] Room selected:', chatContext.owner_room)
}

export function mountChatPanel(container, options = {}) {
  if (!container) {
    throw new Error('chat panel container is required')
  }

  state.mode = options.defaultMode || 'rule'

  container.innerHTML = `
    <div class="chat-panel">
      <div class="chat-header">Alfred Chat Assistant</div>
      <div id="current-room-display" class="current-room" style="padding: 8px; font-size: 12px; color: #999; text-align: center;">
        📍 Phòng: <span id="room-name-display">Chưa chọn</span>
      </div>
      <div class="chat-history" id="chat-history"></div>
      <div class="chat-controls">
        <select id="chat-mode" class="chat-mode-select">
          <option value="rule"   ${state.mode === 'rule'   ? 'selected' : ''}>Rule</option>
          <option value="llm"    ${state.mode === 'llm'    ? 'selected' : ''}>LLM</option>
          <option value="gemini" ${state.mode === 'gemini' ? 'selected' : ''}>Gemini</option>
        </select>
        <select id="room-selector" class="room-selector" style="flex: 0.5; padding: 8px;">
          <option value="">-- Chọn phòng --</option>
        </select>
        <input id="chat-message" placeholder="Nhập lệnh hoặc hỏi Alfred..." />
        <button id="chat-send">Gửi</button>
      </div>
    </div>
  `

  const historyEl = container.querySelector('#chat-history')
  const inputEl = container.querySelector('#chat-message')
  const sendBtn = container.querySelector('#chat-send')
  const modeEl = container.querySelector('#chat-mode')
  const roomSelectorEl = container.querySelector('#room-selector')
  const roomDisplayEl = container.querySelector('#room-name-display')

  const addChat = (speaker, text) => {
    const align = speaker === 'user' ? 'right' : 'left'
    historyEl.insertAdjacentHTML('beforeend', _renderMessage(align, text))
    _scrollBottom(historyEl)
  }

  localStorage.setItem('chat_mode', state.mode)

  modeEl.addEventListener('change', (event) => {
    state.mode = event.target.value
    localStorage.setItem('chat_mode', state.mode)
    addChat('system', `Chế độ chat đổi thành: ${state.mode}`)
  })

  // ✅ Populate room selector and set up room change listener
  const updateRoomSelector = () => {
    const rooms = chatContext.rooms || []
    roomSelectorEl.innerHTML = '<option value="">-- Chọn phòng --</option>'
    rooms.forEach(room => {
      const roomId = room.id || room.room_id
      const roomName = room.name || room.room_name
      if (roomId && roomName) {
        roomSelectorEl.innerHTML += `<option value="${roomId}">${roomName}</option>`
      }
    })
    // Pre-select current room if set
    if (state.currentRoomId) {
      roomSelectorEl.value = state.currentRoomId
    }
  }

  roomSelectorEl.addEventListener('change', (event) => {
    const roomId = event.target.value
    const selectedOption = event.target.selectedOptions[0]
    const roomName = selectedOption?.textContent || ''
    if (roomId) {
      setCurrentRoom(roomId, roomName)
      if (roomDisplayEl) {
        roomDisplayEl.textContent = roomName
      }
      addChat('system', `✓ Phòng đã chọn: ${roomName}`)
    } else {
      state.currentRoomId = null
      state.currentRoomName = null
      chatContext.owner_room = null
      if (roomDisplayEl) {
        roomDisplayEl.textContent = 'Chưa chọn'
      }
    }
  })

  // Initial room selector population
  updateRoomSelector()

  const sendMessage = async () => {
    const message = inputEl.value.trim()
    if (!message) return

    addChat('user', message)
    inputEl.value = ''

    // Detect SOS before sending — open popup as soon as reply comes back
    const _isSOS = /\b(sos|help me|cứu|cứu tôi|cứu với|emergency|khẩn cấp|cấp cứu)\b/i.test(message)

    try {
      const response = await AIApi.chat({
        message,
        mode: state.mode,
        context: chatContext
      })

      const reply = response.reply || response.message || 'Không có phản hồi.'
      addChat('assistant', reply)

      if (_isSOS || reply.includes('🆘')) {
        openSosRecordModal()
      }

      if (response.devices_changed) {
        addChat('assistant', '⚡️ [Thiết bị đã thay đổi]')
      }

    } catch (err) {
      console.error(err)
      addChat('assistant', 'Lỗi kết nối AI. Vui lòng thử lại.')
    }
  }

  sendBtn.addEventListener('click', sendMessage)

  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  })

  if (options.initialMessage) {
    addChat('assistant', options.initialMessage)
  }

  // Return a reference to updateRoomSelector so it can be called externally
  // when rooms list is updated
  return { updateRoomSelector }
}

// ✅ Stub functions for diagnostic/wellness (for compatibility with main.js)
export function renderDiagnostic(status) {
  return `<div class="diagnostic-panel">Diagnostic: ${status || 'ready'}</div>`
}

export function updateWellnessIndex(data) {
  return `<div class="wellness-panel">Wellness: OK</div>`
}

export function setUserName(name) {
  state.userName = name
  console.log('[Chat] User name set:', name)
}
