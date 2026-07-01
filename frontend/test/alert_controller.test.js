import test from 'node:test'
import assert from 'node:assert/strict'
import { JSDOM } from 'jsdom'

// ── helpers ─────────────────────────────────────────────────────────────────

function makeAlertItem(overrides = {}) {
  return {
    id: 1,
    device_code: 'den',
    message: 'Device turned on',
    level: 'info',
    is_read: false,
    created_at: '2026-04-16T10:00:00',
    ...overrides,
  }
}

/**
 * Create an AlertController-like class that mirrors the real implementation
 * but accepts injected dependencies (alertApi, renderAlertItem, themeManager)
 * so we can test it without a real DOM or real API.
 */
function makeController({ doc, alertApi, renderItem, themeManager }) {
  // Mirrors src/modules/alert/alert.controller.js logic
  const listElement = doc.getElementById('alert-list')

  return {
    listElement,

    async init() {
      try {
        const res = await alertApi.getAlerts()
        const alerts = res.data || res
        this.render(alerts)
        this._bindMarkRead()
      } catch (e) {
        // silently fail — mirrors original behaviour
      }
    },

    onNewAlert(data) {
      if (!this.listElement) return
      if ((data.level || '').toLowerCase() === 'critical') {
        themeManager.apply('emergency')
      }
      const html = renderItem(data)
      this.listElement.insertAdjacentHTML('afterbegin', html)
      this._bindMarkRead()
    },

    render(alerts) {
      if (!this.listElement) return
      this.listElement.innerHTML = alerts.map(renderItem).join('')
    },

    async markRead(alertId, element) {
      try {
        await alertApi.markRead(alertId)
        element.classList.add('is-read')
      } catch (e) {
        // silently fail
      }
    },

    _bindMarkRead() {
      if (!this.listElement) return
      this.listElement
        .querySelectorAll('.alert-item[data-id]:not([data-bound])')
        .forEach(el => {
          el.setAttribute('data-bound', '1')
          el.style.cursor = 'pointer'
          el.addEventListener('click', () => {
            const id = el.getAttribute('data-id')
            if (id) this.markRead(Number(id), el)
          })
        })
    },
  }
}

function makeDoc(extraHtml = '') {
  const dom = new JSDOM(`<!doctype html><body>
    <ul id="alert-list">${extraHtml}</ul>
  </body>`)
  return dom.window.document
}

function makeRender() {
  return (item) =>
    `<li class="alert-item" data-id="${item.id}">${item.message}</li>`
}

// ── tests ────────────────────────────────────────────────────────────────────

test('AlertController.render fills list with alert items', async () => {
  const doc = makeDoc()
  const alerts = [makeAlertItem({ id: 1, message: 'Alert A' }), makeAlertItem({ id: 2, message: 'Alert B' })]
  const ctrl = makeController({
    doc,
    alertApi: { getAlerts: async () => alerts, markRead: async () => {} },
    renderItem: makeRender(),
    themeManager: { apply: () => {} },
  })

  ctrl.render(alerts)

  const list = doc.getElementById('alert-list')
  assert.equal(list.querySelectorAll('.alert-item').length, 2)
  assert.ok(list.innerHTML.includes('Alert A'))
  assert.ok(list.innerHTML.includes('Alert B'))
})

test('AlertController.init fetches and renders alerts from api', async () => {
  const doc = makeDoc()
  const alerts = [makeAlertItem({ id: 10, message: 'Fetched alert' })]
  let called = false

  const ctrl = makeController({
    doc,
    alertApi: {
      getAlerts: async () => { called = true; return alerts },
      markRead: async () => {},
    },
    renderItem: makeRender(),
    themeManager: { apply: () => {} },
  })

  await ctrl.init()

  assert.ok(called, 'getAlerts should be called')
  assert.ok(doc.getElementById('alert-list').innerHTML.includes('Fetched alert'))
})

test('AlertController.init handles api error gracefully without throwing', async () => {
  const doc = makeDoc()
  const ctrl = makeController({
    doc,
    alertApi: { getAlerts: async () => { throw new Error('network error') }, markRead: async () => {} },
    renderItem: makeRender(),
    themeManager: { apply: () => {} },
  })

  // Must not throw
  await assert.doesNotReject(() => ctrl.init())
})

