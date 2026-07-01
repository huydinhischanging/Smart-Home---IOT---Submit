/**
 * ✅ SECURE: Authentication Storage Module
 * 
 * Security Practices:
 * 1. Uses sessionStorage as primary (cleared on tab close)
 * 2. Falls back to localStorage only if sessionStorage unavailable
 * 3. Stores minimal information (token + user profile)
 * 4. Supports CSRF token for state-changing operations
 * 
 * ⚠️  IMPORTANT: Tokens in JavaScript are XSS-vulnerable.
 * For production, configure backend to send tokens as HttpOnly, Secure cookies.
 */

const AUTH_TOKEN_KEY = 'batman_os_token'
const AUTH_USER_KEY = 'batman_os_user'
const AUTH_CSRF_KEY = 'batman_os_csrf'

let hasMigratedLegacyAuth = false

/**
 * Get sessionStorage if available
 * @returns {Storage|null}
 */
function getSessionStore() {
  try {
    return window.sessionStorage
  } catch (e) {
    console.warn('[Auth] sessionStorage not available:', e.message)
    return null
  }
}

/**
 * Get localStorage if available (fallback only)
 * @returns {Storage|null}
 */
function getLegacyStore() {
  try {
    return window.localStorage
  } catch (e) {
    console.warn('[Auth] localStorage not available:', e.message)
    return null
  }
}

/**
 * Migrate old localStorage tokens to sessionStorage
 */
function migrateLegacyAuth() {
  if (hasMigratedLegacyAuth) return
  hasMigratedLegacyAuth = true

  const sessionStore = getSessionStore()
  const legacyStore = getLegacyStore()
  if (!legacyStore) return

  const user = legacyStore.getItem(AUTH_USER_KEY)
  const csrf = legacyStore.getItem(AUTH_CSRF_KEY)
  const token = legacyStore.getItem(AUTH_TOKEN_KEY)

  // Migrate to sessionStorage if available
  if (sessionStore) {
    if (user) sessionStore.setItem(AUTH_USER_KEY, user)
    if (csrf) sessionStore.setItem(AUTH_CSRF_KEY, csrf)
    if (token) sessionStore.setItem(AUTH_TOKEN_KEY, token)
  }

  // ✅ Clear insecure localStorage (persistent storage of tokens is not recommended)
  console.warn('[Auth] Migrating tokens from localStorage to sessionStorage for better security')
  legacyStore.removeItem(AUTH_TOKEN_KEY)
  legacyStore.removeItem(AUTH_USER_KEY)
  legacyStore.removeItem(AUTH_CSRF_KEY)
}

/**
 * Get primary storage (sessionStorage preferred, localStorage fallback)
 * @returns {Storage|null}
 */
function getPrimaryStore() {
  migrateLegacyAuth()
  return getSessionStore() || getLegacyStore()
}

/**
 * Get authentication token for API requests
 * @returns {string} Bearer token or empty string
 */
export function getBearerAuthToken() {
  const store = getPrimaryStore()
  if (!store) return ''
  
  const token = store.getItem(AUTH_TOKEN_KEY)
  return token ? `Bearer ${token}` : ''
}

/**
 * Get raw token (without Bearer prefix)
 * @returns {string} Raw token or empty string
 */
export function getAuthToken() {
  const store = getPrimaryStore()
  if (!store) return ''
  return store.getItem(AUTH_TOKEN_KEY) || ''
}

/**
 * Get authenticated user profile
 * @returns {Object|null} User object {id, username, email, role} or null
 */
export function getAuthUser() {
  const store = getPrimaryStore()
  if (!store) return null

  const raw = store.getItem(AUTH_USER_KEY)
  if (!raw) return null

  try {
    return JSON.parse(raw)
  } catch (e) {
    console.error('[Auth] Failed to parse user data:', e)
    return null
  }
}

/**
 * Get CSRF token for state-changing operations (POST, PUT, DELETE)
 * @returns {string} CSRF token or empty string
 */
export function getCsrfToken() {
  const store = getPrimaryStore()
  if (!store) return ''
  return store.getItem(AUTH_CSRF_KEY) || ''
}

/**
 * Check if user is authenticated
 * @returns {boolean}
 */
export function isAuthenticated() {
  return !!getAuthToken() && !!getAuthUser()
}

/**
 * Save authentication session
 * @param {string} token - JWT/Bearer token from server
 * @param {Object} user - User profile object
 * @param {string} csrfToken - Optional CSRF token
 */
export function saveAuthSession(token, user, csrfToken = '') {
  const store = getPrimaryStore()
  if (!store) {
    console.error('[Auth] No storage available')
    return
  }

  // ✅ Clear previous session first
  store.removeItem(AUTH_TOKEN_KEY)
  store.removeItem(AUTH_USER_KEY)
  store.removeItem(AUTH_CSRF_KEY)

  // Save new session
  if (token) {
    store.setItem(AUTH_TOKEN_KEY, token)
  }
  if (user) {
    store.setItem(AUTH_USER_KEY, JSON.stringify(user))
  }
  if (csrfToken) {
    store.setItem(AUTH_CSRF_KEY, csrfToken)
  }

  // ✅ Ensure legacy storage is cleared
  const legacyStore = getLegacyStore()
  if (legacyStore && legacyStore !== store) {
    legacyStore.removeItem(AUTH_TOKEN_KEY)
    legacyStore.removeItem(AUTH_USER_KEY)
    legacyStore.removeItem(AUTH_CSRF_KEY)
  }
}

/**
 * Clear authentication session (on logout)
 */
export function clearAuthSession() {
  const sessionStore = getSessionStore()
  const legacyStore = getLegacyStore()

  // Clear from sessionStorage
  if (sessionStore) {
    sessionStore.removeItem(AUTH_TOKEN_KEY)
    sessionStore.removeItem(AUTH_USER_KEY)
    sessionStore.removeItem(AUTH_CSRF_KEY)
  }

  // Clear from localStorage (if being used)
  if (legacyStore && legacyStore !== sessionStore) {
    legacyStore.removeItem(AUTH_TOKEN_KEY)
    legacyStore.removeItem(AUTH_USER_KEY)
    legacyStore.removeItem(AUTH_CSRF_KEY)
  }

  console.log('[Auth] Session cleared')
}

/**
 * Get all auth headers for API requests
 * @returns {Object} Headers object with Authorization and X-CSRF-Token
 */
export function getAuthHeaders() {
  const headers = {}
  
  const bearerToken = getBearerAuthToken()
  if (bearerToken) {
    headers.Authorization = bearerToken
  }

  const csrfToken = getCsrfToken()
  if (csrfToken) {
    headers['X-CSRF-Token'] = csrfToken
  }

  return headers
}

/**
 * Debug helper: Log current auth state
 */
export function debugAuthState() {
  console.group('[Auth Debug]')
  console.log('Is Authenticated:', isAuthenticated())
  console.log('User:', getAuthUser())
  console.log('Token:', getAuthToken() ? '✓ Set' : '✗ Not set')
  console.log('CSRF:', getCsrfToken() ? '✓ Set' : '✗ Not set')
  console.log('Storage Type:', getSessionStore() ? 'sessionStorage' : 'localStorage')
  console.groupEnd()
}