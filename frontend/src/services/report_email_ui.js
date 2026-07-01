export function getReportDeliveryState({ token, user }) {
  const hasSession = !!token && !!user
  const email = user?.email || 'Sign in to sync your notification email'

  return {
    hasSession,
    email,
    disabled: !hasSession,
    statusMessage: hasSession
      ? `Ready to email the latest report to ${email}`
      : 'Sign in to send reports to your notification email.',
    statusTone: 'idle',
  }
}

export function getReportEmailRecipients(data, user) {
  const recipients = data?.delivery?.recipients
  if (Array.isArray(recipients) && recipients.length > 0) {
    return recipients.join(', ')
  }

  return user?.email || 'your notification email'
}

export function getReportEmailErrorMessage(data) {
  return data?.message || data?.error || 'Email send failed'
}

export function setReportEmailStatus(document, message = '', tone = 'idle') {
  const targets = [
    document.getElementById('report-email-status'),
    document.getElementById('profile-report-status'),
  ]

  targets.forEach((el) => {
    if (!el) return
    el.textContent = message
    el.className =
      'report-email-status' + (tone && tone !== 'idle' ? ' ' + tone : '')
  })
}

export function setReportEmailBusy(document, busy, token, user) {
  const disabled = busy || !token || !user
  ;[
    document.getElementById('report-email-btn'),
    document.getElementById('profile-report-email-btn'),
  ].forEach((btn) => {
    if (!btn) return
    btn.disabled = disabled
  })
}

export function syncReportDeliveryUI(document, token, user) {
  const reportDeliveryState = getReportDeliveryState({ token, user })
  ;[
    document.getElementById('report-account-email'),
    document.getElementById('profile-report-email'),
  ].forEach((el) => {
    if (!el) return
    el.textContent = reportDeliveryState.email
  })

  setReportEmailStatus(
    document,
    reportDeliveryState.statusMessage,
    reportDeliveryState.statusTone,
  )
  setReportEmailBusy(document, false, token, user)
  return reportDeliveryState
}

export function createReportEmailController({
  document,
  apiBaseUrl,
  getToken,
  getUser,
  authHeaders,
  fetchImpl,
  showAlert,
}) {
  async function emailPatientReport() {
    const token = getToken()
    const user = getUser()

    if (!token) {
      setReportEmailStatus(document, '✗ Not logged in', 'error')
      return { ok: false, reason: 'not-logged-in' }
    }

    setReportEmailBusy(document, true, token, user)
    setReportEmailStatus(
      document,
      'Sending report to your notification email...',
      'pending',
    )

    try {
      const res = await fetchImpl(`${apiBaseUrl}/patient/report/email`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({}),
      })
      const data = await res.json().catch(() => ({}))

      if (!res.ok) {
        const errorMessage = getReportEmailErrorMessage(data)
        setReportEmailStatus(document, '✗ ' + errorMessage, 'error')
        return { ok: false, reason: 'request-failed', data }
      }

      const recipients = getReportEmailRecipients(data, getUser())
      setReportEmailStatus(document, '✅ Report emailed to ' + recipients, 'success')
      if (typeof showAlert === 'function') {
        showAlert('✅ Patient report emailed to ' + recipients, 'info')
      }
      return { ok: true, recipients, data }
    } catch {
      setReportEmailStatus(
        document,
        '✗ Network error while sending report email',
        'error',
      )
      return { ok: false, reason: 'network-error' }
    } finally {
      setReportEmailBusy(document, false, getToken(), getUser())
    }
  }

  function bindButtons() {
    ;['report-email-btn', 'profile-report-email-btn'].forEach((id) => {
      const button = document.getElementById(id)
      if (!button || button.dataset.reportEmailBound === 'true') return
      button.dataset.reportEmailBound = 'true'
      button.addEventListener('click', (event) => {
        event.preventDefault()
        void emailPatientReport()
      })
    })
  }

  function sync() {
    return syncReportDeliveryUI(document, getToken(), getUser())
  }

  return {
    bindButtons,
    sync,
    emailPatientReport,
  }
}

if (typeof window !== 'undefined') {
  window.ReportEmailUI = {
    getReportDeliveryState,
    getReportEmailRecipients,
    getReportEmailErrorMessage,
    setReportEmailStatus,
    setReportEmailBusy,
    syncReportDeliveryUI,
    createReportEmailController,
  }
}