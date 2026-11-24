import type { LoginResponse } from '../types'

const API = '/api/v1'

function tokens() {
  return {
    access: localStorage.getItem('ve_access_token'),
    refresh: localStorage.getItem('ve_refresh_token'),
  }
}

export function storeTokens(data: LoginResponse) {
  localStorage.setItem('ve_access_token', data.access_token)
  localStorage.setItem('ve_refresh_token', data.refresh_token)
}

export function clearTokens() {
  localStorage.removeItem('ve_access_token')
  localStorage.removeItem('ve_refresh_token')
}

async function refreshAccess(): Promise<boolean> {
  const { refresh } = tokens()
  if (!refresh) return false
  try {
    const res = await fetch(`${API}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    })
    if (!res.ok) return false
    const data = (await res.json()) as LoginResponse
    storeTokens(data)
    return true
  } catch {
    return false
  }
}

export async function apiFetch<T>(path: string, options: RequestInit = {}, retry = true): Promise<T> {
  const { access } = tokens()
  const headers = new Headers(options.headers)
  headers.set('Content-Type', 'application/json')
  if (access) headers.set('Authorization', `Bearer ${access}`)

  // 5-second timeout to prevent UI freezes if backend is offline
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 5000)

  let response: Response
  try {
    response = await fetch(`${API}${path}`, {
      ...options,
      headers,
      signal: options.signal || controller.signal,
    })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('Connection timed out. Backend server is not responding.')
    }
    throw new Error('Backend server is unreachable. Please ensure the backend is running on port 8000.')
  } finally {
    clearTimeout(timer)
  }

  if (response.status === 401 && retry && (await refreshAccess())) {
    return apiFetch<T>(path, options, false)
  }
  if (response.status === 401) {
    clearTokens()
    if (!window.location.pathname.startsWith('/login')) {
      window.location.assign('/login')
    }
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const body = await response.json()
      message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* ignore */
    }
    throw new Error(message)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export async function downloadFile(path: string, filename: string): Promise<void> {
  const { access } = tokens()
  const headers = new Headers()
  if (access) headers.set('Authorization', `Bearer ${access}`)
  const response = await fetch(`${API}${path}`, { headers })
  if (!response.ok) throw new Error(`Export failed (${response.status})`)
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path),
  post: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  put: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
}
