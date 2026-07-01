import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * Alert/Notification Store (Pinia)
 * Manages alerts, notifications, and toasts
 */
export const useAlertStore = defineStore('alert', () => {
  // ============= STATE =============
  const alerts = ref([])  // Array<{ id, type, message, timestamp, persistent }>

  // ============= ACTIONS =============

  /**
   * Add alert with auto-dismiss
   * @param {string} type Type: 'success', 'error', 'warning', 'info'
   * @param {string} message Alert message
   * @param {number} duration Auto-dismiss time (ms), 0 = never
   * @returns {number} Alert ID
   */
  function addAlert(type, message, duration = 3000) {
    const id = Date.now() + Math.random()
    const alert = {
      id,
      type,
      message,
      timestamp: new Date(),
      persistent: duration === 0,
    }

    alerts.value.push(alert)
    console.log(`[Alert] ${type.toUpperCase()}: ${message}`)

    if (duration > 0) {
      setTimeout(() => removeAlert(id), duration)
    }

    return id
  }

  /**
   * Add success alert (auto-dismiss in 3s)
   */
  function addSuccess(message, duration = 3000) {
    return addAlert('success', message, duration)
  }

  /**
   * Add error alert (auto-dismiss in 5s)
   */
  function addError(message, duration = 5000) {
    return addAlert('error', message, duration)
  }

  /**
   * Add warning alert (auto-dismiss in 4s)
   */
  function addWarning(message, duration = 4000) {
    return addAlert('warning', message, duration)
  }

  /**
   * Add info alert (auto-dismiss in 3s)
   */
  function addInfo(message, duration = 3000) {
    return addAlert('info', message, duration)
  }

  /**
   * Remove alert by ID
   */
  function removeAlert(id) {
    const index = alerts.value.findIndex(a => a.id === id)
    if (index >= 0) {
      alerts.value.splice(index, 1)
    }
  }

  /**
   * Clear all alerts
   */
  function clearAll() {
    alerts.value = []
  }

  /**
   * Clear alerts of specific type
   */
  function clearByType(type) {
    alerts.value = alerts.value.filter(a => a.type !== type)
  }

  /**
   * Clear auto-dismiss alerts (keep persistent ones)
   */
  function clearAutoDissmiss() {
    alerts.value = alerts.value.filter(a => a.persistent)
  }

  /**
   * Get alerts of specific type
   */
  function getAlertsByType(type) {
    return alerts.value.filter(a => a.type === type)
  }

  /**
   * Check if there are any errors
   */
  function hasErrors() {
    return alerts.value.some(a => a.type === 'error')
  }

  return {
    // State
    alerts,

    // Actions
    addAlert,
    addSuccess,
    addError,
    addWarning,
    addInfo,
    removeAlert,
    clearAll,
    clearByType,
    clearAutoDissmiss,
    getAlertsByType,
    hasErrors,
  }
})
