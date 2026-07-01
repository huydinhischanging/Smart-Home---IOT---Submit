import { createPinia } from 'pinia'

// Import all stores
import { useAuthStore } from './auth.store'
import { useDeviceStore } from './device.store'
import { useAlertStore } from './alert.store'
import { useUIStore } from './ui.store'

/**
 * Create and configure Pinia store
 */
export const pinia = createPinia()

/**
 * Pinia Plugin: Log state mutations in development
 */
if (import.meta.env.DEV) {
  pinia.use(({ store }) => {
    // Log all actions
    store.$onAction(({ name, args, after, onError }) => {
      console.log(`[${store.$id}] Action: ${name}(${JSON.stringify(args)})`)

      after(() => {
        console.log(`[${store.$id}] Action complete: ${name}`)
      })

      onError((error) => {
        console.error(`[${store.$id}] Action error: ${name}`, error)
      })
    })

    // Log all state changes
    store.$subscribe(({ events }) => {
      events.forEach(event => {
        console.log(`[${store.$id}] State changed:`, event.key, event.newValue)
      })
    })
  })
}

/**
 * Initialize all stores
 * Call this once on app startup
 */
export async function initializeStores(authHeader) {
  const authStore = useAuthStore()
  const deviceStore = useDeviceStore()
  const uiStore = useUIStore()

  // Load user profile
  const userLoaded = await authStore.loadUser()
  if (!userLoaded) {
    console.warn('[Stores] Failed to load user profile')
    return false
  }

  // Load devices
  await deviceStore.fetchDevices(authHeader)

  // Set initial theme
  const savedTheme = localStorage.getItem('ui_theme') || 'dark'
  uiStore.setTheme(savedTheme)

  console.log('[Stores] Initialized successfully')
  return true
}

// Export all stores
export { useAuthStore, useDeviceStore, useAlertStore, useUIStore }
