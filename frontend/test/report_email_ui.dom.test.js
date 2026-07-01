import test from 'node:test'
import assert from 'node:assert/strict'
import { JSDOM } from 'jsdom'

import { createReportEmailController } from '../src/services/report_email_ui.js'

function createDom() {
  const dom = new JSDOM(`<!doctype html><body>
    <button id="report-email-btn">EMAIL REPORT</button>
    <button id="profile-report-email-btn">EMAIL PROFILE REPORT</button>
    <div id="report-email-status"></div>
    <div id="profile-report-status"></div>
    <div id="report-account-email"></div>
    <div id="profile-report-email"></div>
  </body>`)
  return dom.window.document
}

test('report email controller syncs notification email and sends email on button click', async () => {
  const document = createDom()
  const alerts = []
  const fetchCalls = []
  const user = { email: 'demo@example.com' }

  const controller = createReportEmailController({
    document,
    apiBaseUrl: '/api',
    getToken: () => 'token',
    getUser: () => user,
    authHeaders: () => ({ Authorization: 'Bearer token' }),
    fetchImpl: async (url, options) => {
      fetchCalls.push({ url, options })
      return {
        ok: true,
        json: async () => ({
          delivery: { recipients: ['demo@example.com'] },
        }),
      }
    },
    showAlert: (message, tone) => alerts.push({ message, tone }),
  })

  controller.bindButtons()
  controller.sync()

  assert.equal(
    document.getElementById('report-account-email').textContent,
    'demo@example.com',
  )
  assert.equal(
    document.getElementById('report-email-status').textContent,
    'Ready to email the latest report to demo@example.com',
  )

  document.getElementById('report-email-btn').click()
  await new Promise((resolve) => setTimeout(resolve, 0))

  assert.equal(fetchCalls.length, 1)
  assert.equal(fetchCalls[0].url, '/api/patient/report/email')
  assert.equal(fetchCalls[0].options.method, 'POST')
  assert.equal(fetchCalls[0].options.body, '{}')
  assert.equal(
    document.getElementById('report-email-status').textContent,
    '✅ Report emailed to demo@example.com',
  )
  assert.deepEqual(alerts, [
    { message: '✅ Patient report emailed to demo@example.com', tone: 'info' },
  ])
  assert.equal(document.getElementById('report-email-btn').disabled, false)
})

test('report email controller falls back to authenticated email when backend omits recipients', async () => {
  const document = createDom()

  const controller = createReportEmailController({
    document,
    apiBaseUrl: '/api',
    getToken: () => 'token',
    getUser: () => ({ email: 'fallback@example.com' }),
    authHeaders: () => ({ Authorization: 'Bearer token' }),
    fetchImpl: async () => ({
      ok: true,
      json: async () => ({ status: 'success' }),
    }),
  })

  await controller.emailPatientReport()

  assert.equal(
    document.getElementById('report-email-status').textContent,
    '✅ Report emailed to fallback@example.com',
  )
})