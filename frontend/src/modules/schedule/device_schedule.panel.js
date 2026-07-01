// src/modules/schedule/device_schedule.panel.js
// Device schedule management UI (create / toggle / delete schedules)

import { AutomationApi } from '../../services/api/automation.api.js'
import { DeviceApi }     from '../../services/api/device.api.js'

// ─────────────────────────────────────────────
// STATE
// ─────────────────────────────────────────────
let _schedules = []
let _devices   = []
let _editingId = null   // null = create mode

// ─────────────────────────────────────────────
// INIT
// ─────────────────────────────────────────────
export async function initSchedulePanel() {
  await _loadDevices()
  await _loadSchedules()
  _bindModalEvents()
}

// ─────────────────────────────────────────────
// LOAD DATA
// ─────────────────────────────────────────────
async function _loadDevices() {
  try {
    _devices = await DeviceApi.getDevices()
  } catch (err) {
    console.warn('[Schedule] Could not load devices:', err)
    _devices = []
  }
}

async function _loadSchedules() {
  try {
    _schedules = await AutomationApi.listSchedules()
  } catch (err) {
    console.warn('[Schedule] Could not load schedules:', err)
    _schedules = []
  }
  _renderList()
}

// ─────────────────────────────────────────────
// RENDER SCHEDULE LIST
// ─────────────────────────────────────────────
function _renderList() {
  const container = document.getElementById('sched-list')
  if (!container) return

  if (!_schedules.length) {
    container.innerHTML = `
      <div class="sched-empty">
        <div class="sched-empty-icon">⏰</div>
        <div>No schedules yet.<br>Click <strong>+ Add Schedule</strong> to get started.</div>
      </div>`
    return
  }

  container.innerHTML = _schedules.map(s => {
    const device = _devices.find(d => d.id === s.device_id)
    const deviceName = device?.name || `Device #${s.device_id}`
    const deviceIcon = device?.icon || '💡'
    const timeLabel  = AutomationApi.describeCron(s.cron_expr)
    const actionLabel = s.action?.is_on !== undefined
      ? (s.action.is_on ? 'ON' : 'OFF')
      : (s.action?.value || '?')
    return `
      <div class="sched-item ${s.is_active ? '' : 'sched-inactive'}" data-id="${s.id}">
        <div class="sched-icon">${deviceIcon}</div>
        <div class="sched-info">
          <div class="sched-label">${s.label || deviceName}</div>
          <div class="sched-meta">
            <span class="sched-device">${deviceName}</span>
            <span class="sched-sep">·</span>
            <span class="sched-time">${timeLabel}</span>
            <span class="sched-sep">·</span>
            <span class="sched-action">${actionLabel}</span>
          </div>
        </div>
        <div class="sched-controls">
          <label class="sched-toggle" title="${s.is_active ? 'Disable schedule' : 'Enable schedule'}">
            <input type="checkbox" ${s.is_active ? 'checked' : ''}
              onchange="SchedulePanel.toggle(${s.id}, this.checked)">
            <span class="sched-slider"></span>
          </label>
          <button class="sched-btn-edit" onclick="SchedulePanel.openEdit(${s.id})" title="Sửa">✏️</button>
          <button class="sched-btn-del"  onclick="SchedulePanel.delete(${s.id})" title="Xóa">🗑️</button>
        </div>
      </div>`
  }).join('')
}

// ─────────────────────────────────────────────
// MODAL HELPERS
// ─────────────────────────────────────────────
function _getModal()    { return document.getElementById('sched-modal') }
function _getForm()     { return document.getElementById('sched-form') }
function _getStatus()   { return document.getElementById('sched-form-status') }

function _populateDeviceSelect() {
  const sel = document.getElementById('sched-device')
  if (!sel) return
  sel.innerHTML = '<option value="">-- Chọn thiết bị --</option>' +
    _devices.map(d => `<option value="${d.id}">${d.icon || '💡'} ${d.name}</option>`).join('')
}

function _openModal(title) {
  _populateDeviceSelect()
  const modal = _getModal()
  if (!modal) return
  document.getElementById('sched-modal-title').textContent = title
  modal.classList.remove('sos-hidden')
  _setStatus('')
}

function _closeModal() {
  const modal = _getModal()
  if (modal) modal.classList.add('sos-hidden')
  _editingId = null
  _getForm()?.reset()
}

function _setStatus(msg, isError = false) {
  const el = _getStatus()
  if (!el) return
  el.textContent = msg
  el.style.color = isError ? '#f87171' : '#34d399'
}

function _bindModalEvents() {
  const modal = _getModal()
  if (!modal) return
  modal.addEventListener('click', e => {
    if (e.target === modal) _closeModal()
  })

  // Show/hide extra rows based on recurrence select
  document.getElementById('sched-recurrence')?.addEventListener('change', e => {
    const val       = e.target.value
    const customRow = document.getElementById('sched-custom-cron-row')
    const daysRow   = document.getElementById('sched-days-row')
    if (customRow) customRow.style.display = val === 'custom'   ? 'block' : 'none'
    if (daysRow)   daysRow.style.display   = val === 'specific' ? 'block' : 'none'
  })
}

