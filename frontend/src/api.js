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
  // 文件上传：multipart/form-data，不能设 Content-Type（要带 boundary）
  upload: (p, file, opts = {}) => {
    const headers = { Accept: 'application/json' }
    if (token) headers.Authorization = `Bearer ${token}`
    const form = new FormData()
    form.append('file', file, file.name)
    return fetch(BASE + p, { method: 'POST', headers, body: form }).then(async (res) => {
      const text = await res.text()
      let payload = null
      if (text) {
        try {
          payload = JSON.parse(text)
        } catch {
          payload = text
        }
      }
      if (!res.ok) {
        if (res.status === 401 && !opts.silentAuth) {
          clearSession()
          if (!location.hash.startsWith('#/login')) location.hash = '#/login'
        }
        const msg =
          (payload && payload.detail &&
            (typeof payload.detail === 'string' ? payload.detail : payload.detail[0]?.msg)) ||
          `上传失败 (${res.status})`
        throw new ApiError(msg, res.status, payload)
      }
      return payload
    })
  },
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

// ---- 附件 ----
export const attachmentApi = {
  list: (ticketId) => api.get(`/tickets/${ticketId}/attachments`),
  upload: (ticketId, file) => api.upload(`/tickets/${ticketId}/attachments`, file),
  remove: (ticketId, attachmentId) => api.del(`/tickets/${ticketId}/attachments/${attachmentId}`),
  // 下载需要带令牌，不能用普通 <a href>，改为取 blob 后触发下载
  download: async (ticketId, attachmentId, filename) => {
    const res = await fetch(`${BASE}/tickets/${ticketId}/attachments/${attachmentId}/download`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) throw new ApiError(`下载失败 (${res.status})`, res.status)
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename || 'download'
    document.body.appendChild(a)
    a.click()
    a.remove()
    // 释放对象 URL，避免内存泄漏
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  },
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
