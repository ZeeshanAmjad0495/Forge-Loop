import { request } from './client'
import type { AuditEvent } from '../types'

export function listProjectAuditEvents(projectId: string): Promise<AuditEvent[]> {
  return request<AuditEvent[]>('GET', `/projects/${projectId}/audit-events`)
}

export function getAuditEvent(auditEventId: string): Promise<AuditEvent> {
  return request<AuditEvent>('GET', `/audit-events/${auditEventId}`)
}
