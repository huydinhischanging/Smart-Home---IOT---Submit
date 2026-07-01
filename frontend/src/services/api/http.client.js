// ==========================================================
// HTTP CLIENT – PRO VERSION (FIX 204 + THROW ERRORS)
// ==========================================================

const BASE_URL = import.meta.env.VITE_BASE_URL || ''
import { getBearerAuthToken } from '../auth.storage.js'


// ==========================================================
// CORE REQUEST
// ==========================================================
async function request(url, options = {}) {
  const bearerToken = getBearerAuthToken()

  try {

    const res = await fetch(`${BASE_URL}${url}`, {

      method: options.method || 'GET',
      credentials: 'include',

      headers: {
        'Content-Type': 'application/json',
        ...(bearerToken
          ? { 'Authorization': 'Bearer ' + bearerToken }
          : {}),
        ...(options.headers || {})
      },

      body: options.body || null

    })

    // 🔥 HANDLE 204 NO CONTENT (DELETE chuẩn REST)
    if (res.status === 204) {
      return null
    }

    const contentType = res.headers.get('content-type')
    let data = null

    if (contentType && contentType.includes('application/json')) {
      data = await res.json()
    } else {
      data = await res.text()
    }

    // 🔥 THROW ERROR THAY VÌ RETURN NULL
    if (!res.ok) {

      const error = new Error(
        data?.message || `HTTP Error ${res.status}`
      )

      error.status = res.status
      error.data = data

      throw error
    }

    return data

  }
  catch (err) {

    console.error('[HTTP EXCEPTION]', err)

    // 🔥 KHÔNG NUỐT LỖI
    throw err
  }
}


// ==========================================================
// EXPORT CLIENT
// ==========================================================
export const HttpClient = {

  get: (url) =>
    request(url, {
      method: 'GET'
    }),

  post: (url, body) =>
    request(url, {
      method: 'POST',
      body: JSON.stringify(body)
    }),

  delete: (url) =>
    request(url, {
      method: 'DELETE'
    }),

  patch: (url, body) =>
    request(url, {
      method: 'PATCH',
      body: JSON.stringify(body)
    })

}

// 🔥 OPTIONAL: nếu ai import default
export default HttpClient