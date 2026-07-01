// src/services/api/automation.api.js
// CRUD for device schedules and automations

import { HttpClient } from './http.client.js'

export const AutomationApi = {

  // =====================================================
  // SCHEDULES
  // =====================================================

  async listSchedules() {
    const res = await HttpClient.get('/api/automation/schedules')
    if (!res || res.success !== true) throw new Error(res?.message || 'Failed to fetch schedules')
    return res.data
  },

  async createSchedule({ device_id, label, cron_expr, action, remind_only = false }) {
    const res = await HttpClient.post('/api/automation/schedules', {
      device_id,
      label,
      cron_expr,
      action,
      remind_only,
    })
    if (!res || res.success !== true) throw new Error(res?.message || 'Failed to create schedule')
    return res.id
  },

  async updateSchedule(id, patch) {
    const res = await HttpClient.patch(`/api/automation/schedules/${id}`, patch)
    if (!res || res.success !== true) throw new Error(res?.message || 'Failed to update schedule')
    return res
  },

  async deleteSchedule(id) {
    const res = await HttpClient.delete(`/api/automation/schedules/${id}`)
    if (!res || res.success !== true) throw new Error(res?.message || 'Failed to delete schedule')
    return true
  },

  // =====================================================
  // HELPERS
  // =====================================================

  /**
   * Build a cron expression from user-friendly inputs.
   * @param {string} time       "HH:MM"
   * @param {string} recurrence "daily"|"weekday"|"weekend"|"specific"|"custom"
   * @param {string} [customCron]   used when recurrence === "custom"
   * @param {string[]} [specificDays]  day numbers ["1","3"] used when recurrence === "specific"
   * @returns {string} cron expression
   */
  buildCron(time, recurrence, customCron = '', specificDays = []) {
    if (recurrence === 'custom') return customCron.trim()
    const [hh, mm] = time.split(':').map(Number)
    switch (recurrence) {
      case 'daily':    return `${mm} ${hh} * * *`
      case 'weekday':  return `${mm} ${hh} * * 1-5`
      case 'weekend':  return `${mm} ${hh} * * 6,0`
      case 'specific': {
        if (!specificDays.length) return ''
        const dow = [...specificDays].sort((a, b) => Number(a) - Number(b)).join(',')
        return `${mm} ${hh} * * ${dow}`
      }
      default:         return `${mm} ${hh} * * *`
    }
  },

  /**
   * Human-readable description of a cron expression.
   * @param {string} cron_expr
   * @returns {string}
   */
  describeCron(cron_expr) {
    if (!cron_expr) return ''
    const parts = cron_expr.trim().split(/\s+/)
    if (parts.length !== 5) return cron_expr
    const [min, hour, , , dow] = parts
    const hh = hour.padStart(2, '0')
    const mm = min.padStart(2, '0')
    const time = `${hh}:${mm}`
    if (dow === '*')                      return `Daily ${time}`
    if (dow === '1-5')                    return `Mon–Fri ${time}`
    if (dow === '6,0' || dow === '0,6')  return `Sat–Sun ${time}`
    // Specific days: "1,3" → "Mon, Wed 22:00"
    const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    if (/^[\d,]+$/.test(dow)) {
      const dayLabels = dow.split(',').map(d => DAY_NAMES[+d] ?? d).join(', ')
      return `${dayLabels} ${time}`
    }
    return `${time} (${cron_expr})`
  },
}
