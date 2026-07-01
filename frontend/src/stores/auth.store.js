import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getAuthToken,
  getAuthUser,
  saveAuthSession,
  clearAuthSession,
} from '../services/auth.storage.js'

/**
 * Authentication Store (Pinia)
 * Manages user login state, tokens, and user profile
 */
export const useAuthStore = defineStore('auth', () => {
  // ============= STATE =============
  // Delegate to auth.storage.js (sessionStorage, migrates old localStorage tokens)
  const token = ref(getAuthToken())
  const user = ref(getAuthUser())  // restore on page refresh
  const isLoading = ref(false)
  const error = ref(null)

  // ============= COMPUTED =============
  const isAuthenticated = computed(() => !!token.value && !!user.value)

  /**
   * Get authorization header for API calls
   */
  function getAuthHeader() {
    return token.value ? { 'Authorization': `Bearer ${token.value}` } : {}
  }

  /**
   * Check if user has a specific role
   */
  function hasRole(role) {
    if (!user.value) return false
    const userRoles = Array.isArray(user.value.roles) ? user.value.roles : [user.value.role]
    return userRoles.includes(role)
  }

  // ============= ACTIONS =============

  /**
   * Load user profile from backend
   * Called on app initialization
   */
  async function loadUser() {
    if (!token.value) return false

    isLoading.value = true
    error.value = null

    try {
      const response = await fetch('/api/auth/profile', {
        headers: getAuthHeader(),
      })

      if (response.ok) {
        user.value = await response.json()
        return true
      } else if (response.status === 401) {
        // Token invalid
        logout()
        return false
      }
    } catch (err) {
      console.error('[Auth] Profile load failed:', err)
      error.value = err.message
      return false
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Login with email and password
   * @param {string} email User email
   * @param {string} password User password
   * @returns {boolean} Success status
   */
  async function login(email, password) {
    isLoading.value = true
    error.value = null

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })

      const data = await response.json()

      if (!response.ok) {
        error.value = data.error || 'Login failed'
        return false
      }

      // Store token and user
      token.value = data.token
      user.value = data.user

      // Persist via auth.storage (sessionStorage, clears old localStorage)
      saveAuthSession(token.value, user.value)

      console.log('[Auth] Login successful:', user.value.email)
      return true
    } catch (err) {
      console.error('[Auth] Login failed:', err)
      error.value = err.message
      return false
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Register new user
   * @param {string} username Username
   * @param {string} email Email address
   * @param {string} password Password
   * @returns {boolean} Success status
   */
  async function register(username, email, password) {
    isLoading.value = true
    error.value = null

    try {
      const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password }),
      })

      const data = await response.json()

      if (!response.ok) {
        error.value = data.error || 'Registration failed'
        return false
      }

      // Auto login after register
      token.value = data.token
      user.value = data.user
      saveAuthSession(token.value, user.value)

      console.log('[Auth] Registration successful')
      return true
    } catch (err) {
      console.error('[Auth] Registration failed:', err)
      error.value = err.message
      return false
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Logout and clear auth state
   */
  function logout() {
    token.value = ''
    user.value = null
    error.value = null

    // Delegate to auth.storage (clears sessionStorage + any legacy localStorage)
    clearAuthSession()

    console.log('[Auth] Logged out')
  }

  /**
   * Request password reset
   * @param {string} email Email address
   */
  async function requestPasswordReset(email) {
    isLoading.value = true
    error.value = null

    try {
      const response = await fetch('/api/auth/forgot-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      })

      const data = await response.json()

      if (!response.ok) {
        error.value = data.error || 'Request failed'
        return false
      }

      console.log('[Auth] Password reset link sent')
      return true
    } catch (err) {
      console.error('[Auth] Password reset request failed:', err)
      error.value = err.message
      return false
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Reset password with token
   * @param {string} token Reset token
   * @param {string} newPassword New password
   */
  async function resetPassword(resetToken, newPassword) {
    isLoading.value = true
    error.value = null

    try {
      const response = await fetch('/api/auth/reset-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: resetToken, password: newPassword }),
      })

      const data = await response.json()

      if (!response.ok) {
        error.value = data.error || 'Password reset failed'
        return false
      }

      // Logout user after password reset
      logout()

      console.log('[Auth] Password reset successful')
      return true
    } catch (err) {
      console.error('[Auth] Password reset failed:', err)
      error.value = err.message
      return false
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Refresh access token
   */
  async function refreshToken() {
    try {
      const response = await fetch('/api/auth/refresh-token', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
      })

      if (!response.ok) {
        logout()
        return false
      }

      const data = await response.json()
      token.value = data.access_token
      saveAuthSession(token.value, user.value)

      console.log('[Auth] Token refreshed')
      return true
    } catch (err) {
      console.error('[Auth] Token refresh failed:', err)
      logout()
      return false
    }
  }

  return {
    // State
    token,
    user,
    isLoading,
    error,

    // Computed
    isAuthenticated,

    // Actions
    getAuthHeader,
    hasRole,
    loadUser,
    login,
    register,
    logout,
    requestPasswordReset,
    resetPassword,
    refreshToken,
  }
})
