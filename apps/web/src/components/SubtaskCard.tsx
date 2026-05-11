import { useState } from 'react'
import { updateSubtask } from '../api'
import type { AssigneeType, DevTaskStatus, Subtask } from '../types'
import { ALL_STATUSES, ASSIGNEE_TYPES } from '../lib/constants'

export function SubtaskList({
  subtasks,
  onSubtaskUpdate,
}: {
  subtasks: Subtask[]
  onSubtaskUpdate: (updated: Subtask) => void
}) {
  if (subtasks.length === 0) return null
  return (
    <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
      {subtasks.map(st => (
        <SubtaskRow key={st.id} subtask={st} onUpdate={onSubtaskUpdate} />
      ))}
    </ul>
  )
}

export function SubtaskRow({ subtask, onUpdate }: { subtask: Subtask; onUpdate: (s: Subtask) => void }) {
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleStatusChange(next: string) {
    setError(null)
    setBusy(true)
    try {
      const updated = await updateSubtask(subtask.id, { status: next as DevTaskStatus })
      onUpdate(updated)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function handleAssigneeTypeChange(next: AssigneeType) {
    setError(null)
    setBusy(true)
    try {
      const updated = await updateSubtask(subtask.id, { assignee_type: next })
      onUpdate(updated)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function handleAssigneeNameBlur(name: string) {
    if (name === (subtask.assignee_name ?? '')) return
    setBusy(true)
    try {
      const updated = await updateSubtask(subtask.id, { assignee_name: name || null })
      onUpdate(updated)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <li style={{ marginBottom: 6 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 13 }}>{subtask.title}</span>
        <select
          value={subtask.status}
          onChange={e => handleStatusChange(e.target.value)}
          disabled={busy}
          style={{ fontSize: 11 }}
        >
          {ALL_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        {subtask.qa_required && (
          <span className="status done" style={{ fontSize: 11 }}>QA</span>
        )}
        <select
          value={subtask.assignee_type}
          onChange={e => handleAssigneeTypeChange(e.target.value as AssigneeType)}
          disabled={busy}
          style={{ fontSize: 11 }}
        >
          {ASSIGNEE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        {subtask.assignee_type !== 'unassigned' && (
          <input
            defaultValue={subtask.assignee_name ?? ''}
            onBlur={e => handleAssigneeNameBlur(e.target.value)}
            placeholder="name"
            disabled={busy}
            style={{ fontSize: 11, padding: '1px 4px', background: '#1a1a1a', border: '1px solid #444', color: '#fff', borderRadius: 3, width: 90 }}
          />
        )}
      </div>
      {error && <div className="error" style={{ fontSize: 11, marginTop: 2 }}>{error}</div>}
    </li>
  )
}
