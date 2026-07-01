import test from 'node:test'
import assert from 'node:assert/strict'

// ── ApiClient logic extracted for testability ────────────────────────────────
// Mirrors src/services/api_client.js but accepts injectable fetch + baseUrl.

function makeApiClient({ baseUrl = 'http://127.0.0.1:5000', fetchFn, getToken = () => '' } = {}) {
  async function apiFetch(path, options = {}) {
    const bearerToken = getToken()
    const res = await fetchFn(`${baseUrl}${path}`, {
      ...options,
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...(bearerToken ? { 'Authorization': 'Bearer ' + bearerToken } : {}),
        ...(options.headers || {}),
      },
    })
    if (!res.ok) return null
    return res.json()
  }

  return {
    async getDevices()          { const d = await apiFetch('/api/devices');          return d?.devices || [] },
    async getDeviceStatus()     { return apiFetch('/api/device-status') },
    async getBrokerConfig()     { return apiFetch('/api/broker-config') },
    async saveBrokerConfig(cfg) {
      return apiFetch('/api/broker-config', { method: 'POST', body: JSON.stringify(cfg) })
    },
    async createDevice(data) {
      return apiFetch('/api/devices', { method: 'POST', body: JSON.stringify(data) })
    },
    async deleteDevice(name) {
      return apiFetch(`/api/devices/${encodeURIComponent(name)}`, { method: 'DELETE' })
    },
    async sendControl(name, action) {
      return apiFetch('/api/devices/control', { method: 'POST', body: JSON.stringify({ device_name: name, action }) })
    },
  }
}

// ── stub helpers ─────────────────────────────────────────────────────────────

function okFetch(body) {
  return async (url, opts) => ({
    ok: true,
    _url: url,
    _opts: opts,
    json: async () => body,
  })
}

function failFetch() {
  return async () => ({ ok: false, json: async () => ({}) })
}

let _lastRequest = null
function recordingFetch(body) {
  return async (url, opts) => {
    _lastRequest = { url, opts }
    return { ok: true, json: async () => body }
  }
}

// ── tests ─────────────────────────────────────────────────────────────────────

test('ApiClient.getDevices returns devices array from response', async () => {
  const client = makeApiClient({ fetchFn: okFetch({ devices: [{ id: 1, name: 'den' }] }) })
  const devices = await client.getDevices()
  assert.deepEqual(devices, [{ id: 1, name: 'den' }])
})

test('ApiClient.getDevices returns empty array when response has no devices key', async () => {
  const client = makeApiClient({ fetchFn: okFetch({}) })
  const devices = await client.getDevices()
  assert.deepEqual(devices, [])
})

test('ApiClient.getDevices returns empty array on HTTP error', async () => {
  const client = makeApiClient({ fetchFn: failFetch() })
  const devices = await client.getDevices()
  assert.deepEqual(devices, [])
})

test('ApiClient.getDeviceStatus returns response body directly', async () => {
  const body = { den: true, quat: false }
  const client = makeApiClient({ fetchFn: okFetch(body) })
  const result = await client.getDeviceStatus()
  assert.deepEqual(result, body)
})

test('ApiClient.getBrokerConfig returns null on HTTP error', async () => {
  const client = makeApiClient({ fetchFn: failFetch() })
  const result = await client.getBrokerConfig()
  assert.equal(result, null)
})

test('ApiClient.saveBrokerConfig sends POST with JSON body', async () => {
  const client = makeApiClient({ fetchFn: recordingFetch({ ok: true }) })
  await client.saveBrokerConfig({ host: 'broker.example.com', port: 8883 })

  assert.ok(_lastRequest.url.includes('/api/broker-config'))
  assert.equal(_lastRequest.opts.method, 'POST')
  assert.deepEqual(
    JSON.parse(_lastRequest.opts.body),
    { host: 'broker.example.com', port: 8883 }
  )
})

test('ApiClient.createDevice sends POST with device data', async () => {
  const client = makeApiClient({ fetchFn: recordingFetch({ id: 5 }) })
  await client.createDevice({ name: 'new-device', code: 'nd01' })

  assert.ok(_lastRequest.url.includes('/api/devices'))
  assert.equal(_lastRequest.opts.method, 'POST')
  assert.deepEqual(JSON.parse(_lastRequest.opts.body), { name: 'new-device', code: 'nd01' })
})

test('ApiClient.deleteDevice encodes device name in URL', async () => {
  const client = makeApiClient({ fetchFn: recordingFetch({}) })
  await client.deleteDevice('đèn chính')

  assert.ok(_lastRequest.url.includes(encodeURIComponent('đèn chính')))
  assert.equal(_lastRequest.opts.method, 'DELETE')
})

test('ApiClient.sendControl sends device name and action', async () => {
  const client = makeApiClient({ fetchFn: recordingFetch({ status: 'ok' }) })
  await client.sendControl('quat', 'ON')

  assert.ok(_lastRequest.url.includes('/api/devices/control'))
  assert.equal(_lastRequest.opts.method, 'POST')
  assert.deepEqual(JSON.parse(_lastRequest.opts.body), { device_name: 'quat', action: 'ON' })
})

test('ApiClient attaches Authorization header when bearer token present', async () => {
  const client = makeApiClient({
    fetchFn: recordingFetch({}),
    getToken: () => 'test-jwt-token',
  })
  await client.getBrokerConfig()

  assert.equal(_lastRequest.opts.headers['Authorization'], 'Bearer test-jwt-token')
})

test('ApiClient omits Authorization header when no token', async () => {
  const client = makeApiClient({
    fetchFn: recordingFetch({}),
    getToken: () => '',
  })
  await client.getBrokerConfig()

  assert.equal(_lastRequest.opts.headers['Authorization'], undefined)
})

test('ApiClient uses provided baseUrl in all requests', async () => {
  const client = makeApiClient({
    baseUrl: 'https://api.example.com',
    fetchFn: recordingFetch({}),
  })
  await client.getDeviceStatus()

  assert.ok(_lastRequest.url.startsWith('https://api.example.com'))
})
