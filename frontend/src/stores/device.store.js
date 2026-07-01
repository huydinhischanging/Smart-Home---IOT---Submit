import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * Device Store (Pinia)
 * Manages device registry, status, and control actions
 */
export const useDeviceStore = defineStore('device', () => {
  // ============= STATE =============
  const devices = ref(new Map())  // Map<code, device>
  const isLoading = ref(false)
  const error = ref(null)
  const controllingDevices = ref(new Set())  // Devices being controlled

  // ============= COMPUTED =============
  const deviceList = computed(() => Array.from(devices.value.values()))
  const activeDevices = computed(() =>
    deviceList.value.filter(d => !d.is_deleted)
  )
  const devicesByRoom = computed(() => {
    const byRoom = {}
    activeDevices.value.forEach(device => {
      const roomId = device.room_id || 'no_room'
      if (!byRoom[roomId]) byRoom[roomId] = []
      byRoom[roomId].push(device)
    })
    return byRoom
  })

  // ============= ACTIONS =============

  /**
   * Fetch all devices from API
   */
  async function fetchDevices(authHeader) {
    isLoading.value = true
    error.value = null

    try {
      const response = await fetch('/api/devices', {
        headers: authHeader,
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const data = await response.json()
      const devicesPayload = Array.isArray(data?.data) ? data.data : []

      // Clear and rebuild map
      devices.value.clear()
      devicesPayload.forEach(device => {
        devices.value.set(device.code, {
          ...device,
          last_updated: new Date().toISOString(),
        })
      })

      console.log(`[Devices] Loaded ${devicesPayload.length} devices`)
    } catch (err) {
      error.value = err.message
      console.error('[Devices] Fetch failed:', err)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Get device by code
   */
  function getDevice(deviceCode) {
    return devices.value.get(deviceCode)
  }

  /**
   * Add device to store
   */
  function addDevice(device) {
    devices.value.set(device.code, {
      ...device,
      last_updated: new Date().toISOString(),
    })
    console.log(`[Devices] Added: ${device.code}`)
  }

  /**
   * Update device state from MQTT/Socket
   * Called when server sends device state update
   */
  function updateDeviceState(deviceCode, newState) {
    const device = devices.value.get(deviceCode)
    if (device) {
      device.state = newState
      device.last_updated = new Date().toISOString()
      console.log(`[Devices] State updated: ${deviceCode} -> ${newState}`)
    }
  }

  /**
   * Control device (ON/OFF/TOGGLE)
   */
  async function controlDevice(deviceCode, action, authHeader) {
    const device = devices.value.get(deviceCode)
    if (!device) {
      error.value = 'Device not found'
      return false
    }

    // Prevent multiple simultaneous commands
    if (controllingDevices.value.has(deviceCode)) {
      console.warn(`[Devices] Already controlling ${deviceCode}`)
      return false
    }

    controllingDevices.value.add(deviceCode)
    error.value = null

    try {
      const response = await fetch('/api/devices/control', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeader,
        },
        body: JSON.stringify({ device_code: deviceCode, action }),
      })

      const data = await response.json()

      if (!response.ok) {
        error.value = data.error || `Control failed: ${response.status}`
        return false
      }

      // Update local state optimistically
      if (action === 'ON') {
        device.state = 1
      } else if (action === 'OFF') {
        device.state = 0
      } else if (action === 'TOGGLE') {
        device.state = device.state ? 0 : 1
      }
      device.last_updated = new Date().toISOString()

      console.log(`[Devices] Controlled: ${deviceCode} -> ${action}`)
      return true
    } catch (err) {
      error.value = err.message
      console.error(`[Devices] Control failed for ${deviceCode}:`, err)
      return false
    } finally {
      controllingDevices.value.delete(deviceCode)
    }
  }

  /**
   * Delete device
   */
  async function deleteDevice(deviceCode, authHeader) {
    error.value = null

    try {
      const response = await fetch(`/api/devices/${deviceCode}`, {
        method: 'DELETE',
        headers: authHeader,
      })

      if (!response.ok) {
        error.value = `Delete failed: ${response.status}`
        return false
      }

      // Remove from store
      devices.value.delete(deviceCode)
      console.log(`[Devices] Deleted: ${deviceCode}`)
      return true
    } catch (err) {
      error.value = err.message
      console.error(`[Devices] Delete failed for ${deviceCode}:`, err)
      return false
    }
  }

  /**
   * Create new device
   */
  async function createDevice(deviceData, authHeader) {
    isLoading.value = true
    error.value = null

    try {
      const response = await fetch('/api/devices', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeader,
        },
        body: JSON.stringify(deviceData),
      })

      const data = await response.json()

      if (!response.ok) {
        error.value = data.error || 'Creation failed'
        return null
      }

      const normalized = {
        id: data.device_id,
        name: data.name,
        code: data.code,
        type: data.type,
        device_type: data.device_type,
        category: data.category,
        room_id: data.room_id,
        metadata: data.metadata,
        control_types: deviceData.control_types || [deviceData.device_type || deviceData.type || 'switch'],
      }

      addDevice(normalized)
      console.log(`[Devices] Created: ${normalized.code}`)
      return normalized
    } catch (err) {
      error.value = err.message
      console.error('[Devices] Creation failed:', err)
      return null
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Update device metadata — no backend PUT endpoint; kept for future use.
   * @deprecated Not yet implemented server-side.
   */
  async function updateDevice(_deviceCode, _updates, _authHeader) {
    console.warn('[Devices] updateDevice is not yet supported by the backend')
    return false
  }

  /**
   * Get device by room
   */
  function getDevicesByRoom(roomId) {
    return activeDevices.value.filter(d => d.room_id === roomId)
  }

  /**
   * Clear all devices
   */
  function clearDevices() {
    devices.value.clear()
    controllingDevices.value.clear()
    error.value = null
  }

  return {
    // State
    devices,
    isLoading,
    error,
    controllingDevices,

    // Computed
    deviceList,
    activeDevices,
    devicesByRoom,

    // Actions
    fetchDevices,
    getDevice,
    addDevice,
    updateDeviceState,
    controlDevice,
    deleteDevice,
    createDevice,
    updateDevice,
    getDevicesByRoom,
    clearDevices,
  }
})
