// src/modules/device/device.controller.js
// Responsibility: Public API (Facade) for Device UI

import {
  initIconPickerView,
  renderDeviceCardView,
  updateDeviceStatusView,
  removeDeviceCardView
} from './device.view.js'

import { DeviceApi } from '../../services/api/device.api.js'

export const DeviceManager = {

  /* ========= ICON PICKER ========= */
  initIconPicker() {
    initIconPickerView()
  },

  /* ========= RENDER ========= */
  renderDeviceCard(device) {

    // 1️⃣ Render DOM
    renderDeviceCardView(device)

    // 2️⃣ Attach delete event
    const card = document.querySelector(
      `[data-device-code="${device.code}"]`
    )

    if (!card) return

    const deleteBtn = card.querySelector('.device-delete')
    if (!deleteBtn) return

    deleteBtn.addEventListener('click', async (e) => {
      e.stopPropagation()

      if (!confirm(`Delete device "${device.name}"?`)) return

      try {

        // ⚠️ Chỉ cần await là đủ
        await DeviceApi.deleteDevice(device.code)

        // Nếu không throw lỗi => coi như thành công
        removeDeviceCardView(device.code)

        console.log('[DeviceManager] Deleted:', device.code)

      } catch (err) {

        console.error('Delete error:', err)
        alert('Delete failed')

      }
    })
  },

  /* ========= STATUS ========= */
  updateStatusUI(deviceCode, status) {
    updateDeviceStatusView(deviceCode, status)
  }
}