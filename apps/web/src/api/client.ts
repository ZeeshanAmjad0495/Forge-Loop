import { clearToken, getToken } from '../auth'

export const BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8080'

export async function handleResponse<T>(res: Response): Promise<T> {
  if (res.status === 401) {
    clearToken()
    throw new Error('401: Unauthorized')
  }
  if (res.ok) return res.json() as Promise<T>
  let message = res.statusText
  try {
    const body = await res.json()
    if (typeof body.detail === 'string') message = body.detail
  } catch {
    // keep statusText
  }
  throw new Error(`${res.status}: ${message}`)
}

export function authHeaders(): Record<string, string> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

type Method = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'

export async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { ...authHeaders() }
  const init: RequestInit = { method, headers }
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    init.body = JSON.stringify(body)
  }
  const res = await fetch(`${BASE}${path}`, init)
  return handleResponse<T>(res)
}
