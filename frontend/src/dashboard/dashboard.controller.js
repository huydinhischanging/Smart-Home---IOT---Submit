// src/dashboard/dashboard.controller.js

// 🔌 API
import { ApiClient } from '../services/api/index.js'

// 🔗 SOCKET (DÙNG CHUNG – KHÔNG TẠO IO() Ở ĐÂY)
import { getSocket } from '../services/socket.client.js'

// 🧩 Device module
import { DeviceManager } from '../modules/device/device.controller.js'

// 🌐 3D
import { open3DEnvironment } from '../modules/scene3d/index.js'

export function initDashboardController() {

  console.log('[Dashboard] Initializing controller...')

  /* =====================================================
   * DOM HELPERS
   * ===================================================== */
  const $ = id => document.getElementById(id)

  const devicesContainer = $('devicesContainer')
  const toggleBtn = $('toggleDevicesBtn')

  /* =====================================================
   * MODAL HANDLERS
import { printHealthReport } from './print_report.js';
   * ===================================================== */
  window.openAddDeviceModal = () => {

    const modal = $('addDeviceModal')
    if (!modal) return

    modal.style.display = 'block'
    DeviceManager.initIconPicker()
  }

  window.closeAddDeviceModal = () => {

    const modal = $('addDeviceModal')
    if (!modal) return

    modal.style.display = 'none'
  }

  /* =====================================================
   * CREATE DEVICE
   * ===================================================== */
  window.createNewDevice = async () => {

    const nameInput = $('deviceName')
    if (!nameInput) return

    const name = nameInput.value.trim()

    if (!name) {
      alert('Enter device name')
      return
    }

    const controlTypes = [
      ...document.querySelectorAll(
        '#controlTypesContainer input:checked'
      )
    ].map(i => i.value)

    const icon =
      document.querySelector('.icon-option.selected')
        ?.dataset.icon || '💡'

    try {

      const device = await ApiClient.createDevice({
        name,
        icon,
        control_types: controlTypes
      })

      if (!device) {
        alert('Failed to create device')
        return
      }

      DeviceManager.renderDeviceCard(device)

      devicesContainer?.classList.add('show')

      if (toggleBtn)
        toggleBtn.innerText = '📁 Close Devices'

      closeAddDeviceModal()

    }
    catch (err) {

      console.error('[CreateDevice] Error:', err)
      alert(err?.message || 'Server error while creating device')

    }
  }

  /* =====================================================
   * DELETE DEVICE
   * ===================================================== */
  window.deleteDevice = async (code) => {

    if (!code) return

    try {

      await ApiClient.deleteDevice(code)
      DeviceManager.removeDeviceCard(code)

    }
    catch (err) {

      console.error('[DeleteDevice] Error:', err)
      alert('Failed to delete device')

    }
  }

  /* =====================================================
   * DEVICE CONTROL (WAIT SOCKET CONFIRM)
   * ===================================================== */
  window.sendControlCommand = (deviceCode, payload, deviceType = null, category = null) => {

    if (!deviceCode || !payload) return

    ApiClient.sendControl(deviceCode, payload, deviceType, category)

    // ❌ DO NOT update UI here
    // ✅ Wait for socket confirmation
  }

  /* =====================================================
   * UI EVENTS
   * ===================================================== */
  $('openEnvBtn')?.addEventListener(
    'click',
    open3DEnvironment
  )

  $('addDeviceBtn')?.addEventListener(
    'click',
    openAddDeviceModal
  )

  $('createDeviceBtn')?.addEventListener(
    'click',
    createNewDevice
  )

  $('cancelAddDeviceBtn')?.addEventListener(
    'click',
    closeAddDeviceModal
  )

  /* =====================================================
   * TOGGLE DEVICES PANEL
   * ===================================================== */
  toggleBtn?.addEventListener('click', () => {

    if (!devicesContainer) return

    devicesContainer.classList.toggle('show')

    toggleBtn.innerText =
      devicesContainer.classList.contains('show')
        ? '📁 Close Devices'
        : '📂 Open Devices'
  })

  // Print Report button
  const printBtn = document.getElementById('printReportBtn');
  if (printBtn) {
    printBtn.addEventListener('click', printHealthReport);
  }
  /* =====================================================
   * SOCKET EVENTS
   * ===================================================== */
  const _socket = getSocket()
  if (_socket) {
    _socket.on('device_status', data => {
      const deviceCode = data?.device_code || data?.code
      if (!deviceCode) return
      DeviceManager.updateStatusUI(deviceCode, {
        is_on: data.is_on ?? data.payload === 'ON',
        value: data.value ?? data.payload
      })
    })
  }

  /* =====================================================
   * LOAD DEVICES ON START
   * ===================================================== */
  async function loadDevicesOnStart() {

    try {

      console.log('[Dashboard] Loading devices...')

      const devices = await ApiClient.getDevices()

      console.log('[Dashboard] Devices received:', devices)

      if (!Array.isArray(devices) || devices.length === 0) {

        console.log('[Dashboard] No devices found')
        return
      }

      devices.forEach(device => {

        DeviceManager.renderDeviceCard(device)

      })

      devicesContainer?.classList.add('show')

      if (toggleBtn)
        toggleBtn.innerText = '📁 Close Devices'

    }
    catch (err) {

      console.error('[Dashboard] Load devices error:', err)

    }
  }

  // 🚀 CALL LOAD ON START
  loadDevicesOnStart()

  console.log('[Dashboard] Controller ready ✅')
}