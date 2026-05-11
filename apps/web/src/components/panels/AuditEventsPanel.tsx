import { useState } from 'react'
import type { AuditEvent } from '../../types'

export function AuditEventsPanel({ events }: { events: AuditEvent[] }) {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ marginTop: 8 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{ background: 'none', border: '1px solid #444', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: 13 }}
      >
        {open ? '▾' : '▸'} Audit log ({events.length})
      </button>
      {open && (
        <div style={{ marginTop: 8 }}>
          {events.length === 0 && <p style={{ fontSize: 13, color: '#888' }}>No events yet.</p>}
          {events.map(e => (
            <div key={e.id} style={{ fontSize: 12, color: '#aaa', marginBottom: 4 }}>
              <span style={{ color: '#888', marginRight: 6 }}>{e.created_at.slice(0, 19).replace('T', ' ')}</span>
              <span style={{ color: '#fff', marginRight: 6 }}>{e.action}</span>
              <span style={{ marginRight: 6 }}>{e.target_type}</span>
              <code style={{ fontSize: 11 }}>{e.target_id.slice(0, 12)}…</code>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
