import { request } from './client'
import type { PlanningRunResponse, Ticket } from '../types'

export function createProjectTicket(
  projectId: string,
  title: string,
  description: string,
): Promise<Ticket> {
  return request<Ticket>('POST', `/projects/${projectId}/tickets`, { title, description })
}

export function listProjectTickets(projectId: string): Promise<Ticket[]> {
  return request<Ticket[]>('GET', `/projects/${projectId}/tickets`)
}

export function createTicket(title: string, description: string): Promise<Ticket> {
  return request<Ticket>('POST', `/tickets`, { title, description })
}

export function createPlanningRun(
  ticketId: string,
  provider?: string,
): Promise<PlanningRunResponse> {
  return request<PlanningRunResponse>(
    'POST',
    `/tickets/${ticketId}/planning-runs`,
    provider ? { provider } : undefined,
  )
}
