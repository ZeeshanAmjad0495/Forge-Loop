import { clearToken, getToken } from './auth'
import type { LoginResponse, PlanningRunResponse, ProvidersResponse, Ticket } from './types'

const BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8080'

async function handleResponse<T>(res: Response): Promise<T> {
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

function authHeaders(): Record<string, string> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const res = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  return handleResponse<LoginResponse>(res)
}

export async function createTicket(title: string, description: string): Promise<Ticket> {
  const res = await fetch(`${BASE}/tickets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ title, description }),
  })
  return handleResponse<Ticket>(res)
}

export async function createPlanningRun(
  ticketId: string,
  provider?: string,
): Promise<PlanningRunResponse> {
  const init: RequestInit = {
    method: 'POST',
    headers: { ...authHeaders() },
  }
  if (provider) {
    init.headers = { 'Content-Type': 'application/json', ...authHeaders() }
    init.body = JSON.stringify({ provider })
  }
  const res = await fetch(`${BASE}/tickets/${ticketId}/planning-runs`, init)
  return handleResponse<PlanningRunResponse>(res)
}

export async function listProviders(): Promise<ProvidersResponse> {
  const res = await fetch(`${BASE}/llm/providers`, { headers: authHeaders() })
  return handleResponse<ProvidersResponse>(res)
}
