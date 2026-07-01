/**
 * Test Setup - Node.js Test Runner Configuration with jsdom
 * Provides browser-like globals (localStorage, sessionStorage, document, window)
 */

import { JSDOM } from 'jsdom'

// Create a new JSDOM instance to simulate a browser environment
const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', {
  url: 'http://localhost:5173',
})

// Set up global objects that browser tests expect
globalThis.window = dom.window
globalThis.document = dom.window.document

// Mock localStorage with real in-memory implementation
class LocalStorageMock {
  constructor() {
    this.store = {}
  }

  clear() {
    this.store = {}
  }

  getItem(key) {
    return this.store[key] || null
  }

  setItem(key, value) {
    this.store[key] = String(value)
  }

  removeItem(key) {
    delete this.store[key]
  }

  key(index) {
    const keys = Object.keys(this.store)
    return keys[index] || null
  }

  get length() {
    return Object.keys(this.store).length
  }
}

class SessionStorageMock extends LocalStorageMock {}

// Install mocks on global (tests use globalThis.localStorage)
globalThis.localStorage = new LocalStorageMock()
globalThis.sessionStorage = new SessionStorageMock()

// Polyfill for fetch if needed (Node.js 18+ has it)
if (typeof globalThis.fetch === 'undefined') {
  globalThis.fetch = async () => ({ ok: false })
}