test('AlertController.onNewAlert prepends new alert to list', async () => {
  const doc = makeDoc('<li class="alert-item" data-id="1">Old</li>')
  const ctrl = makeController({
    doc,
    alertApi: { getAlerts: async () => [], markRead: async () => {} },
    renderItem: makeRender(),
    themeManager: { apply: () => {} },
  })

  ctrl.onNewAlert(makeAlertItem({ id: 99, message: 'New alert' }))

  const items = doc.getElementById('alert-list').querySelectorAll('.alert-item')
  assert.equal(items[0].getAttribute('data-id'), '99')
  assert.equal(items[1].getAttribute('data-id'), '1')
})

test('AlertController.onNewAlert applies emergency theme on critical level', async () => {
  const doc = makeDoc()
  const applied = []
  const ctrl = makeController({
    doc,
    alertApi: { getAlerts: async () => [], markRead: async () => {} },
    renderItem: makeRender(),
    themeManager: { apply: (t) => applied.push(t) },
  })

  ctrl.onNewAlert(makeAlertItem({ id: 5, level: 'critical', message: 'CRITICAL' }))

  assert.deepEqual(applied, ['emergency'])
})

test('AlertController.onNewAlert does NOT apply theme for info level', async () => {
  const doc = makeDoc()
  const applied = []
  const ctrl = makeController({
    doc,
    alertApi: { getAlerts: async () => [], markRead: async () => {} },
    renderItem: makeRender(),
    themeManager: { apply: (t) => applied.push(t) },
  })

  ctrl.onNewAlert(makeAlertItem({ id: 6, level: 'info', message: 'INFO' }))

  assert.equal(applied.length, 0)
})

test('AlertController.markRead calls api and adds is-read class', async () => {
  const doc = makeDoc('<li class="alert-item" data-id="7">Read me</li>')
  const markedIds = []
  const ctrl = makeController({
    doc,
    alertApi: { getAlerts: async () => [], markRead: async (id) => { markedIds.push(id) } },
    renderItem: makeRender(),
    themeManager: { apply: () => {} },
  })

  const el = doc.querySelector('.alert-item')
  await ctrl.markRead(7, el)

  assert.deepEqual(markedIds, [7])
  assert.ok(el.classList.contains('is-read'))
})

test('AlertController.markRead handles api error without throwing', async () => {
  const doc = makeDoc('<li class="alert-item" data-id="8">Item</li>')
  const ctrl = makeController({
    doc,
    alertApi: { getAlerts: async () => [], markRead: async () => { throw new Error('fail') } },
    renderItem: makeRender(),
    themeManager: { apply: () => {} },
  })

  const el = doc.querySelector('.alert-item')
  await assert.doesNotReject(() => ctrl.markRead(8, el))
  assert.ok(!el.classList.contains('is-read'))
})

test('AlertController._bindMarkRead attaches click listener once (data-bound guard)', async () => {
  const doc = makeDoc()
  const markedIds = []
  const ctrl = makeController({
    doc,
    alertApi: { getAlerts: async () => [], markRead: async (id) => { markedIds.push(id) } },
    renderItem: makeRender(),
    themeManager: { apply: () => {} },
  })

  ctrl.onNewAlert(makeAlertItem({ id: 20, message: 'Bindable' }))
  // Call bind again — should not double-bind
  ctrl._bindMarkRead()

  const item = doc.querySelector('.alert-item[data-id="20"]')
  assert.equal(item.getAttribute('data-bound'), '1')
})

test('AlertController renders nothing when listElement is missing', () => {
  const dom = new JSDOM('<!doctype html><body></body>')
  const doc = dom.window.document
  const ctrl = makeController({
    doc,
    alertApi: { getAlerts: async () => [], markRead: async () => {} },
    renderItem: makeRender(),
    themeManager: { apply: () => {} },
  })

  // All methods should be safe to call without a list element
  assert.doesNotThrow(() => ctrl.render([makeAlertItem()]))
  assert.doesNotThrow(() => ctrl.onNewAlert(makeAlertItem()))
  assert.doesNotThrow(() => ctrl._bindMarkRead())
})
