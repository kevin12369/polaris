/**
 * 统一 API 客户端：自动附带令牌、统一错误处理。
 */
const BASE = import.meta.env.VITE_API_BASE || '/api'

let token = localStorage.getItem('sw_token') || ''

export function setToken(t) {
  token = t || ''
  if (t) localStorage.setItem('sw_token', t)
  else localStorage.removeItem('sw_token')
}

export function getToken() {
  return token
}

export function clearSession() {
  token = ''
  localStorage.removeItem('sw_token')
  localStorage.removeItem('sw_user')
  localStorage.removeItem('sw_company')
}

export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message)
    this.status = status
    this.payload = payload
  }
}

async function request(method, path, body, opts = {}) {
  const headers = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(BASE + path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  let payload = null
  const text = await res.text()
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = text
    }
  }

  if (!res.ok) {
    // 401 自动登出
    if (res.status === 401 && !opts.silentAuth) {
      clearSession()
      if (!location.hash.startsWith('#/login')) location.hash = '#/login'
    }
    const msg =
      (payload && payload.detail && (typeof payload.detail === 'string' ? payload.detail : payload.detail[0]?.msg)) ||
      `请求失败 (${res.status})`
    throw new ApiError(msg, res.status, payload)
  }
  return payload
}

export const api = {
  get: (p, opts) => request('GET', p, undefined, opts),
  post: (p, b, opts) => request('POST', p, b ?? {}, opts),
  put: (p, b, opts) => request('PUT', p, b ?? {}, opts),
  patch: (p, b, opts) => request('PATCH', p, b ?? {}, opts),
  del: (p, opts) => request('DELETE', p, undefined, opts),
}

// ---- 认证 ----
export const authApi = {
  login: (email, password) => api.post('/auth/login', { email, password }),
  register: (payload) => api.post('/auth/register', payload),
  me: () => api.get('/auth/me'),
  members: () => api.get('/auth/members'),
  addMember: (payload) => api.post('/auth/members', payload),
}

// ---- 工单 ----
export const ticketApi = {
  meta: () => api.get('/tickets/meta'),
  list: (params = {}) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => {
      if (v !== '' && v !== null && v !== undefined) q.append(k, v)
    })
    return api.get(`/tickets?${q.toString()}`)
  },
  get: (id) => api.get(`/tickets/${id}`),
  create: (payload) => api.post('/tickets', payload),
  update: (id, payload) => api.patch(`/tickets/${id}`, payload),
  changeStatus: (id, toStatus, note, resolutionNote) =>
    api.post(`/tickets/${id}/status`, {
      to_status: toStatus,
      note: note || '',
      resolution_note: resolutionNote || null,
    }),
  comment: (id, note) => api.post(`/tickets/${id}/comment`, { note }),
  suggest: (id, content) => api.post(`/tickets/${id}/suggest`, { content }),
  promoteToKb: (id, payload = {}) => api.post(`/tickets/${id}/promote-to-kb`, payload),
}

// ---- 知识库 ----
export const kbApi = {
  list: (params = {}) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => {
      if (v !== '' && v !== null && v !== undefined) q.append(k, v)
    })
    return api.get(`/kb?${q.toString()}`)
  },
  get: (id) => api.get(`/kb/${id}`),
  create: (payload) => api.post('/kb', payload),
  update: (id, payload) => api.put(`/kb/${id}`, payload),
  remove: (id) => api.del(`/kb/${id}`),
  categories: () => api.get('/kb/categories'),
  helpful: (id) => api.post(`/kb/${id}/helpful`),
}

// ---- AI 排障 ----
export const assistantApi = {
  status: () => api.get('/assistant/status'),
  troubleshoot: (errorText, ticketId) =>
    api.post('/assistant/troubleshoot', { error_text: errorText, ticket_id: ticketId ?? null }),
  history: () => api.get('/assistant/history'),
}

// ---- 仪表盘 ----
export const dashboardApi = {
  get: (days = 30) => api.get(`/dashboard?days=${days}`),
}
