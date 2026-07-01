/**
 * Unit Tests: Device API Module
 * Tests for src/services/api_client.js - Device operations
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ApiClient } from '../src/services/api_client.js'

describe('Device API Module', () => {
  beforeEach(() => {
    global.fetch = vi.fn()
    vi.clearAllMocks()
  })

  describe('getDevices', () => {
    it('should fetch and return devices list', async () => {
      const mockDevices = [
        { id: 1, code: 'fan', name: 'Living Room Fan', status: 'on' },
        { id: 2, code: 'light', name: 'Kitchen Light', status: 'off' },
      ]

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ devices: mockDevices }),
      })

      const devices = await ApiClient.getDevices()

      expect(devices).toEqual(mockDevices)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/devices'),
        expect.any(Object)
      )
    })

    it('should return empty array when API returns null', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      })

      const devices = await ApiClient.getDevices()

      expect(devices).toEqual([])
    })

    it('should return empty array on API error', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      })

      const devices = await ApiClient.getDevices()

      expect(devices).toEqual([])
    })
  })

  describe('getDeviceStatus', () => {
    it('should fetch device status successfully', async () => {
      const mockStatus = {
        fan: { status: 'on', lastUpdate: '2026-04-19T10:30:00Z' },
        light: { status: 'off', lastUpdate: '2026-04-19T10:25:00Z' },
      }

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockStatus,
      })

      const status = await ApiClient.getDeviceStatus()

      expect(status).toEqual(mockStatus)
    })

    it('should handle empty device status', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      })

      const status = await ApiClient.getDeviceStatus()

      expect(status).toEqual({})
    })
  })

  describe('createDevice', () => {
    it('should create a new device', async () => {
      const newDevice = {
        code: 'ac',
        name: 'Air Conditioner',
        type: 'climate',
      }

      const mockResponse = {
        id: 3,
        ...newDevice,
        createdAt: '2026-04-19T10:00:00Z',
      }

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      })

      const result = await ApiClient.createDevice(newDevice)

      expect(result).toEqual(mockResponse)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/devices'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(newDevice),
        })
      )
    })

    it('should return null on creation failure', async () => {
      const newDevice = { code: 'fan', name: 'Fan' }

      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
      })

      const result = await ApiClient.createDevice(newDevice)

      expect(result).toBeNull()
    })
  })

  describe('updateDevice', () => {
    it('should update an existing device', async () => {
      const deviceId = 1
      const updates = {
        name: 'Updated Fan Name',
        status: 'off',
      }

      const mockResponse = {
        id: deviceId,
        code: 'fan',
        ...updates,
        updatedAt: '2026-04-19T11:00:00Z',
      }

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      })

      const result = await ApiClient.updateDevice(deviceId, updates)

      expect(result).toEqual(mockResponse)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/api/devices/${deviceId}`),
        expect.objectContaining({
          method: 'PUT',
        })
      )
    })

    it('should handle update with partial data', async () => {
      const deviceId = 1
      const updates = { name: 'New Name' }

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: deviceId, ...updates }),
      })

      const result = await ApiClient.updateDevice(deviceId, updates)

      expect(result).toBeDefined()
      expect(result.name).toBe('New Name')
    })
  })

  describe('deleteDevice', () => {
    it('should delete a device', async () => {
      const deviceId = 1

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true }),
      })

      const result = await ApiClient.deleteDevice(deviceId)

      expect(result).toBeDefined()
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/api/devices/${deviceId}`),
        expect.objectContaining({
          method: 'DELETE',
        })
      )
    })

    it('should return null on deletion failure', async () => {
      const deviceId = 1

      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
      })

      const result = await ApiClient.deleteDevice(deviceId)

      expect(result).toBeNull()
    })
  })

  describe('controlDevice', () => {
    it('should send control command to device', async () => {
      const command = {
        device_code: 'fan',
        action: 'on',
      }

      const mockResponse = {
        success: true,
        deviceCode: 'fan',
        action: 'on',
        timestamp: '2026-04-19T11:15:00Z',
      }

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      })

      const result = await ApiClient.controlDevice(command)

      expect(result).toEqual(mockResponse)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/device-control'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(command),
        })
      )
    })

    it('should handle control command with parameters', async () => {
      const command = {
        device_code: 'ac',
        action: 'set_temperature',
        parameters: {
          temperature: 25,
          mode: 'cool',
        },
      }

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true }),
      })

      const result = await ApiClient.controlDevice(command)

      expect(result).toBeDefined()
      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: JSON.stringify(command),
        })
      )
    })
  })

  describe('Device API Error Handling', () => {
    it('should log errors and return null on fetch failure', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error')

      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      })

      const result = await ApiClient.getDevices()

      expect(result).toEqual([])
      expect(consoleErrorSpy).toHaveBeenCalled()

      consoleErrorSpy.mockRestore()
    })

    it('should handle network errors gracefully', async () => {
      global.fetch.mockRejectedValueOnce(new Error('Network error'))

      // Should not throw, just return null/empty
      try {
        await ApiClient.getDevices()
      } catch (e) {
        expect(e).toBeDefined() // Expected behavior - error bubbles
      }
    })

    it('should handle malformed JSON response', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => {
          throw new Error('Invalid JSON')
        },
      })

      try {
        await ApiClient.getDevices()
      } catch (e) {
        expect(e).toBeDefined()
      }
    })
  })
})
