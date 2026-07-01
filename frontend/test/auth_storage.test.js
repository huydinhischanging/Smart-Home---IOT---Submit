import test from 'node:test'
import assert from 'node:assert/strict'

// Provide a minimal sessionStorage / localStorage stub so the module works
// outside a browser.
function makeStore() {
  const data = {}
  return {
    getItem: (k) => (Object.prototype.hasOwnProperty.call(data, k) ? data[k] : null),
    setItem: (k, v) => { data[k] = String(v) },
    removeItem: (k) => { delete data[k] },
    clear: () => { Object.keys(data).forEach((k) => delete data[k]) },
  }
}

function withFakeBrowser(fn) {
  const sessionStore = makeStore()
  const localStore = makeStore()

  globalThis.window = {
    sessionStorage: sessionStore,
    localStorage: localStore,
  }

  try {
    return fn(sessionStore, localStore)
  } finally {
    delete globalThis.window
  }
}

// Re-import the module fresh in each test by clearing the module cache.
async function loadModule() {
  // Node's ESM cache cannot be busted without worker threads, so we exercise
  // the exported functions directly via dynamic import with a cache-bust query.
  const { default: mod } = await import(
    '../src/services/auth.storage.js?' + Date.now()
  ).catch(() => null) || {}

  if (mod) return mod

  // Fallback: return a plain import (first run).
  return import('../src/services/auth.storage.js')
}

test('saveAuthSession stores user JSON; getAuthUser returns it', async () => {
  const sessionStore = makeStore()
  const localStore = makeStore()
  globalThis.window = { sessionStorage: sessionStore, localStorage: localStore }

  const { saveAuthSession, getAuthUser, clearAuthSession } = await import(
    '../src/services/auth.storage.js'
  )

  const user = { id: 1, username: 'alice', email: 'alice@test.com' }
  saveAuthSession('tok123', user)

  const returned = getAuthUser()
  assert.equal(returned?.username, 'alice')
  assert.equal(returned?.email, 'alice@test.com')

  clearAuthSession()
  assert.equal(getAuthUser(), null)

  delete globalThis.window
})

test('clearAuthSession removes user from sessionStorage and localStorage', async () => {
  const sessionStore = makeStore()
  const localStore = makeStore()
  globalThis.window = { sessionStorage: sessionStore, localStorage: localStore }

  const { saveAuthSession, clearAuthSession, getAuthUser } = await import(
    '../src/services/auth.storage.js'
  )

  saveAuthSession('t', { id: 2, username: 'bob' })
  clearAuthSession()

  assert.equal(getAuthUser(), null)
  assert.equal(sessionStore.getItem('batman_os_user'), null)
  assert.equal(localStore.getItem('batman_os_user'), null)

  delete globalThis.window
})

test('getAuthUser returns null when storage is unavailable', async () => {
  // No globalThis.window — sessionStorage will throw.
  delete globalThis.window

  const { getAuthUser } = await import('../src/services/auth.storage.js')
  // Should return null gracefully, not throw.
  assert.equal(getAuthUser(), null)
})
