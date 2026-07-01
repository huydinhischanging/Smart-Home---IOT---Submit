// src/modules/device/device.view.js
// Responsibility: Handle DOM rendering only (NO business logic)

import { AVAILABLE_ICONS } from './device.icons.js'

/* =====================================================
 * ICON PICKER VIEW
 * ===================================================== */
export function initIconPickerView() {
  const picker = document.getElementById('iconPicker')
  if (!picker) return

  picker.innerHTML = ''

  AVAILABLE_ICONS.forEach((icon, index) => {
    const option = document.createElement('span')
    option.className = 'icon-option' + (index === 0 ? ' selected' : '')
    option.textContent = icon
    option.dataset.icon = icon

    option.addEventListener('click', () => {
      picker.querySelector('.selected')?.classList.remove('selected')
      option.classList.add('selected')
    })

    picker.appendChild(option)
  })
}

/* =====================================================
 * DEVICE CARD VIEW
 * ===================================================== */
export function renderDeviceCardView(device) {
  const container = document.getElementById('folder-devices')
  if (!container || !device?.name || !device?.code) return

  // tránh render trùng
  if (container.querySelector(`[data-device-code="${device.code}"]`)) return

  const card = document.createElement('div')
  card.className = 'control-card device-card'
  card.dataset.deviceCode = device.code

  if (device.is_on === true) {
    card.classList.add('active')
  }

  card.innerHTML = `
    <div class="device-header">
      <div class="device-title">
        <span class="device-icon">${device.icon || '💡'}</span>
        <span class="device-name">${device.name}</span>
      </div>

      <button class="device-delete" title="Delete">❌</button>
    </div>

    <div class="device-controls">
      ${buildControlsHTML(device) || '<em>No controls</em>'}
    </div>
  `

  bindControlEvents(card, device)
  container.appendChild(card)

  requestAnimationFrame(() => {
    card.classList.add('highlight')
    setTimeout(() => card.classList.remove('highlight'), 1200)
  })
}

/* =====================================================
 * REMOVE DEVICE (UI ONLY)
 * ===================================================== */
export function removeDeviceCardView(deviceCode) {
  document
    .querySelector(`[data-device-code="${deviceCode}"]`)
    ?.remove()
}

/* =====================================================
 * UPDATE STATUS (UI ONLY)
 * ===================================================== */
export function updateDeviceStatusView(deviceCode, status) {
  const card = document.querySelector(`[data-device-code="${deviceCode}"]`)
  if (!card) return

  if (status?.is_on !== undefined) {
    card.classList.toggle('active', status.is_on)
  }
}

/* =====================================================
 * INTERNAL HELPERS
 * ===================================================== */
function parseControlTypes(controlTypes) {
  if (Array.isArray(controlTypes)) return controlTypes
  try {
    return JSON.parse(controlTypes || '[]')
  } catch {
    return []
  }
}

function buildControlsHTML(device) {
  const types = parseControlTypes(device.control_types)
  let html = ''

  types.forEach(type => {
    if (type === 'switch' || type === 'fan') {
      html += `
        <div class="control-group">
          <button data-action="ON">ON</button>
          <button data-action="OFF">OFF</button>
        </div>
      `
    }

    if (type === 'slider') {
      html += `
        <div class="control-group">
          <input type="range" min="0" max="180" value="90">
          <span>90°</span>
        </div>
      `
    }

    if (type === 'motor') {
      html += `
        <div class="control-group">
          <button data-action="CLOCKWISE">▶</button>
          <button data-action="STOP">⏹</button>
          <button data-action="COUNTER_CLOCKWISE">◀</button>
        </div>
      `
    }
  })

  return html
}

/* =====================================================
 * BIND CONTROL EVENTS (CHUẨN PAYLOAD BACKEND)
 * ===================================================== */
function bindControlEvents(card, device) {
  const deviceCode = device.code
  const deviceType = device.device_type || device.type
  const category = device.category
  // 🔘 BUTTON CONTROLS
  card.querySelectorAll('[data-action]').forEach(btn => {
    btn.addEventListener('click', () => {
      const action = btn.dataset.action

      // MOTOR
      if (action === 'CLOCKWISE') {
        window.sendControlCommand?.(deviceCode, {
          action: 'ROTATE',
          direction: 'CW'
        }, deviceType, category)
      } else if (action === 'COUNTER_CLOCKWISE') {
        window.sendControlCommand?.(deviceCode, {
          action: 'ROTATE',
          direction: 'CCW'
        }, deviceType, category)
      } else if (action === 'STOP') {
        window.sendControlCommand?.(deviceCode, {
          action: 'STOP'
        }, deviceType, category)
      } else {
        // ON / OFF
        window.sendControlCommand?.(deviceCode, action, deviceType, category)
      }
    })
  })

  // 🎚 SLIDER
  card.querySelectorAll('input[type="range"]').forEach(slider => {
    const label = slider.nextElementSibling

    slider.addEventListener('input', () => {
      label.innerText = slider.value + '°'
    })

    slider.addEventListener('change', () => {
      window.sendControlCommand?.(deviceCode, {
        action: 'SET_VALUE',
        value: Number(slider.value)
      }, deviceType, category)
    })
  })
}
