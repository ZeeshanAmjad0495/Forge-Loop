import { useState } from 'react'
import type { AuditEvent } from '../../types'

/**
 * Task 98 — operational execution timeline.
 *
 * A curated, chronological read of the audit log (the source of truth):
 * provider/route decisions, runner decisions, approvals, failures,
 * CI/incident analysis. No new backend — derived from already-loaded
 * audit events. Kept deliberately simple (no analytics/billing UI).
 */

type Category =
  | 'failure'
  | 'approval'
  | 'runner'
  | 'analysis'
  | 'provider'
  | 'other'

const COLORS: Record<Category, string> = {
  failure: '#e06c75',
  approval: '#e5c07b',
  runner: '#61afef',
  analysis: '#c678dd',
  provider: '#98c379',
  other: '#888',
}

function categorize(action: string): Category {
  if (action.endsWith('_failed') || action.endsWith('_blocked')) return 'failure'
  if (action.startsWith('approval_') || action.includes('approval')) return 'approval'
  if (action.startsWith('runner_route') || action.includes('execution') || action.includes('tool_run')) return 'runner'
  if (action.includes('analysis') || action.startsWith('ci_') || action.startsWith('incident_')) return 'analysis'
  if (action.startsWith('model_route') || action.includes('cost')) return 'provider'
  return 'other'
}

function salient(details: Record<string, unknown>): string {
  const keys = [
    'selected_runner',
    'selected_provider',
    'provider',
    'reason',
    'conclusion',
    'status',
    'error',
  ]
  const parts: string[] = []
  for (const k of keys) {
    const v = details?.[k]
    if (v !== undefined && v !== null && v !== '') {
      parts.push(`${k}=${String(v).slice(0, 60)}`)
    }
  }
  return parts.join('  ')
}

export function ExecutionTimelinePanel({ events }: { events: AuditEvent[] }) {
  const [open, setOpen] = useState(true)
  const [onlyKey, setOnlyKey] = useState(false)
  const rows = onlyKey
    ? events.filter(e => {
        const c = categorize(e.action)
        return c === 'failure' || c === 'approval' || c === 'runner' || c === 'provider'
      })
    : events
  return (
    <div style={{ marginTop: 16 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{ background: 'none', border: '1px solid #444', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: 13 }}
      >
        {open ? '▾' : '▸'} Execution timeline ({events.length})
      </button>
      {open && (
        <div style={{ marginTop: 8 }}>
          <label style={{ fontSize: 12, color: '#aaa', display: 'block', marginBottom: 8 }}>
            <input
              type="checkbox"
              checked={onlyKey}
              onChange={e => setOnlyKey(e.target.checked)}
              style={{ marginRight: 6 }}
            />
            Key decisions only (provider / runner / approval / failures)
          </label>
          {rows.length === 0 && (
            <p style={{ fontSize: 13, color: '#888' }}>No execution events yet.</p>
          )}
          {rows.map(e => {
            const cat = categorize(e.action)
            const info = salient(e.details || {})
            return (
              <div
                key={e.id}
                style={{
                  fontSize: 12,
                  marginBottom: 6,
                  paddingLeft: 8,
                  borderLeft: `3px solid ${COLORS[cat]}`,
                }}
              >
                <span style={{ color: '#888', marginRight: 6 }}>
                  {e.created_at.slice(0, 19).replace('T', ' ')}
                </span>
                <span style={{ color: COLORS[cat], fontWeight: 600, marginRight: 6 }}>
                  {e.action}
                </span>
                <span style={{ color: '#aaa', marginRight: 6 }}>
                  {e.target_type}
                </span>
                {info && (
                  <span style={{ color: '#ccc' }}>· {info}</span>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
