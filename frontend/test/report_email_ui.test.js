import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createReportEmailController,
  getReportDeliveryState,
  getReportEmailRecipients,
  getReportEmailErrorMessage,
} from '../src/services/report_email_ui.js'

test('getReportDeliveryState returns signed-out prompt when no session exists', () => {
  assert.deepEqual(getReportDeliveryState({ token: '', user: null }), {
    hasSession: false,
    email: 'Sign in to sync your notification email',
    disabled: true,
    statusMessage: 'Sign in to send reports to your notification email.',
    statusTone: 'idle',
  })
})

test('getReportDeliveryState uses notification email when session exists', () => {
  assert.deepEqual(
    getReportDeliveryState({ token: 'token', user: { email: 'demo@example.com' } }),
    {
      hasSession: true,
      email: 'demo@example.com',
      disabled: false,
      statusMessage: 'Ready to email the latest report to demo@example.com',
      statusTone: 'idle',
    },
  )
})

test('getReportEmailRecipients prefers backend delivery recipients', () => {
  assert.equal(
    getReportEmailRecipients(
      { delivery: { recipients: ['one@example.com', 'two@example.com'] } },
      { email: 'fallback@example.com' },
    ),
    'one@example.com, two@example.com',
  )
})

test('getReportEmailRecipients falls back to authenticated user email', () => {
  assert.equal(
    getReportEmailRecipients({}, { email: 'fallback@example.com' }),
    'fallback@example.com',
  )
})

test('getReportEmailErrorMessage resolves message, error, and default fallback', () => {
  assert.equal(getReportEmailErrorMessage({ message: 'Unavailable' }), 'Unavailable')
  assert.equal(getReportEmailErrorMessage({ error: 'Failed' }), 'Failed')
  assert.equal(getReportEmailErrorMessage({}), 'Email send failed')
})

test('createReportEmailController returns not-logged-in status without calling fetch', async () => {
  let fetchCalled = false
  const document = {
    getElementById(id) {
      if (id === 'report-email-status' || id === 'profile-report-status') {
        return { textContent: '', className: '' }
      }
      if (id === 'report-email-btn' || id === 'profile-report-email-btn') {
        return { disabled: false }
      }
      return null
    },
  }

  const controller = createReportEmailController({
    document,
    apiBaseUrl: '/api',
    getToken: () => '',
    getUser: () => null,
    authHeaders: () => ({ Authorization: 'Bearer token' }),
    fetchImpl: async () => {
      fetchCalled = true
      throw new Error('fetch should not run')
    },
  })

  const result = await controller.emailPatientReport()
  assert.equal(result.ok, false)
  assert.equal(result.reason, 'not-logged-in')
  assert.equal(fetchCalled, false)
})