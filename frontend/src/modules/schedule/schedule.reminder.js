// src/modules/schedule/schedule.reminder.js
// Popup reminder shown when a remind_only schedule fires on the backend.
// Listens for "schedule_reminder" socket event and shows a dismissible modal.

import { DeviceApi } from '../../services/api/device.api.js'

const COUNTDOWN_SECS = 60

let _countdownTimer = null
let _queue = []   // support multiple reminders stacking
let _showing = false

// ─────────────────────────────────────────────
// PUBLIC: register socket listener
// ─────────────────────────────────────────────
export function initScheduleReminder(socket) {
  if (!socket) return
  socket.on('schedule_reminder', (data) => {
    _enqueue(data)
  })
}

// ─────────────────────────────────────────────
// QUEUE MANAGEMENT
// ─────────────────────────────────────────────
function _enqueue(data) {
  _queue.push(data)
  if (!_showing) _showNext()
}

function _showNext() {
  if (!_queue.length) { _showing = false; return }
  _showing = true
  _show(_queue.shift())
}

// ─────────────────────────────────────────────
// SHOW POPUP
// ─────────────────────────────────────────────
function _show(data) {
  const { label, device_name, device_code, is_on, value } = data

  const actionText = is_on ? 'TURN ON' : 'TURN OFF'
  const actionIcon = is_on ? '💡' : '🌙'

  const popup = document.getElementById('sched-reminder-popup')
  if (!popup) return

  document.getElementById('sched-rem-icon').textContent  = actionIcon
  document.getElementById('sched-rem-label').textContent = label
  document.getElementById('sched-rem-device').textContent = device_name
  document.getElementById('sched-rem-action').textContent = actionText

  // Store for confirm handler
  popup.dataset.deviceCode = device_code
  popup.dataset.value      = value
  popup.dataset.isOn       = is_on ? '1' : '0'

  popup.style.display = 'flex'
  popup.classList.remove('sched-rem-hiding')

  _startCountdown(popup)
}

// ─────────────────────────────────────────────
// COUNTDOWN BAR
// ─────────────────────────────────────────────
function _startCountdown(popup) {
  clearInterval(_countdownTimer)
  const bar = document.getElementById('sched-rem-bar')
  const countEl = document.getElementById('sched-rem-countdown')
  let remaining = COUNTDOWN_SECS

  if (bar) {
    bar.style.transition = 'none'
    bar.style.width = '100%'
    // Trigger reflow to restart animation
    void bar.offsetWidth
    bar.style.transition = `width ${COUNTDOWN_SECS}s linear`
    bar.style.width = '0%'
  }

  _countdownTimer = setInterval(() => {
    remaining--
    if (countEl) countEl.textContent = remaining + 's'
    if (remaining <= 0) {
      clearInterval(_countdownTimer)
      _dismiss()
    }
  }, 1000)

  if (countEl) countEl.textContent = COUNTDOWN_SECS + 's'
}

// ─────────────────────────────────────────────
// ACTIONS
// ─────────────────────────────────────────────
function _dismiss() {
  clearInterval(_countdownTimer)
  const popup = document.getElementById('sched-reminder-popup')
  if (!popup) return
  popup.classList.add('sched-rem-hiding')
  setTimeout(() => {
    popup.style.display = 'none'
    popup.classList.remove('sched-rem-hiding')
    _showing = false
    _showNext()
  }, 350)
}

async function _confirm() {
  const popup = document.getElementById('sched-reminder-popup')
  if (!popup) return
  const deviceCode = popup.dataset.deviceCode
  const isOn = popup.dataset.isOn === '1'
  _dismiss()

  try {
    await DeviceApi.sendControl(deviceCode, isOn ? 'ON' : 'OFF')
    _toast(`✅ ${isOn ? 'Turned on' : 'Turned off'} ${deviceCode}`)
  } catch (err) {
    _toast(`❌ Error: ${err.message}`, true)
  }
}

async function _confirmOpposite() {
  const popup = document.getElementById('sched-reminder-popup')
  if (!popup) return
  const deviceCode = popup.dataset.deviceCode
  const isOn = popup.dataset.isOn === '1'
  _dismiss()

  const opposite = isOn ? 'OFF' : 'ON'
  try {
    await DeviceApi.sendControl(deviceCode, opposite)
    _toast(`✅ ${!isOn ? 'Turned on' : 'Turned off'} ${deviceCode}`)
  } catch (err) {
    _toast(`❌ Error: ${err.message}`, true)
  }
}

function _toast(msg, isError = false) {
  const el = document.createElement('div')
  el.className = 'sched-toast' + (isError ? ' sched-toast-err' : '')
  el.textContent = msg
  document.body.appendChild(el)
  setTimeout(() => el.remove(), 3500)
}

// ─────────────────────────────────────────────
// EXPOSE to inline HTML onclick
// ─────────────────────────────────────────────
window.ScheduleReminder = {
  confirm:         _confirm,
  confirmOpposite: _confirmOpposite,
  dismiss:         _dismiss,
}
