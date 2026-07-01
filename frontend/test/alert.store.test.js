import test from 'node:test'
import assert from 'node:assert/strict'

// Mock for alert store
function createMockAlertStore() {
  let nextId = 1
  const timers = new Map()

  const store = {
    alerts: [],

    addAlert(type, message, duration = 3000) {
      const id = nextId++
      const alert = {
        id,
        type,
        message,
        persistent: duration === 0,
        timestamp: new Date()
      }
      this.alerts.push(alert)

      if (duration > 0) {
        const timer = setTimeout(() => {
          this.removeAlert(id)
        }, duration)
        timers.set(id, timer)
      }

      return id
    },

    addSuccess(message, duration = 3000) {
      return this.addAlert('success', message, duration)
    },

    addError(message, duration = 5000) {
      return this.addAlert('error', message, duration)
    },

    addWarning(message, duration = 4000) {
      return this.addAlert('warning', message, duration)
    },

    addInfo(message, duration = 3000) {
      return this.addAlert('info', message, duration)
    },

    removeAlert(id) {
      const idx = this.alerts.findIndex(a => a.id === id)
      if (idx >= 0) {
        this.alerts.splice(idx, 1)
      }
      if (timers.has(id)) {
        clearTimeout(timers.get(id))
        timers.delete(id)
      }
    },

    clearAll() {
      this.alerts = []
      timers.forEach(t => clearTimeout(t))
      timers.clear()
    },

    clearByType(type) {
      const idsToRemove = this.alerts.filter(a => a.type === type).map(a => a.id)
      idsToRemove.forEach(id => this.removeAlert(id))
    },

    clearAutoDissmiss() {
      const idsToRemove = this.alerts.filter(a => !a.persistent).map(a => a.id)
      idsToRemove.forEach(id => this.removeAlert(id))
    },

    getAlertsByType(type) {
      return this.alerts.filter(a => a.type === type)
    },

    hasErrors() {
      return this.alerts.some(a => a.type === 'error')
    }
  }
  return store
}

test('Alert Store - Initial State', async (t) => {
  await t.test('should initialize with empty alerts', () => {
    const store = createMockAlertStore()
    assert.deepStrictEqual(store.alerts, [])
  })
})

test('Alert Store - addAlert', async (t) => {
  await t.test('should add alert with auto-dismiss', () => {
    const store = createMockAlertStore()
    const id = store.addAlert('info', 'Test message', 3000)

    assert.strictEqual(store.alerts.length, 1)
    assert.strictEqual(store.alerts[0].type, 'info')
    assert.strictEqual(store.alerts[0].message, 'Test message')
    assert.strictEqual(store.alerts[0].persistent, false)
    assert.strictEqual(typeof id, 'number')
  })

  await t.test('should add persistent alert when duration is 0', () => {
    const store = createMockAlertStore()
    store.addAlert('error', 'Persistent error', 0)

    assert.strictEqual(store.alerts[0].persistent, true)
  })

  await t.test('should return unique alert ID', () => {
    const store = createMockAlertStore()
    const id1 = store.addAlert('info', 'Message 1')
    const id2 = store.addAlert('info', 'Message 2')

    assert.notStrictEqual(id1, id2)
  })
})

test('Alert Store - addSuccess', async (t) => {
  await t.test('should add success alert with default duration', () => {
    const store = createMockAlertStore()
    store.addSuccess('Success message')

    assert.strictEqual(store.alerts[0].type, 'success')
    assert.strictEqual(store.alerts[0].message, 'Success message')
  })

  await t.test('should support custom duration', () => {
    const store = createMockAlertStore()
    store.addSuccess('Success', 5000)

    assert.strictEqual(store.alerts[0].persistent, false)
  })
})

test('Alert Store - addError', async (t) => {
  await t.test('should add error alert with default duration', () => {
    const store = createMockAlertStore()
    store.addError('Error message')

    assert.strictEqual(store.alerts[0].type, 'error')
    assert.strictEqual(store.alerts[0].message, 'Error message')
  })
})

test('Alert Store - addWarning', async (t) => {
  await t.test('should add warning alert', () => {
    const store = createMockAlertStore()
    store.addWarning('Warning message')

    assert.strictEqual(store.alerts[0].type, 'warning')
    assert.strictEqual(store.alerts[0].message, 'Warning message')
  })
})

