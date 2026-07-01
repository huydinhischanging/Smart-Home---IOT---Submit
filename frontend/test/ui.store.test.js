import test from 'node:test'
import assert from 'node:assert/strict'

// Mock for UI store
function createMockUIStore() {
  const store = {
    theme: localStorage.getItem('ui_theme') || 'dark',
    sidebarOpen: true,
    openModals: new Map(),
    notifications: [],
    loading: false,
    connectionStatus: 'disconnected',

    toggleTheme() {
      this.setTheme(this.theme === 'dark' ? 'light' : 'dark')
    },

    setTheme(newTheme) {
      if (!['light', 'dark'].includes(newTheme)) return
      this.theme = newTheme
      localStorage.setItem('ui_theme', newTheme)
      document.documentElement.setAttribute('data-theme', newTheme)
    },

    toggleSidebar() {
      this.sidebarOpen = !this.sidebarOpen
    },

    openModal(modalName, data = null) {
      this.openModals.set(modalName, data)
    },

    closeModal(modalName) {
      this.openModals.delete(modalName)
    },

    isModalOpen(modalName) {
      return this.openModals.has(modalName)
    },

    getModalData(modalName) {
      return this.openModals.get(modalName) || null
    },

    closeAllModals() {
      this.openModals.clear()
    },

    setLoading(value) {
      this.loading = value
    },

    setConnectionStatus(status) {
      if (!['connecting', 'connected', 'disconnected'].includes(status)) return
      this.connectionStatus = status
    },

    addNotification(message, type = 'info', duration = 3000) {
      const id = Date.now()
      const notification = { id, message, type }
      this.notifications.push(notification)

      if (duration > 0) {
        setTimeout(() => {
          this.removeNotification(id)
        }, duration)
      }

      return id
    },

    removeNotification(id) {
      const idx = this.notifications.findIndex(n => n.id === id)
      if (idx >= 0) {
        this.notifications.splice(idx, 1)
      }
    },

    clearNotifications() {
      this.notifications = []
    },

    reset() {
      this.sidebarOpen = true
      this.openModals.clear()
      this.notifications = []
      this.loading = false
      this.connectionStatus = 'disconnected'
    }
  }
  return store
}

test('UI Store - Initial State', async (t) => {
  await t.test('should initialize with default values', () => {
    localStorage.clear()
    const store = createMockUIStore()

    assert.strictEqual(store.theme, 'dark')
    assert.strictEqual(store.sidebarOpen, true)
    assert.strictEqual(store.openModals.size, 0)
    assert.deepStrictEqual(store.notifications, [])
    assert.strictEqual(store.loading, false)
    assert.strictEqual(store.connectionStatus, 'disconnected')
  })

  await t.test('should load theme from localStorage if available', () => {
    localStorage.clear()
    localStorage.setItem('ui_theme', 'light')
    const store = createMockUIStore()

    assert.strictEqual(store.theme, 'light')
  })
})

test('UI Store - toggleTheme', async (t) => {
  await t.test('should toggle theme between light and dark', () => {
    localStorage.clear()
    const store = createMockUIStore()

    assert.strictEqual(store.theme, 'dark')

    store.toggleTheme()

    assert.strictEqual(store.theme, 'light')

    store.toggleTheme()

    assert.strictEqual(store.theme, 'dark')
  })

  await t.test('should persist theme to localStorage', () => {
    localStorage.clear()
    const store = createMockUIStore()

    store.toggleTheme()

    assert.strictEqual(localStorage.getItem('ui_theme'), 'light')
  })
})

test('UI Store - setTheme', async (t) => {
  await t.test('should set specific theme', () => {
    localStorage.clear()
    const store = createMockUIStore()

    store.setTheme('light')

    assert.strictEqual(store.theme, 'light')
    assert.strictEqual(localStorage.getItem('ui_theme'), 'light')
  })

  await t.test('should ignore invalid theme values', () => {
    localStorage.clear()
    const store = createMockUIStore()
    const originalTheme = store.theme

    store.setTheme('invalid')

    assert.strictEqual(store.theme, originalTheme)
  })
})

test('UI Store - toggleSidebar', async (t) => {
  await t.test('should toggle sidebar state', () => {
    const store = createMockUIStore()

    assert.strictEqual(store.sidebarOpen, true)

    store.toggleSidebar()

    assert.strictEqual(store.sidebarOpen, false)

    store.toggleSidebar()

    assert.strictEqual(store.sidebarOpen, true)
  })
})

test('UI Store - Modal Management', async (t) => {
  await t.test('should open modal', () => {
    const store = createMockUIStore()

    store.openModal('settings')

    assert.strictEqual(store.isModalOpen('settings'), true)
  })

  await t.test('should open modal with data', () => {
    const store = createMockUIStore()
    const modalData = { userId: 123, name: 'Test' }

    store.openModal('editUser', modalData)

    assert.deepStrictEqual(store.getModalData('editUser'), modalData)
  })

  await t.test('should close modal', () => {
    const store = createMockUIStore()

    store.openModal('settings')
    assert.strictEqual(store.isModalOpen('settings'), true)

    store.closeModal('settings')

    assert.strictEqual(store.isModalOpen('settings'), false)
  })

  await t.test('should return null data for closed modal', () => {
    const store = createMockUIStore()

    assert.strictEqual(store.getModalData('closedModal'), null)
  })

  await t.test('should close all modals', () => {
    const store = createMockUIStore()

    store.openModal('settings')
    store.openModal('about')
    store.openModal('help')

    assert.strictEqual(store.openModals.size, 3)

    store.closeAllModals()

    assert.strictEqual(store.openModals.size, 0)
  })

  await t.test('should support multiple simultaneous modals', () => {
    const store = createMockUIStore()

    store.openModal('modal1', { data: 1 })
    store.openModal('modal2', { data: 2 })
    store.openModal('modal3', { data: 3 })

    assert.strictEqual(store.isModalOpen('modal1'), true)
    assert.strictEqual(store.isModalOpen('modal2'), true)
    assert.strictEqual(store.isModalOpen('modal3'), true)

    assert.deepStrictEqual(store.getModalData('modal2'), { data: 2 })
  })
})

