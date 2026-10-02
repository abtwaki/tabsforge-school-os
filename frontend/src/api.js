const API_ROOT = '/api'

export const getToken = () => localStorage.getItem('tabsforge_token')

// Platform admins can scope every request to a specific school via the
// topbar context switcher — stored here and appended as ?school_id=.
export const getSchoolCtx = () => localStorage.getItem('tabsforge_school_ctx') || ''
export const setSchoolCtx = id =>
  id ? localStorage.setItem('tabsforge_school_ctx', id)
     : localStorage.removeItem('tabsforge_school_ctx')

function withCtx(path) {
  const ctx = getSchoolCtx()
  if (!ctx) return path
  return `${path}${path.includes('?') ? '&' : '?'}school_id=${encodeURIComponent(ctx)}`
}

export async function api(path, options = {}) {
  const token = getToken()
  const headers = { ...options.headers }
  if (token) headers.Authorization = `Token ${token}`
  if (options.body && !(options.body instanceof FormData)) headers['Content-Type'] = 'application/json'
  const response = await fetch(`${API_ROOT}${withCtx(path)}`, { ...options, headers })
  if (response.status === 401) {
    localStorage.removeItem('tabsforge_token')
    localStorage.removeItem('tabsforge_user')
    if (!location.pathname.startsWith('/login')) location.assign('/login')
  }
  if (response.status === 403) throw new Error('You do not have permission to perform this action.')
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(extractError(data, response.status))
  }
  if (response.status === 204) return null
  return response.json()
}

/** Turn a DRF error body into a readable, actionable message. */
function extractError(data, status) {
  if (!data) return `Request failed (${status}).`
  if (typeof data === 'string') return data
  if (Array.isArray(data)) return data.join(' ')
  // Plain-language fields first.
  for (const k of ['detail', 'message', 'error', 'non_field_errors']) {
    const v = data[k]
    if (v) return Array.isArray(v) ? v.join(' ') : String(v)
  }
  // Field-level errors: {email: ['already exists'], term: ['Required']}
  const parts = Object.entries(data)
    .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${Array.isArray(v) ? v.join(', ') : v}`)
  if (parts.length) return parts.join(' · ')
  return `Request failed (${status}).`
}

export const get = path => api(path)
export const post = (path, body) => api(path, { method: 'POST', body: body instanceof FormData ? body : JSON.stringify(body) })
export const patch = (path, body) => api(path, { method: 'PATCH', body: body instanceof FormData ? body : JSON.stringify(body) })
export const put = (path, body) => api(path, { method: 'PUT', body: body instanceof FormData ? body : JSON.stringify(body) })
export const remove = path => api(path, { method: 'DELETE' })

/** Download an authenticated file (PDF receipts, report cards, exports). */
export async function download(path, filename) {
  const token = getToken()
  const response = await fetch(`${API_ROOT}${withCtx(path)}`, {
    headers: token ? { Authorization: `Token ${token}` } : {},
  })
  if (!response.ok) {
    let data = null
    try { data = await response.json() } catch {}
    throw new Error(extractError(data, response.status))
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename || 'download'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

/** WebSocket URL for the chat channel (token-authenticated via query). */
export function chatSocketUrl() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${location.host}/ws/chat/?token=${encodeURIComponent(getToken() || '')}`
}
