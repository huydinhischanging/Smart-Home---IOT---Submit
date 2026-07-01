// src/dashboard/index.js
import { renderDashboard } from './dashboard.view.js'
import { initDashboardController } from './dashboard.controller.js'
import { renderHealthReport } from './health_report.js'

import { ApiClient } from '../services/api_client.js'
import { DeviceManager } from '../modules/device/device.controller.js'
import { printHealthReport } from './print_report.js';

export async function initDashboard() {
  const app = document.getElementById('app')
  if (!app) {
    console.error('[Dashboard] #app not found')
    return
  }

  // 1️⃣ Render layout (tạo devicesContainer)
  renderDashboard(app)

  // 2️⃣ Init controller (event, socket, modal…)
  initDashboardController()

  // 3️⃣ Load Health Report (min/max/avg BPM)
  renderHealthReport()

  // 4️⃣ LOAD DEVICES TỪ BACKEND
  try {
    const devices = await ApiClient.getDevices()
    console.log('[Dashboard] devices:', devices)

    if (Array.isArray(devices) && devices.length > 0) {
      devices.forEach(device => {
        DeviceManager.renderDeviceCard(device)
      })
    } else {
      console.warn('[Dashboard] No devices found')
    }
  } catch (err) {
    console.error('[Dashboard] Failed to load devices', err)
  }
}
