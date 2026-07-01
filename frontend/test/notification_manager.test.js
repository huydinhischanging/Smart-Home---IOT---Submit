import test from 'node:test'
import assert from 'node:assert/strict'
import { JSDOM } from 'jsdom'

// ── helper: creates a JSDOM window with the NotificationManager logic wired in ──

function makeManager(doc) {
  // Mirrors src/modules/alert/notification.manager.js logic
  return {
    _drawer: null,

    notify(title, message, type = 'info') {
      const drawer = doc.getElementById('notification-drawer') || this._createDrawer(doc)
      const icon = type === 'critical' ? '🚨' : '🤖'
      const html = `<div class="bat-toast ${type}"><div class="toast-content"><b>${icon} ${title}</b><p>${message}</p></div></div>`
      drawer.insertAdjacentHTML('afterbegin', html)
    },

    _createDrawer(document) {
      const div = document.createElement('div')
      div.id = 'notification-drawer'
      div.className = 'toast-container'
      document.body.appendChild(div)
      this._drawer = div
      return div
    },
  }
}

// ── tests ────────────────────────────────────────────────────────────────────

test('NotificationManager.notify creates drawer when none exists', () => {
  const { window } = new JSDOM('<!doctype html><body></body>')
  const doc = window.document
  const mgr = makeManager(doc)

  assert.equal(doc.getElementById('notification-drawer'), null)

  mgr.notify('Test', 'Hello')

  assert.notEqual(doc.getElementById('notification-drawer'), null)
})

test('NotificationManager.notify inserts toast into drawer', () => {
  const { window } = new JSDOM('<!doctype html><body></body>')
  const doc = window.document
  const mgr = makeManager(doc)

  mgr.notify('Title', 'Body text', 'info')

  const drawer = doc.getElementById('notification-drawer')
  const toast = drawer.querySelector('.bat-toast')
  assert.notEqual(toast, null)
  assert.ok(toast.classList.contains('info'))
  assert.ok(drawer.innerHTML.includes('Title'))
  assert.ok(drawer.innerHTML.includes('Body text'))
})

test('NotificationManager.notify uses 🚨 icon for critical type', () => {
  const { window } = new JSDOM('<!doctype html><body></body>')
  const doc = window.document
  const mgr = makeManager(doc)

  mgr.notify('EMERGENCY', 'Critical alert', 'critical')

  const drawer = doc.getElementById('notification-drawer')
  assert.ok(drawer.innerHTML.includes('🚨'))
  assert.ok(drawer.querySelector('.bat-toast.critical') !== null)
})

test('NotificationManager.notify uses 🤖 icon for non-critical type', () => {
  const { window } = new JSDOM('<!doctype html><body></body>')
  const doc = window.document
  const mgr = makeManager(doc)

  mgr.notify('Info', 'Everything OK', 'info')

  const drawer = doc.getElementById('notification-drawer')
  assert.ok(drawer.innerHTML.includes('🤖'))
})

test('NotificationManager.notify prepends most recent toast first', () => {
  const { window } = new JSDOM('<!doctype html><body></body>')
  const doc = window.document
  const mgr = makeManager(doc)

  mgr.notify('First', 'msg1')
  mgr.notify('Second', 'msg2')

  const drawer = doc.getElementById('notification-drawer')
  const toasts = drawer.querySelectorAll('.bat-toast')
  assert.equal(toasts.length, 2)
  // Second toast was inserted afterbegin so it comes first in DOM
  assert.ok(toasts[0].innerHTML.includes('Second'))
  assert.ok(toasts[1].innerHTML.includes('First'))
})

test('NotificationManager.notify reuses existing drawer element', () => {
  const { window } = new JSDOM(`<!doctype html><body>
    <div id="notification-drawer" class="toast-container"></div>
  </body>`)
  const doc = window.document
  const mgr = makeManager(doc)

  mgr.notify('Reuse', 'Test reuse')

  // Should not create a second drawer
  const drawers = doc.querySelectorAll('#notification-drawer')
  assert.equal(drawers.length, 1)
  assert.ok(drawers[0].innerHTML.includes('Reuse'))
})

test('NotificationManager.notify handles empty title and message', () => {
  const { window } = new JSDOM('<!doctype html><body></body>')
  const doc = window.document
  const mgr = makeManager(doc)

  assert.doesNotThrow(() => mgr.notify('', ''))

  const drawer = doc.getElementById('notification-drawer')
  assert.notEqual(drawer, null)
})
