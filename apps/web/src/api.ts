import type { PlanningRunResponse, Ticket } from './types'

const BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8080'

async function handleResponse<T>(res: Response): Promise<T> {
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

export async function createTicket(title: string, description: string): Promise<Ticket> {
  const res = await fetch(`${BASE}/tickets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, description }),
  })
  return handleResponse<Ticket>(res)
}

export async function createPlanningRun(ticketId: string): Promise<PlanningRunResponse> {
  const res = await fetch(`${BASE}/tickets/${ticketId}/planning-runs`, {
    method: 'POST',
  })
  return handleResponse<PlanningRunResponse>(res)
}
