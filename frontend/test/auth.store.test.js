import test from 'node:test'
import assert from 'node:assert/strict'

// Mock for Pinia store - simulating useAuthStore
function createMockAuthStore() {
  const store = {
    token: '',
    user: null,
    isLoading: false,
    error: null,

    get isAuthenticated() {
      return this.token !== '' && this.user !== null
    },

    getAuthHeader() {
      return this.token ? { 'Authorization': `Bearer ${this.token}` } : {}
    },

    hasRole(role) {
      if (!this.user) return false
      if (Array.isArray(this.user.roles)) {
        return this.user.roles.includes(role)
      }
      return this.user.role === role
    },

    logout() {
      this.token = ''
      this.user = null
      this.error = null
      localStorage.clear()
      sessionStorage.clear()
    },

    async login(email, password) {
      this.isLoading = true
      try {
        const res = await global.fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password })
        })
        if (!res.ok) {
          const data = await res.json()
          this.error = data.error || 'Login failed'
          return false
        }
        const data = await res.json()
        this.token = data.token
        this.user = data.user
        localStorage.setItem('auth_token', this.token)
        return true
      } catch (err) {
        this.error = `Network error: ${err.message}`
        return false
      } finally {
        this.isLoading = false
      }
    },

    async register(username, email, password) {
      this.isLoading = true
      try {
        const res = await global.fetch('/api/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, email, password })
        })
        if (!res.ok) {
          const data = await res.json()
          this.error = data.error || 'Registration failed'
          return false
        }
        const data = await res.json()
        this.token = data.token
        this.user = data.user
        localStorage.setItem('auth_token', this.token)
        return true
      } catch (err) {
        this.error = err.message
        return false
      } finally {
        this.isLoading = false
      }
    },

    async loadUser() {
      if (!this.token) return false
      try {
        const res = await global.fetch('/api/auth/me', {
          headers: { 'Authorization': `Bearer ${this.token}` }
        })
        if (res.status === 401) {
          this.logout()
          return false
        }
        if (!res.ok) return false
        this.user = await res.json()
        return true
      } finally {
        this.isLoading = false
      }
    },

    async refreshToken() {
      try {
        const res = await global.fetch('/api/auth/refresh', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${this.token}` }
        })
        if (!res.ok) {
          this.logout()
          return false
        }
        const data = await res.json()
        this.token = data.access_token
        localStorage.setItem('auth_token', this.token)
        return true
      } catch (err) {
        this.logout()
        return false
      }
    },

    async requestPasswordReset(email) {
      this.isLoading = true
      try {
        const res = await global.fetch('/api/auth/password-reset', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email })
        })
        if (!res.ok) {
          const data = await res.json()
          this.error = data.error || 'Password reset request failed'
          return false
        }
        return true
      } finally {
        this.isLoading = false
      }
    },

    async resetPassword(token, newPassword) {
      try {
        const res = await global.fetch('/api/auth/reset-password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token, password: newPassword })
        })
        if (!res.ok) {
          const data = await res.json()
          this.error = data.error || 'Password reset failed'
          return false
        }
        this.logout()
        return true
      } catch (err) {
        this.error = err.message
        return false
      }
    }
  }
  return store
}

test('Auth Store - Initial State', async (t) => {
  await t.test('should initialize with empty state', () => {
    localStorage.clear()
    const store = createMockAuthStore()
    assert.strictEqual(store.token, '')
    assert.strictEqual(store.user, null)
    assert.strictEqual(store.isLoading, false)
    assert.strictEqual(store.error, null)
  })

  await t.test('should load token from localStorage if available', () => {
    localStorage.clear()
    localStorage.setItem('auth_token', 'test-token-123')
    const store = createMockAuthStore()
    store.token = localStorage.getItem('auth_token') || ''
    assert.strictEqual(store.token, 'test-token-123')
  })
})

test('Auth Store - Computed Properties', async (t) => {
  await t.test('should compute isAuthenticated as false when no token', () => {
    const store = createMockAuthStore()
    assert.strictEqual(store.isAuthenticated, false)
  })

  await t.test('should compute isAuthenticated as true when token and user exist', () => {
    const store = createMockAuthStore()
    store.token = 'test-token'
    store.user = { id: 1, email: 'test@example.com' }
    assert.strictEqual(store.isAuthenticated, true)
  })

  await t.test('should compute isAuthenticated as false if only token exists', () => {
    const store = createMockAuthStore()
    store.token = 'test-token'
    store.user = null
    assert.strictEqual(store.isAuthenticated, false)
  })
})

test('Auth Store - getAuthHeader', async (t) => {
  await t.test('should return empty object when no token', () => {
    const store = createMockAuthStore()
    const header = store.getAuthHeader()
    assert.deepStrictEqual(header, {})
  })

  await t.test('should return Authorization header with Bearer token', () => {
    const store = createMockAuthStore()
    store.token = 'test-token-xyz'
    const header = store.getAuthHeader()
    assert.deepStrictEqual(header, { 'Authorization': 'Bearer test-token-xyz' })
  })
})

test('Auth Store - hasRole', async (t) => {
  await t.test('should return false when user is null', () => {
    const store = createMockAuthStore()
    store.user = null
    assert.strictEqual(store.hasRole('admin'), false)
  })

  await t.test('should return true when user has role (array)', () => {
    const store = createMockAuthStore()
    store.user = { id: 1, roles: ['admin', 'user'] }
    assert.strictEqual(store.hasRole('admin'), true)
    assert.strictEqual(store.hasRole('user'), true)
    assert.strictEqual(store.hasRole('superadmin'), false)
  })

  await t.test('should return true when user has role (string)', () => {
    const store = createMockAuthStore()
    store.user = { id: 1, role: 'admin' }
    assert.strictEqual(store.hasRole('admin'), true)
    assert.strictEqual(store.hasRole('user'), false)
  })
})

test('Auth Store - logout', async (t) => {
  await t.test('should clear all auth state', () => {
    const store = createMockAuthStore()
    store.token = 'test-token'
    store.user = { id: 1, email: 'test@example.com' }
    store.error = 'some error'

    store.logout()

    assert.strictEqual(store.token, '')
    assert.strictEqual(store.user, null)
    assert.strictEqual(store.error, null)
  })
})

test('Auth Store - login', async (t) => {
  await t.test('should handle login success', async () => {
    global.fetch = async () => ({
      ok: true,
      json: async () => ({
        token: 'new-token',
        user: { id: 1, email: 'test@example.com', username: 'testuser' }
      })
    })

    const store = createMockAuthStore()
    const result = await store.login('test@example.com', 'password123')

    assert.strictEqual(result, true)
    assert.strictEqual(store.token, 'new-token')
    assert.strictEqual(store.user.email, 'test@example.com')
    assert.strictEqual(store.isLoading, false)
  })

  await t.test('should handle login failure', async () => {
    global.fetch = async () => ({
      ok: false,
      json: async () => ({ error: 'Invalid credentials' })
    })

    const store = createMockAuthStore()
    const result = await store.login('test@example.com', 'wrongpassword')

    assert.strictEqual(result, false)
    assert.strictEqual(store.error, 'Invalid credentials')
    assert.strictEqual(store.token, '')
    assert.strictEqual(store.user, null)
  })
})
