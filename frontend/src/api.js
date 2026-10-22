let token = localStorage.getItem('access') || ''
let meCache = null

export function setToken(value) {
  token = value || ''
  meCache = null
  if (token) localStorage.setItem('access', token)
  else localStorage.removeItem('access')
}
export const getToken = () => token

async function request(url, options = {}, retried = false) {
  const headers = { ...(options.headers || {}) }
  if (token) headers.Authorization = `Bearer ${token}`
  const resp = await fetch(url, { ...options, headers })
  // Просроченный/битый токен: DRF отвечает 401 даже на публичных эндпоинтах.
  // Сбрасываем токен и повторяем запрос как анонимный.
  if (resp.status === 401 && token && !retried) {
    setToken('')
    window.dispatchEvent(new Event('auth-expired'))
    return request(url, options, true)
  }
  const data = await resp.json().catch(() => ({}))
  if (!resp.ok) {
    const err = new Error('request failed')
    err.status = resp.status
    err.data = data
    throw err
  }
  return data
}

const json = (body) => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  list: (ordering, page) => request(`/api/comments/?ordering=${encodeURIComponent(ordering)}&page=${page}`),
  create: (formData) => request('/api/comments/', { method: 'POST', body: formData }),
  preview: (text) => request('/api/comments/preview/', json({ text })),
  thread: (id) => request(`/api/comments/${id}/thread/`),
  profile: (username, page = 1) => request(`/api/users/${encodeURIComponent(username)}/?page=${page}`),
  captcha: () => request('/api/captcha/'),
  register: (body) => request('/api/auth/register/', json(body)),
  login: (body) => request('/api/auth/token/', json(body)),
  // данные своего профиля для автозаполнения полей 1-3 (кешируются до выхода)
  me: () => {
    if (!meCache) {
      meCache = request('/api/auth/me/').catch((e) => {
        meCache = null
        throw e
      })
    }
    return meCache
  },
}

// Ошибки DRF -> плоский объект { поле: 'сообщение' }
export function flattenErrors(data) {
  const out = {}
  for (const [key, value] of Object.entries(data || {})) {
    out[key] = Array.isArray(value) ? value.join(' ') : String(value)
  }
  return out
}
