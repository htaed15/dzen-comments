let token = localStorage.getItem('access') || ''

export function setToken(value) {
  token = value || ''
  if (token) localStorage.setItem('access', token)
  else localStorage.removeItem('access')
}
export const getToken = () => token

async function request(url, options = {}) {
  const headers = { ...(options.headers || {}) }
  if (token) headers.Authorization = `Bearer ${token}`
  const resp = await fetch(url, { ...options, headers })
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
  captcha: () => request('/api/captcha/'),
  register: (body) => request('/api/auth/register/', json(body)),
  login: (body) => request('/api/auth/token/', json(body)),
}

// Ошибки DRF -> плоский объект { поле: 'сообщение' }
export function flattenErrors(data) {
  const out = {}
  for (const [key, value] of Object.entries(data || {})) {
    out[key] = Array.isArray(value) ? value.join(' ') : String(value)
  }
  return out
}