test('Alert Store - addInfo', async (t) => {
  await t.test('should add info alert', () => {
    const store = createMockAlertStore()
    store.addInfo('Info message')

    assert.strictEqual(store.alerts[0].type, 'info')
    assert.strictEqual(store.alerts[0].message, 'Info message')
  })
})

test('Alert Store - removeAlert', async (t) => {
  await t.test('should remove alert by ID', () => {
    const store = createMockAlertStore()
    const id = store.addAlert('info', 'Message')

    assert.strictEqual(store.alerts.length, 1)

    store.removeAlert(id)

    assert.strictEqual(store.alerts.length, 0)
  })

  await t.test('should do nothing for non-existent ID', () => {
    const store = createMockAlertStore()
    store.addAlert('info', 'Message')

    store.removeAlert(9999)

    assert.strictEqual(store.alerts.length, 1)
  })
})

test('Alert Store - clearAll', async (t) => {
  await t.test('should clear all alerts', () => {
    const store = createMockAlertStore()
    store.addAlert('info', 'Message 1')
    store.addAlert('error', 'Message 2')
    store.addAlert('success', 'Message 3')

    assert.strictEqual(store.alerts.length, 3)

    store.clearAll()

    assert.strictEqual(store.alerts.length, 0)
  })
})

test('Alert Store - clearByType', async (t) => {
  await t.test('should clear alerts of specific type', () => {
    const store = createMockAlertStore()
    store.addAlert('info', 'Info 1')
    store.addAlert('error', 'Error 1')
    store.addAlert('info', 'Info 2')

    store.clearByType('info')

    assert.strictEqual(store.alerts.length, 1)
    assert.strictEqual(store.alerts[0].type, 'error')
  })
})

test('Alert Store - clearAutoDissmiss', async (t) => {
  await t.test('should keep only persistent alerts', () => {
    const store = createMockAlertStore()
    store.addAlert('info', 'Auto dismiss', 3000)
    store.addAlert('error', 'Persistent', 0)

    store.clearAutoDissmiss()

    assert.strictEqual(store.alerts.length, 1)
    assert.strictEqual(store.alerts[0].persistent, true)
  })
})

test('Alert Store - getAlertsByType', async (t) => {
  await t.test('should return alerts of specific type', () => {
    const store = createMockAlertStore()
    store.addAlert('error', 'Error 1')
    store.addAlert('info', 'Info 1')
    store.addAlert('error', 'Error 2')

    const errors = store.getAlertsByType('error')

    assert.strictEqual(errors.length, 2)
    assert.ok(errors.every(a => a.type === 'error'))
  })

  await t.test('should return empty array for non-existent type', () => {
    const store = createMockAlertStore()
    store.addAlert('info', 'Message')

    const alerts = store.getAlertsByType('success')

    assert.deepStrictEqual(alerts, [])
  })
})

test('Alert Store - hasErrors', async (t) => {
  await t.test('should return true when errors exist', () => {
    const store = createMockAlertStore()
    store.addAlert('info', 'Info')
    store.addAlert('error', 'Error')

    assert.strictEqual(store.hasErrors(), true)
  })

  await t.test('should return false when no errors', () => {
    const store = createMockAlertStore()
    store.addAlert('info', 'Info')
    store.addAlert('success', 'Success')

    assert.strictEqual(store.hasErrors(), false)
  })

  await t.test('should return false when empty', () => {
    const store = createMockAlertStore()

    assert.strictEqual(store.hasErrors(), false)
  })
})

test('Alert Store - Multiple Alerts', async (t) => {
  await t.test('should handle multiple simultaneous alerts', () => {
    const store = createMockAlertStore()

    store.addSuccess('Success 1')
    store.addError('Error 1')
    store.addWarning('Warning 1')
    store.addInfo('Info 1')

    assert.strictEqual(store.alerts.length, 4)
    const types = store.alerts.map(a => a.type).sort()
    assert.deepStrictEqual(types, ['error', 'info', 'success', 'warning'])
  })
})

test('Alert Store - Timestamp Management', async (t) => {
  await t.test('should set timestamp on alert creation', () => {
    const store = createMockAlertStore()
    const beforeTime = new Date()

    store.addAlert('info', 'Message')

    const afterTime = new Date()
    const alertTime = store.alerts[0].timestamp

    assert.ok(alertTime.getTime() >= beforeTime.getTime())
    assert.ok(alertTime.getTime() <= afterTime.getTime())
  })
})
