import test from 'node:test'
import assert from 'node:assert/strict'

// Mock for Pinia device store
function createMockDeviceStore() {
  const store = {
    devices: new Map(),
    isLoading: false,
    error: null,
    controllingDevices: new Set(),

    get deviceList() {
      return Array.from(this.devices.values())
    },

    get activeDevices() {
      return Array.from(this.devices.values()).filter(d => !d.is_deleted)
    },

    get devicesByRoom() {
      const grouped = {}
      for (const device of this.devices.values()) {
        if (!device.is_deleted) {
          const roomId = device.room_id || 'no_room'
          if (!grouped[roomId]) grouped[roomId] = []
          grouped[roomId].push(device)
        }
      }
      return grouped
    },

    addDevice(device) {
      device.last_updated = new Date().toISOString()
      this.devices.set(device.code, device)
    },

    getDevice(code) {
      return this.devices.get(code)
    },

    updateDeviceState(code, newState) {
      const device = this.devices.get(code)
      if (device) {
        device.state = newState
        device.last_updated = new Date().toISOString()
      }
    },

    async controlDevice(code, action, headers) {
      if (this.controllingDevices.has(code)) return false
      const device = this.getDevice(code)
      if (!device) {
        this.error = 'Device not found'
        return false
      }

      this.controllingDevices.add(code)
      try {
        const res = await global.fetch(`/api/devices/${code}/control`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...headers },
          body: JSON.stringify({ action })
        })
        if (!res.ok) {
          const data = await res.json()
          this.error = data.error || 'Control failed'
          return false
        }
        const newState = action === 'ON' ? 1 : 0
        this.updateDeviceState(code, newState)
        return true
      } finally {
        this.controllingDevices.delete(code)
      }
    },

    async fetchDevices(headers) {
      this.isLoading = true
      this.devices.clear()
      try {
        const res = await global.fetch('/api/devices', { headers })
        if (!res.ok) {
          this.error = `HTTP ${res.status}`
          return
        }
        const devices = await res.json()
        devices.forEach(d => this.addDevice(d))
        this.error = null
      } finally {
        this.isLoading = false
      }
    },

    async createDevice(data, headers) {
      this.isLoading = true
      try {
        const res = await global.fetch('/api/devices', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...headers },
          body: JSON.stringify(data)
        })
        if (!res.ok) {
          const errorData = await res.json()
          this.error = errorData.error || 'Creation failed'
          return null
        }
        const device = await res.json()
        this.addDevice(device)
        return device
      } finally {
        this.isLoading = false
      }
    },

    async deleteDevice(code, headers) {
      try {
        const res = await global.fetch(`/api/devices/${code}`, {
          method: 'DELETE',
          headers
        })
        if (!res.ok) {
          this.error = `Delete failed: HTTP ${res.status}`
          return false
        }
        this.devices.delete(code)
        return true
      } catch (err) {
        this.error = err.message
        return false
      }
    },

    async updateDevice(code, updates, headers) {
      try {
        const res = await global.fetch(`/api/devices/${code}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json', ...headers },
          body: JSON.stringify(updates)
        })
        if (!res.ok) {
          const data = await res.json()
          this.error = data.error || 'Update failed'
          return false
        }
        const updated = await res.json()
        this.devices.set(code, updated)
        return true
      } catch (err) {
        this.error = err.message
        return false
      }
    },

    getDevicesByRoom(roomId) {
      return Array.from(this.devices.values()).filter(
        d => d.room_id === roomId && !d.is_deleted
      )
    },

    clearDevices() {
      this.devices.clear()
      this.controllingDevices.clear()
      this.error = null
    }
  }
  return store
}

test('Device Store - Initial State', async (t) => {
  await t.test('should initialize with empty devices', () => {
    const store = createMockDeviceStore()
    assert.strictEqual(store.devices.size, 0)
    assert.strictEqual(store.isLoading, false)
    assert.strictEqual(store.error, null)
    assert.strictEqual(store.controllingDevices.size, 0)
  })
})

test('Device Store - Computed Properties', async (t) => {
  await t.test('should compute deviceList as empty array initially', () => {
    const store = createMockDeviceStore()
    assert.deepStrictEqual(store.deviceList, [])
  })

  await t.test('should compute activeDevices filtering deleted devices', () => {
    const store = createMockDeviceStore()
    store.devices.set('light', { code: 'light', name: 'Light', is_deleted: false })
    store.devices.set('fan', { code: 'fan', name: 'Fan', is_deleted: true })

    const activeDevices = store.activeDevices
    assert.strictEqual(activeDevices.length, 1)
    assert.strictEqual(activeDevices[0].code, 'light')
  })

  await t.test('should compute devicesByRoom grouping devices', () => {
    const store = createMockDeviceStore()
    store.devices.set('light1', { code: 'light1', room_id: 1, is_deleted: false })
    store.devices.set('light2', { code: 'light2', room_id: 1, is_deleted: false })
    store.devices.set('fan', { code: 'fan', room_id: 2, is_deleted: false })

    const byRoom = store.devicesByRoom
    assert.strictEqual(byRoom[1].length, 2)
    assert.strictEqual(byRoom[2].length, 1)
    assert.strictEqual(byRoom['no_room'], undefined)
  })
})

test('Device Store - addDevice', async (t) => {
  await t.test('should add device to store', () => {
    const store = createMockDeviceStore()
    const device = { code: 'light', name: 'Light', state: 0 }

    store.addDevice(device)

    assert.strictEqual(store.devices.size, 1)
    assert.strictEqual(store.getDevice('light').name, 'Light')
  })

  await t.test('should set last_updated timestamp', () => {
    const store = createMockDeviceStore()
    store.addDevice({ code: 'light', name: 'Light' })

    const device = store.getDevice('light')
    assert.ok(device.last_updated)
  })
})

test('Device Store - getDevice', async (t) => {
  await t.test('should return device by code', () => {
    const store = createMockDeviceStore()
    store.devices.set('light', { code: 'light', name: 'Light' })

    const device = store.getDevice('light')
    assert.strictEqual(device.code, 'light')
  })

  await t.test('should return undefined for non-existent device', () => {
    const store = createMockDeviceStore()
    const device = store.getDevice('nonexistent')
    assert.strictEqual(device, undefined)
  })
})

test('Device Store - updateDeviceState', async (t) => {
  await t.test('should update device state and timestamp', () => {
    const store = createMockDeviceStore()
    store.devices.set('light', { code: 'light', state: 0, last_updated: null })

    store.updateDeviceState('light', 1)

    const device = store.getDevice('light')
    assert.strictEqual(device.state, 1)
    assert.ok(device.last_updated)
  })
})

test('Device Store - controlDevice', async (t) => {
  await t.test('should control device successfully', async () => {
    const store = createMockDeviceStore()
    store.devices.set('light', { code: 'light', state: 0, name: 'Light' })

    global.fetch = async () => ({
      ok: true,
      json: async () => ({ success: true })
    })

    const result = await store.controlDevice('light', 'ON', {})

    assert.strictEqual(result, true)
    assert.strictEqual(store.getDevice('light').state, 1)
    assert.strictEqual(store.controllingDevices.has('light'), false)
  })

  await t.test('should prevent simultaneous control of same device', async () => {
    const store = createMockDeviceStore()
    store.devices.set('light', { code: 'light', state: 0 })
    store.controllingDevices.add('light')

    const result = await store.controlDevice('light', 'ON', {})

    assert.strictEqual(result, false)
  })

  await t.test('should handle control failure', async () => {
    const store = createMockDeviceStore()
    store.devices.set('light', { code: 'light', state: 0 })

    global.fetch = async () => ({
      ok: false,
      json: async () => ({ error: 'Device offline' })
    })

    const result = await store.controlDevice('light', 'ON', {})

    assert.strictEqual(result, false)
    assert.strictEqual(store.error, 'Device offline')
  })

  await t.test('should return false for non-existent device', async () => {
    const store = createMockDeviceStore()
    const result = await store.controlDevice('nonexistent', 'ON', {})

    assert.strictEqual(result, false)
    assert.strictEqual(store.error, 'Device not found')
  })
})

test('Device Store - fetchDevices', async (t) => {
  await t.test('should fetch and populate devices', async () => {
    const store = createMockDeviceStore()
    const mockDevices = [
      { code: 'light', name: 'Light', state: 0 },
      { code: 'fan', name: 'Fan', state: 1 }
    ]

    global.fetch = async () => ({
      ok: true,
      json: async () => mockDevices
    })

    await store.fetchDevices({})

    assert.strictEqual(store.devices.size, 2)
    assert.strictEqual(store.isLoading, false)
    assert.strictEqual(store.error, null)
  })

  await t.test('should handle fetch error', async () => {
    const store = createMockDeviceStore()

    global.fetch = async () => ({
      ok: false,
      status: 500
    })

    await store.fetchDevices({})

    assert.ok(store.error)
    assert.strictEqual(store.isLoading, false)
  })
})

test('Device Store - deleteDevice', async (t) => {
  await t.test('should delete device from store', async () => {
    const store = createMockDeviceStore()
    store.devices.set('light', { code: 'light', name: 'Light' })

    global.fetch = async () => ({ ok: true })

    const result = await store.deleteDevice('light', {})

    assert.strictEqual(result, true)
    assert.strictEqual(store.getDevice('light'), undefined)
  })
})

test('Device Store - getDevicesByRoom', async (t) => {
  await t.test('should return devices in specific room', () => {
    const store = createMockDeviceStore()
    store.devices.set('light1', { code: 'light1', room_id: 1, is_deleted: false })
    store.devices.set('light2', { code: 'light2', room_id: 1, is_deleted: false })
    store.devices.set('fan', { code: 'fan', room_id: 2, is_deleted: false })

    const roomDevices = store.getDevicesByRoom(1)

    assert.strictEqual(roomDevices.length, 2)
    assert.ok(roomDevices.every(d => d.room_id === 1))
  })

  await t.test('should exclude deleted devices', () => {
    const store = createMockDeviceStore()
    store.devices.set('light', { code: 'light', room_id: 1, is_deleted: false })
    store.devices.set('deleted', { code: 'deleted', room_id: 1, is_deleted: true })

    const roomDevices = store.getDevicesByRoom(1)

    assert.strictEqual(roomDevices.length, 1)
    assert.strictEqual(roomDevices[0].code, 'light')
  })
})

test('Device Store - clearDevices', async (t) => {
  await t.test('should clear all devices and state', () => {
    const store = createMockDeviceStore()
    store.devices.set('light', { code: 'light' })
    store.controllingDevices.add('light')
    store.error = 'Some error'

    store.clearDevices()

    assert.strictEqual(store.devices.size, 0)
    assert.strictEqual(store.controllingDevices.size, 0)
    assert.strictEqual(store.error, null)
  })
})
