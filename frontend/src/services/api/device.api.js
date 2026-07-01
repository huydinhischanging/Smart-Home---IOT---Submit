// src/services/api/device.api.js

import { HttpClient } from './http.client.js'

export const DeviceApi = {
  normalizeDevice(device) {
    if (!device) return null
    return {
      ...device,
      code: device.code || device.device_code,
      device_code: device.code || device.device_code,
      type: device.type || device.device_type || device.management?.device_type,
      device_type: device.device_type || device.type || device.management?.device_type,
      control_types: Array.isArray(device.control_types) ? device.control_types : (device.type ? [device.type] : []),
      metadata: device.metadata || device.management?.metadata || {},
    }
  },

  /* =====================================================
   * GET DEVICES
   * ===================================================== */
  async getDevices() {

    const res = await HttpClient.get('/api/devices/status')

    if (!res || res.success !== true || !Array.isArray(res.data)) {
      throw new Error(res?.message || 'Failed to fetch devices')
    }

    return res.data.map(device => this.normalizeDevice(device))
  },


  /* =====================================================
   * CREATE DEVICE
   * ===================================================== */
  async createDevice(data) {

    console.log("CREATE DEVICE SEND:", data)

    const payload = {
      device_name: data.device_name || data.name,
      device_id: data.device_id || data.code,
      device_type: data.device_type || data.type || data.control_types?.[0] || 'switch',
      category: data.category,
      control_types: data.control_types,
      icon: data.icon,
      room_id: data.room_id ?? data.location,
      metadata: data.metadata,
      map_x: data.map_x,
      map_y: data.map_y,
    }

    const res = await HttpClient.post('/api/devices', payload)

    if (!res || res.success !== true) {
      throw new Error(res?.message || "Create failed")
    }

    return this.normalizeDevice({
      id: res.device_id,
      name: res.name,
      code: res.code,
      type: res.type,
      device_type: res.device_type,
      category: res.category,
      room_id: res.room_id,
      metadata: res.metadata,
      control_types: payload.control_types || [payload.device_type],
      icon: payload.icon,
    })
  },


  /* =====================================================
   * DELETE DEVICE
   * ===================================================== */
  async deleteDevice(nameOrCode) {

    if (!nameOrCode) {
      throw new Error('Device code missing')
    }

    console.log("DELETE DEVICE SEND:", nameOrCode)

    const res = await HttpClient.delete(`/api/devices/${encodeURIComponent(nameOrCode)}`)

    if (!res || res.success !== true) {
      throw new Error(res?.message || "Delete failed")
    }

    return true
  },


  /* =====================================================
   * DEVICE CONTROL
   * ===================================================== */
  async sendControl(deviceCode, payload, deviceType = null, category = null) {

    if (!deviceCode)
      throw new Error("Device code missing")

    if (payload === undefined || payload === null)
      throw new Error("Payload missing")

    let body = { device_code: deviceCode }

    // STRING (ON/OFF)
    if (typeof payload === "string") {
      body.action = payload.toUpperCase()
    }

    // BOOLEAN
    else if (typeof payload === "boolean") {
      body.state = payload
    }

    // NUMBER (slider)
    else if (typeof payload === "number") {
      body.state = payload
    }

    // OBJECT
    else if (typeof payload === "object") {
      body = { device_code: deviceCode, ...payload }
    }

    console.log("CONTROL SEND:", body)

    const useV2 = deviceType && category && String(category).toLowerCase() !== 'sensor'
    const endpoint = useV2
      ? `/api/devices/actuators/${encodeURIComponent(deviceType)}/${encodeURIComponent(deviceCode)}/control`
      : '/api/devices/control'

    const res = await HttpClient.post(endpoint, body)

    if (!res || res.success !== true) {
      throw new Error(res?.message || "Control failed")
    }

    return res
  },


  /* =====================================================
   * DEVICE STATUS
   * ===================================================== */
  async getDeviceStatus() {

    const res = await HttpClient.get('/api/device-status')

    if (!res) {
      throw new Error('Failed to fetch status')
    }

    return res
  }

}