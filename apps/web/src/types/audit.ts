export type AuditActorType = 'user' | 'system' | 'agent'

export interface AuditEvent {
  id: string
  project_id: string | null
  actor_type: AuditActorType
  actor_id: string
  action: string
  target_type: string
  target_id: string
  details: Record<string, unknown>
  created_at: string
}