test('UI Store - Loading State', async (t) => {
  await t.test('should set loading state', () => {
    const store = createMockUIStore()

    store.setLoading(true)

    assert.strictEqual(store.loading, true)

    store.setLoading(false)

    assert.strictEqual(store.loading, false)
  })
})

test('UI Store - Connection Status', async (t) => {
  await t.test('should set valid connection status', () => {
    const store = createMockUIStore()

    store.setConnectionStatus('connecting')

    assert.strictEqual(store.connectionStatus, 'connecting')

    store.setConnectionStatus('connected')

    assert.strictEqual(store.connectionStatus, 'connected')

    store.setConnectionStatus('disconnected')

    assert.strictEqual(store.connectionStatus, 'disconnected')
  })

  await t.test('should ignore invalid connection status', () => {
    const store = createMockUIStore()

    store.setConnectionStatus('invalid')

    assert.strictEqual(store.connectionStatus, 'disconnected')
  })
})

test('UI Store - Notifications', async (t) => {
  await t.test('should add notification', () => {
    const store = createMockUIStore()

    store.addNotification('Test notification')

    assert.strictEqual(store.notifications.length, 1)
    assert.strictEqual(store.notifications[0].message, 'Test notification')
    assert.strictEqual(store.notifications[0].type, 'info')
  })

  await t.test('should add notification with custom type', () => {
    const store = createMockUIStore()

    store.addNotification('Success', 'success')

    assert.strictEqual(store.notifications[0].type, 'success')
  })

  await t.test('should keep persistent notification (duration 0)', () => {
    const store = createMockUIStore()

    store.addNotification('Persistent', 'info', 0)

    assert.strictEqual(store.notifications.length, 1)
  })

  await t.test('should remove notification by ID', () => {
    const store = createMockUIStore()

    const id = store.addNotification('Message')

    assert.strictEqual(store.notifications.length, 1)

    store.removeNotification(id)

    assert.strictEqual(store.notifications.length, 0)
  })

  await t.test('should clear all notifications', () => {
    const store = createMockUIStore()

    store.addNotification('Notif 1')
    store.addNotification('Notif 2')
    store.addNotification('Notif 3')

    assert.strictEqual(store.notifications.length, 3)

    store.clearNotifications()

    assert.strictEqual(store.notifications.length, 0)
  })
})

test('UI Store - reset', async (t) => {
  await t.test('should reset UI to defaults', () => {
    localStorage.clear()
    const store = createMockUIStore()

    // Change state
    store.sidebarOpen = false
    store.openModal('testModal')
    store.addNotification('test')
    store.setLoading(true)
    store.setConnectionStatus('connected')

    // Reset
    store.reset()

    // Verify defaults
    assert.strictEqual(store.sidebarOpen, true)
    assert.strictEqual(store.openModals.size, 0)
    assert.strictEqual(store.notifications.length, 0)
    assert.strictEqual(store.loading, false)
    assert.strictEqual(store.connectionStatus, 'disconnected')
  })

  await t.test('should not reset theme', () => {
    localStorage.clear()
    const store = createMockUIStore()

    store.setTheme('light')
    store.reset()

    assert.strictEqual(store.theme, 'light')
  })
})

test('UI Store - Integrated Scenarios', async (t) => {
  await t.test('should handle user theme preference during session', () => {
    localStorage.clear()
    const store = createMockUIStore()

    // User starts with default dark theme
    assert.strictEqual(store.theme, 'dark')

    // User toggles to light
    store.toggleTheme()

    assert.strictEqual(store.theme, 'light')
    assert.strictEqual(localStorage.getItem('ui_theme'), 'light')

    // On next load, should remember preference
    const newStore = createMockUIStore()
    assert.strictEqual(newStore.theme, 'light')
  })

  await t.test('should manage multiple modals independently', () => {
    const store = createMockUIStore()

    store.openModal('userSettings', { userId: 1 })
    store.openModal('deviceControl', { deviceCode: 'light' })

    assert.strictEqual(store.isModalOpen('userSettings'), true)
    assert.strictEqual(store.isModalOpen('deviceControl'), true)

    store.closeModal('userSettings')

    assert.strictEqual(store.isModalOpen('userSettings'), false)
    assert.strictEqual(store.isModalOpen('deviceControl'), true)
  })

  await t.test('should handle connection status changes', () => {
    const store = createMockUIStore()

    assert.strictEqual(store.connectionStatus, 'disconnected')

    store.setConnectionStatus('connecting')
    assert.strictEqual(store.connectionStatus, 'connecting')

    store.setConnectionStatus('connected')
    assert.strictEqual(store.connectionStatus, 'connected')

    store.setConnectionStatus('disconnected')
    assert.strictEqual(store.connectionStatus, 'disconnected')
  })
})
