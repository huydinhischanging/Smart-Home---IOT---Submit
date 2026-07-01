import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * UI Store (Pinia)
 * Manages UI state: modals, menus, sidebars, themes
 */
export const useUIStore = defineStore('ui', () => {
  // ============= STATE =============
  const theme = ref(localStorage.getItem('ui_theme') || 'dark')  // 'light' or 'dark'
  const sidebarOpen = ref(true)
  const openModals = ref(new Map())  // Map<modalName, { isOpen, data }>
  const notifications = ref([])
  const loading = ref(false)
  const connectionStatus = ref('disconnected')  // 'disconnected', 'connecting', 'connected'

  // ============= ACTIONS =============

  /**
   * Toggle theme between light and dark
   */
  function toggleTheme() {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
    localStorage.setItem('ui_theme', theme.value)

    // Apply to document
    document.documentElement.setAttribute('data-theme', theme.value)
    console.log(`[UI] Theme: ${theme.value}`)
  }

  /**
   * Set specific theme
   */
  function setTheme(newTheme) {
    if (newTheme === 'light' || newTheme === 'dark') {
      theme.value = newTheme
      localStorage.setItem('ui_theme', theme.value)
      document.documentElement.setAttribute('data-theme', theme.value)
      console.log(`[UI] Theme: ${theme.value}`)
    }
  }

  /**
   * Toggle sidebar
   */
  function toggleSidebar() {
    sidebarOpen.value = !sidebarOpen.value
    console.log(`[UI] Sidebar: ${sidebarOpen.value ? 'open' : 'closed'}`)
  }

  /**
   * Open modal with optional data
   */
  function openModal(modalName, data = null) {
    openModals.value.set(modalName, {
      isOpen: true,
      data,
    })
    console.log(`[UI] Modal opened: ${modalName}`)
  }

  /**
   * Close modal
   */
  function closeModal(modalName) {
    openModals.value.delete(modalName)
    console.log(`[UI] Modal closed: ${modalName}`)
  }

  /**
   * Check if modal is open
   */
  function isModalOpen(modalName) {
    return openModals.value.get(modalName)?.isOpen || false
  }

  /**
   * Get modal data
   */
  function getModalData(modalName) {
    return openModals.value.get(modalName)?.data || null
  }

  /**
   * Close all modals
   */
  function closeAllModals() {
    openModals.value.clear()
    console.log('[UI] All modals closed')
  }

  /**
   * Set loading state
   */
  function setLoading(isLoading) {
    loading.value = isLoading
  }

  /**
   * Update connection status
   */
  function setConnectionStatus(status) {
    if (['disconnected', 'connecting', 'connected'].includes(status)) {
      connectionStatus.value = status
      console.log(`[UI] Connection: ${status}`)
    }
  }

  /**
   * Add notification (different from alerts)
   * Used for non-critical updates
   */
  function addNotification(message, type = 'info', duration = 3000) {
    const id = Date.now()
    const notification = { id, message, type, timestamp: new Date() }

    notifications.value.push(notification)

    if (duration > 0) {
      setTimeout(() => removeNotification(id), duration)
    }

    return id
  }

  /**
   * Remove notification
   */
  function removeNotification(id) {
    const index = notifications.value.findIndex(n => n.id === id)
    if (index >= 0) {
      notifications.value.splice(index, 1)
    }
  }

  /**
   * Clear all notifications
   */
  function clearNotifications() {
    notifications.value = []
  }

  /**
   * Reset UI to defaults
   */
  function reset() {
    sidebarOpen.value = true
    openModals.value.clear()
    notifications.value = []
    loading.value = false
    connectionStatus.value = 'disconnected'
    console.log('[UI] Reset to defaults')
  }

  return {
    // State
    theme,
    sidebarOpen,
    openModals,
    notifications,
    loading,
    connectionStatus,

    // Actions
    toggleTheme,
    setTheme,
    toggleSidebar,
    openModal,
    closeModal,
    isModalOpen,
    getModalData,
    closeAllModals,
    setLoading,
    setConnectionStatus,
    addNotification,
    removeNotification,
    clearNotifications,
    reset,
  }
})
