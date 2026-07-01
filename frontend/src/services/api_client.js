// src/services/api/api_client.js

const API_BASE = 'http://127.0.0.1:5000'
import { getBearerAuthToken } from './auth.storage.js'

async function apiFetch(path, options = {}) {
  const bearerToken = getBearerAuthToken()
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(bearerToken
        ? { 'Authorization': 'Bearer ' + bearerToken }
        : {}),
      ...(options.headers || {})
    }
  })

  if (!res.ok) {
    console.error('[API]', path, 'failed:', res.status)
    return null
  }

  return res.json()
}

export const ApiClient = {
  async getPatientProfile() {
    const data = await apiFetch('/api/patient-report/profile');
    return data?.profile || {};
  },
  async getHeartRateSummary() {
    const data = await apiFetch('/api/patient-report/hr-records');
    return data?.summary || {};
  },

  async getDevices() {
    const data = await apiFetch('/api/devices')
    return data?.data || []
  },

  async getDeviceStatus() {
    return apiFetch('/api/device-status')
  },

  async getBrokerConfig() {
    return apiFetch('/api/broker-config')
  },

  async saveBrokerConfig(config) {
    return apiFetch('/api/broker-config', {
      method: 'POST',
      body: JSON.stringify(config)
    })
  },

  async createDevice(data) {
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
    return apiFetch('/api/devices', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  },

  async deleteDevice(code) {
    return apiFetch(`/api/devices/${encodeURIComponent(code)}`, {
      method: 'DELETE'
    })
  },

  async sendControl(code, action) {
    return apiFetch('/api/devices/control', {
      method: 'POST',
      body: JSON.stringify({ device_code: code, action })
    })
  }
  ,

    async updateDevice(id, updates) {
      return apiFetch(`/api/devices/${id}`, {
        method: 'PUT',
        body: JSON.stringify(updates)
      })
    },

    async controlDevice(command) {
      return apiFetch('/api/device-control', {
        method: 'POST',
        body: JSON.stringify(command)
      })
    },

    async getAlerts() {
      const data = await apiFetch('/api/alerts')
      return data?.alerts || []
    },

    async getAlertsByType(type) {
      const data = await apiFetch(`/api/alerts?type=${encodeURIComponent(type)}`)
      return data?.alerts || []
    },

    async markAlertAsRead(id) {
      return apiFetch(`/api/alerts/${id}/read`, { method: 'PUT' })
    },

    async markAllAlertsAsRead() {
      return apiFetch('/api/alerts/mark-all-read', { method: 'PUT' })
    },

    async deleteAlert(id) {
      return apiFetch(`/api/alerts/${id}`, { method: 'DELETE' })
    },

    async dismissAlert(id, reason) {
      return apiFetch(`/api/alerts/${id}/dismiss`, {
        method: 'PUT',
        body: JSON.stringify(reason ? { reason } : {})
      })
    },

    async getUnreadAlertCount() {
      const data = await apiFetch('/api/alerts/unread-count')
      return data?.unreadCount ?? 0
    },

    async acknowledgeAlert(id, note) {
      return apiFetch(`/api/alerts/${id}/acknowledge`, {
        method: 'PUT',
        body: JSON.stringify(note ? { note } : {})
      })
    }
}
