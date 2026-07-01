/**
 * Unit Tests: Authentication Storage Module
 * Tests for src/services/auth.storage.js
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  getBearerAuthToken,
  getAuthToken,
  getAuthUser,
  getCsrfToken,
  isAuthenticated,
  saveAuthSession,
  clearAuthSession,
  getAuthHeaders,
} from '../src/services/auth.storage.js'

const AUTH_TOKEN_KEY = 'batman_os_token'
const AUTH_USER_KEY = 'batman_os_user'
const AUTH_CSRF_KEY = 'batman_os_csrf'

describe('Auth Storage Module', () => {
  beforeEach(() => {
    window.sessionStorage.clear()
    window.localStorage.clear()
    vi.clearAllMocks()
  })

  describe('getBearerAuthToken', () => {
    it('should return empty string when no token is set', () => {
      const token = getBearerAuthToken()
      expect(token).toBe('')
    })

    it('should return Bearer prefix with token when token is set', () => {
      window.sessionStorage.setItem(AUTH_TOKEN_KEY, 'test-token-123')
      const token = getBearerAuthToken()
      expect(token).toBe('Bearer test-token-123')
    })

    it('should fallback to localStorage when sessionStorage getter fails', () => {
      window.localStorage.setItem(AUTH_TOKEN_KEY, 'legacy-token-xyz')
      const sessionSpy = vi.spyOn(window, 'sessionStorage', 'get').mockImplementation(() => {
        throw new DOMException('sessionStorage is not available for opaque origins', 'SecurityError')
      })

      const token = getBearerAuthToken()

      expect(token).toBe('Bearer legacy-token-xyz')
      sessionSpy.mockRestore()
    })
  })

  describe('getAuthToken', () => {
    it('should return token without Bearer prefix', () => {
      window.sessionStorage.setItem(AUTH_TOKEN_KEY, 'raw-token-value')
      const token = getAuthToken()
      expect(token).toBe('raw-token-value')
    })

    it('should return empty string when no token exists', () => {
      const token = getAuthToken()
      expect(token).toBe('')
    })
  })

  describe('getAuthUser', () => {
    it('should return parsed user object', () => {
      const userData = { id: 1, username: 'john', email: 'john@example.com', role: 'user' }
      window.sessionStorage.setItem(AUTH_USER_KEY, JSON.stringify(userData))
      const user = getAuthUser()
      expect(user).toEqual(userData)
    })

    it('should return null when user data is not set', () => {
      const user = getAuthUser()
      expect(user).toBeNull()
    })

    it('should return null when user data is invalid JSON', () => {
      window.sessionStorage.setItem(AUTH_USER_KEY, 'invalid-json{]')
      const user = getAuthUser()
      expect(user).toBeNull()
    })
  })

  describe('getCsrfToken', () => {
    it('should return CSRF token when set', () => {
      window.sessionStorage.setItem(AUTH_CSRF_KEY, 'csrf-token-xyz')
      const csrf = getCsrfToken()
      expect(csrf).toBe('csrf-token-xyz')
    })

    it('should return empty string when CSRF token is not set', () => {
      const csrf = getCsrfToken()
      expect(csrf).toBe('')
    })
  })

  describe('isAuthenticated', () => {
    it('should return false when no token or user', () => {
      const result = isAuthenticated()
      expect(result).toBe(false)
    })

    it('should return false when only token is set', () => {
      window.sessionStorage.setItem(AUTH_TOKEN_KEY, 'token-123')
      const result = isAuthenticated()
      expect(result).toBe(false)
    })

    it('should return true when both token and user are set', () => {
      window.sessionStorage.setItem(AUTH_TOKEN_KEY, 'token-123')
      window.sessionStorage.setItem(AUTH_USER_KEY, JSON.stringify({ id: 1, username: 'john' }))
      const result = isAuthenticated()
      expect(result).toBe(true)
    })
  })

  describe('saveAuthSession', () => {
    it('should save token, user, and CSRF token to sessionStorage', () => {
      const token = 'new-token'
      const user = { id: 1, username: 'john', email: 'john@example.com' }
      const csrf = 'csrf-token-abc'

      saveAuthSession(token, user, csrf)

      expect(window.sessionStorage.getItem(AUTH_TOKEN_KEY)).toBe(token)
      expect(window.sessionStorage.getItem(AUTH_USER_KEY)).toBe(JSON.stringify(user))
      expect(window.sessionStorage.getItem(AUTH_CSRF_KEY)).toBe(csrf)
    })

    it('should clear previous session before saving', () => {
      window.sessionStorage.setItem(AUTH_TOKEN_KEY, 'old-token')
      window.sessionStorage.setItem(AUTH_USER_KEY, JSON.stringify({ id: 999, username: 'old' }))
      window.sessionStorage.setItem(AUTH_CSRF_KEY, 'old-csrf')

      saveAuthSession('token', { id: 1, username: 'new' })

      expect(window.sessionStorage.getItem(AUTH_TOKEN_KEY)).toBe('token')
      expect(window.sessionStorage.getItem(AUTH_USER_KEY)).toBe(JSON.stringify({ id: 1, username: 'new' }))
      expect(window.sessionStorage.getItem(AUTH_CSRF_KEY)).toBeNull()
    })
  })

  describe('clearAuthSession', () => {
    it('should remove all auth data from sessionStorage', () => {
      window.sessionStorage.setItem(AUTH_TOKEN_KEY, 'token')
      window.sessionStorage.setItem(AUTH_USER_KEY, JSON.stringify({ id: 1 }))
      window.sessionStorage.setItem(AUTH_CSRF_KEY, 'csrf')

      clearAuthSession()

      expect(window.sessionStorage.getItem(AUTH_TOKEN_KEY)).toBeNull()
      expect(window.sessionStorage.getItem(AUTH_USER_KEY)).toBeNull()
      expect(window.sessionStorage.getItem(AUTH_CSRF_KEY)).toBeNull()
    })
  })

  describe('getAuthHeaders', () => {
    it('should return headers object with Authorization and CSRF token', () => {
      window.sessionStorage.setItem(AUTH_TOKEN_KEY, 'auth-token')
      window.sessionStorage.setItem(AUTH_CSRF_KEY, 'csrf-token')

      const headers = getAuthHeaders()

      expect(headers).toEqual({
        Authorization: 'Bearer auth-token',
        'X-CSRF-Token': 'csrf-token',
      })
    })

    it('should omit Authorization header when no token', () => {
      window.sessionStorage.setItem(AUTH_CSRF_KEY, 'csrf-token')

      const headers = getAuthHeaders()

      expect(headers).toEqual({
        'X-CSRF-Token': 'csrf-token',
      })
    })

    it('should return empty object when no auth data', () => {
      const headers = getAuthHeaders()
      expect(headers).toEqual({})
    })
  })
})
