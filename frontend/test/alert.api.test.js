/**
 * Unit Tests: Alert API Module
 * Tests for src/services/api_client.js - Alert operations
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ApiClient } from '../src/services/api_client.js'

describe('Alert API Module', () => {
  beforeEach(() => {
    global.fetch = vi.fn()
    vi.clearAllMocks()
  })

  describe('getAlerts', () => {
    it('should fetch all alerts', async () => {
      const mockAlerts = [
        {
          id: 1,
          type: 'health_warning',
          message: 'High heart rate detected',
          severity: 'high',
          createdAt: '2026-04-19T10:00:00Z',
          isRead: false,
        },
        {
          id: 2,
          type: 'device_offline',
          message: 'Fan device offline',
          severity: 'medium',
          createdAt: '2026-04-19T09:00:00Z',
          isRead: true,
        },
      ]

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ alerts: mockAlerts }),
      })

      const alerts = await ApiClient.getAlerts()

      expect(alerts).toEqual(mockAlerts)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/alerts'),
        expect.any(Object)
      )
    })

    it('should handle empty alerts list', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ alerts: [] }),
      })

      const alerts = await ApiClient.getAlerts()

      expect(alerts).toEqual([])
    })

    it('should return empty array on API error', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      })

      const alerts = await ApiClient.getAlerts()

      expect(alerts).toEqual([])
    })
  })

  describe('getAlertsByType', () => {
    it('should fetch alerts filtered by type', async () => {
      const alertType = 'health_warning'
      const mockAlerts = [
        {
          id: 1,
          type: 'health_warning',
          message: 'High temperature',
          severity: 'high',
        },
      ]

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ alerts: mockAlerts }),
      })

      const alerts = await ApiClient.getAlertsByType(alertType)

      expect(alerts).toEqual(mockAlerts)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/api/alerts?type=${alertType}`),
        expect.any(Object)
      )
    })

    it('should handle alerts with no results', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ alerts: [] }),
      })

      const alerts = await ApiClient.getAlertsByType('nonexistent_type')

      expect(alerts).toEqual([])
    })
  })

  describe('markAlertAsRead', () => {
    it('should mark a single alert as read', async () => {
      const alertId = 1

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: alertId,
          isRead: true,
          updatedAt: '2026-04-19T11:00:00Z',
        }),
      })

      const result = await ApiClient.markAlertAsRead(alertId)

      expect(result).toBeDefined()
      expect(result.isRead).toBe(true)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/api/alerts/${alertId}/read`),
        expect.objectContaining({
          method: 'PUT',
        })
      )
    })

    it('should handle marking alert as read with failure', async () => {
      const alertId = 1

      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
      })

      const result = await ApiClient.markAlertAsRead(alertId)

      expect(result).toBeNull()
    })
  })

  describe('markAllAlertsAsRead', () => {
    it('should mark all alerts as read', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          updatedCount: 5,
          timestamp: '2026-04-19T11:00:00Z',
        }),
      })

      const result = await ApiClient.markAllAlertsAsRead()

      expect(result).toBeDefined()
      expect(result.updatedCount).toBe(5)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/alerts/mark-all-read'),
        expect.objectContaining({
          method: 'PUT',
        })
      )
    })

    it('should handle marking all alerts as read with no alerts', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          updatedCount: 0,
        }),
      })

      const result = await ApiClient.markAllAlertsAsRead()

      expect(result.updatedCount).toBe(0)
    })
  })

  describe('deleteAlert', () => {
    it('should delete an alert', async () => {
      const alertId = 1

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true }),
      })

      const result = await ApiClient.deleteAlert(alertId)

      expect(result).toBeDefined()
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/api/alerts/${alertId}`),
        expect.objectContaining({
          method: 'DELETE',
        })
      )
    })

    it('should handle deletion of nonexistent alert', async () => {
      const alertId = 999

      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
      })

      const result = await ApiClient.deleteAlert(alertId)

      expect(result).toBeNull()
    })
  })

  describe('dismissAlert', () => {
    it('should dismiss an alert', async () => {
      const alertId = 1

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: alertId,
          dismissed: true,
          dismissedAt: '2026-04-19T11:15:00Z',
        }),
      })

      const result = await ApiClient.dismissAlert(alertId)

      expect(result.dismissed).toBe(true)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/api/alerts/${alertId}/dismiss`),
        expect.any(Object)
      )
    })

    it('should handle dismiss with reason', async () => {
      const alertId = 1
      const reason = 'false_alarm'

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: alertId,
          dismissed: true,
          dismissReason: reason,
        }),
      })

      const result = await ApiClient.dismissAlert(alertId, reason)

      expect(result.dismissed).toBe(true)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: expect.stringContaining(reason),
        })
      )
    })
  })

  describe('getUnreadAlertCount', () => {
    it('should fetch unread alert count', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ unreadCount: 3 }),
      })

      const count = await ApiClient.getUnreadAlertCount()

      expect(count).toBe(3)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/alerts/unread-count'),
        expect.any(Object)
      )
    })

    it('should return 0 when no unread alerts', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ unreadCount: 0 }),
      })

      const count = await ApiClient.getUnreadAlertCount()

      expect(count).toBe(0)
    })
  })

  describe('acknowledgeAlert', () => {
    it('should acknowledge an alert', async () => {
      const alertId = 1

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: alertId,
          acknowledged: true,
          acknowledgedAt: '2026-04-19T11:20:00Z',
        }),
      })

      const result = await ApiClient.acknowledgeAlert(alertId)

      expect(result.acknowledged).toBe(true)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/api/alerts/${alertId}/acknowledge`),
        expect.any(Object)
      )
    })

    it('should handle acknowledge with note', async () => {
      const alertId = 1
      const note = 'Checked patient, vitals stable'

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: alertId,
          acknowledged: true,
          note: note,
        }),
      })

      const result = await ApiClient.acknowledgeAlert(alertId, note)

      expect(result.note).toBe(note)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: expect.stringContaining(note),
        })
      )
    })
  })

  describe('Alert API Error Handling', () => {
    it('should log errors on failed request', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error')

      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      })

      const result = await ApiClient.getAlerts()

      expect(result).toEqual([])
      expect(consoleErrorSpy).toHaveBeenCalled()

      consoleErrorSpy.mockRestore()
    })

    it('should handle network timeout gracefully', async () => {
      global.fetch.mockRejectedValueOnce(new Error('Timeout'))

      try {
        await ApiClient.getAlerts()
      } catch (e) {
        expect(e.message).toContain('Timeout')
      }
    })

    it('should handle malformed alert response', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          // Missing required fields
          data: null,
        }),
      })

      const result = await ApiClient.getAlerts()

      expect(result).toEqual([])
    })

    it('should handle concurrent alert operations', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true }),
      })

      const operations = [
        ApiClient.markAlertAsRead(1),
        ApiClient.markAlertAsRead(2),
        ApiClient.markAlertAsRead(3),
      ]

      const results = await Promise.all(operations)

      expect(results).toHaveLength(3)
      expect(global.fetch).toHaveBeenCalledTimes(3)
    })
  })

  describe('Alert Filtering and Sorting', () => {
    it('should fetch alerts with filters', async () => {
      const filters = {
        severity: 'high',
        isRead: false,
        dateFrom: '2026-04-19',
      }

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ alerts: [] }),
      })

      await ApiClient.getAlerts(filters)

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/alerts'),
        expect.any(Object)
      )
    })

    it('should sort alerts by date descending', async () => {
      const mockAlerts = [
        {
          id: 3,
          createdAt: '2026-04-19T12:00:00Z',
        },
        {
          id: 1,
          createdAt: '2026-04-19T10:00:00Z',
        },
        {
          id: 2,
          createdAt: '2026-04-19T11:00:00Z',
        },
      ]

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ alerts: mockAlerts }),
      })

      const alerts = await ApiClient.getAlerts({ sort: 'date_desc' })

      // Should be returned in order from API
      expect(alerts).toHaveLength(3)
    })
  })
})