// ─────────────────────────────────────────────
// PUBLIC API (called from HTML via window.SchedulePanel)
// ─────────────────────────────────────────────
export const SchedulePanel = {

  openAdd() {
    _editingId = null
    _openModal('ADD DEVICE SCHEDULE')
    _getForm()?.reset()
    document.getElementById('sched-custom-cron-row').style.display = 'none'
    document.getElementById('sched-days-row').style.display = 'none'
  },

  openEdit(id) {
    const s = _schedules.find(x => x.id === id)
    if (!s) return
    _editingId = id
    _openModal('EDIT SCHEDULE')

    // Populate form fields
    const f = {
      device:     document.getElementById('sched-device'),
      label:      document.getElementById('sched-label'),
      time:       document.getElementById('sched-time'),
      recurrence: document.getElementById('sched-recurrence'),
      customCron: document.getElementById('sched-custom-cron'),
      actionOn:   document.getElementById('sched-action-on'),
      actionOff:  document.getElementById('sched-action-off'),
      customRow:  document.getElementById('sched-custom-cron-row'),
    }

    if (f.device) f.device.value = s.device_id
    if (f.label)  f.label.value  = s.label || ''

    // Detect recurrence from cron
    const parts = (s.cron_expr || '').trim().split(/\s+/)
    let recVal = 'custom'
    let timeVal = '08:00'
    let specificDays = []
    if (parts.length === 5) {
      const mm = parts[0], hh = parts[1], dow = parts[4]
      timeVal = `${hh.padStart(2,'0')}:${mm.padStart(2,'0')}`
      if (dow === '*')                             recVal = 'daily'
      else if (dow === '1-5')                     recVal = 'weekday'
      else if (dow === '6,0' || dow === '0,6')   recVal = 'weekend'
      else if (/^[\d,]+$/.test(dow)) {
        recVal = 'specific'
        specificDays = dow.split(',')
      }
    }
    if (f.time)       f.time.value       = timeVal
    if (f.recurrence) f.recurrence.value = recVal
    if (f.customCron) f.customCron.value = s.cron_expr

    const customRow = document.getElementById('sched-custom-cron-row')
    const daysRow   = document.getElementById('sched-days-row')
    if (customRow) customRow.style.display = recVal === 'custom'   ? 'block' : 'none'
    if (daysRow)   daysRow.style.display   = recVal === 'specific' ? 'block' : 'none'

    // Restore specific-day checkboxes
    document.querySelectorAll('input[name="sched-dow"]').forEach(cb => {
      cb.checked = specificDays.includes(cb.value)
    })

    const isOn = s.action?.is_on !== undefined ? s.action.is_on : true
    if (isOn && f.actionOn)   f.actionOn.checked  = true
    if (!isOn && f.actionOff) f.actionOff.checked = true
  },

  closeAdd() { _closeModal() },

  async save() {
    const device_id   = parseInt(document.getElementById('sched-device')?.value)
    const label       = document.getElementById('sched-label')?.value.trim()
    const time        = document.getElementById('sched-time')?.value
    const recurrence  = document.getElementById('sched-recurrence')?.value
    const customCron  = document.getElementById('sched-custom-cron')?.value
    const actionOnEl  = document.getElementById('sched-action-on')

    if (!device_id) return _setStatus('Please select a device.', true)
    if (!time && recurrence !== 'custom') return _setStatus('Please select a time.', true)

    const is_on = actionOnEl?.checked !== false

    // Collect specific days if needed
    const specificDays = recurrence === 'specific'
      ? [...document.querySelectorAll('input[name="sched-dow"]:checked')].map(c => c.value)
      : []
    if (recurrence === 'specific' && !specificDays.length)
      return _setStatus('Please select at least one day.', true)

    const cron_expr = AutomationApi.buildCron(time, recurrence, customCron, specificDays)

    if (!cron_expr) return _setStatus('Invalid cron expression.', true)

    _setStatus('Saving...')
    try {
      if (_editingId) {
        await AutomationApi.updateSchedule(_editingId, {
          label: label || null,
          cron_expr,
          action: { is_on, value: is_on ? 'ON' : 'OFF' },
          remind_only: false,
        })
        _setStatus('Schedule updated.')
      } else {
        await AutomationApi.createSchedule({
          device_id,
          label: label || null,
          cron_expr,
          action: { is_on, value: is_on ? 'ON' : 'OFF' },
          remind_only: false,
        })
        _setStatus('Schedule created!')
      }
      await _loadSchedules()
      setTimeout(_closeModal, 1000)
    } catch (err) {
      _setStatus(err.message || 'Save failed.', true)
    }
  },

  async toggle(id, active) {
    try {
      await AutomationApi.updateSchedule(id, { is_active: active })
      const s = _schedules.find(x => x.id === id)
      if (s) s.is_active = active
      _renderList()
    } catch (err) {
      console.error('[Schedule] Toggle error:', err)
      await _loadSchedules()
    }
  },

  async delete(id) {
    if (!confirm('Are you sure you want to delete this schedule?')) return
    try {
      await AutomationApi.deleteSchedule(id)
      _schedules = _schedules.filter(s => s.id !== id)
      _renderList()
    } catch (err) {
      alert('Delete failed: ' + err.message)
    }
  },

  refresh: _loadSchedules,
}

// Expose to window for inline onclick handlers
window.SchedulePanel = SchedulePanel
