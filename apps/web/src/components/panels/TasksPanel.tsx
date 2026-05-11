import { useEffect, useState } from 'react'
import { createProjectEpic, listProjectEpics, updateEpic } from '../../api'
import type { AssigneeType, Epic, EpicPriority, EpicStatus } from '../../types'
import { ASSIGNEE_TYPES, EPIC_PRIORITIES, EPIC_STATUSES } from '../../lib/constants'

export function EpicsPanel({ projectId }: { projectId: string }) {
  const [epics, setEpics] = useState<Epic[]>([])
  const [selected, setSelected] = useState<Epic | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState<EpicPriority>('medium')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')

  useEffect(() => {
    listProjectEpics(projectId)
      .then(setEpics)
      .catch(err => setError((err as Error).message))
  }, [projectId])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setCreateError('')
    setCreating(true)
    try {
      const epic = await createProjectEpic(projectId, { title: title.trim(), description: description.trim(), priority })
      setEpics(prev => [...prev, epic])
      setTitle('')
      setDescription('')
      setPriority('medium')
    } catch (err) {
      setCreateError((err as Error).message)
    } finally {
      setCreating(false)
    }
  }

  async function handleEpicPatch(epicId: string, patch: Partial<{ status: EpicStatus; priority: EpicPriority; assignee_type: AssigneeType; assignee_name: string }>) {
    setBusy(true)
    try {
      const updated = await updateEpic(epicId, patch)
      setEpics(prev => prev.map(e => e.id === updated.id ? updated : e))
      setSelected(updated)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section style={{ marginTop: 24 }}>
      <h3>Epics</h3>
      {error && <div className="error">{error}</div>}

      {epics.length > 0 && (
        <div className="ticket-list" style={{ marginBottom: 12 }}>
          {epics.map(e => (
            <button
              key={e.id}
              className={`ticket-row ${e.status === 'completed' ? 'done' : ''}`}
              onClick={() => setSelected(selected?.id === e.id ? null : e)}
            >
              <span className="ticket-row-title">{e.title}</span>
              <span className="ticket-row-status">{e.status} · {e.priority}</span>
            </button>
          ))}
        </div>
      )}

      {selected && (
        <div style={{ border: '1px solid #444', borderRadius: 6, padding: '10px 14px', marginBottom: 12 }}>
          <strong>{selected.title}</strong>
          {selected.requirement_id && (
            <p style={{ fontSize: 12, color: '#aaa', margin: '4px 0' }}>Requirement: {selected.requirement_id}</p>
          )}
          {selected.business_goal && <p style={{ fontSize: 13, margin: '4px 0' }}>{selected.business_goal}</p>}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 6 }}>
            <label style={{ fontSize: 12 }}>Status:
              <select value={selected.status} onChange={e => handleEpicPatch(selected.id, { status: e.target.value as EpicStatus })} disabled={busy} style={{ marginLeft: 4, fontSize: 12 }}>
                {EPIC_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
            <label style={{ fontSize: 12 }}>Priority:
              <select value={selected.priority} onChange={e => handleEpicPatch(selected.id, { priority: e.target.value as EpicPriority })} disabled={busy} style={{ marginLeft: 4, fontSize: 12 }}>
                {EPIC_PRIORITIES.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </label>
            <label style={{ fontSize: 12 }}>Assignee:
              <select value={selected.assignee_type} onChange={e => handleEpicPatch(selected.id, { assignee_type: e.target.value as AssigneeType })} disabled={busy} style={{ marginLeft: 4, fontSize: 12 }}>
                {ASSIGNEE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </label>
            {selected.assignee_type !== 'unassigned' && (
              <label style={{ fontSize: 12 }}>Name:
                <input
                  defaultValue={selected.assignee_name ?? ''}
                  onBlur={e => { if (e.target.value !== (selected.assignee_name ?? '')) handleEpicPatch(selected.id, { assignee_name: e.target.value }) }}
                  disabled={busy}
                  style={{ marginLeft: 4, fontSize: 12, padding: '2px 4px', background: '#1a1a1a', border: '1px solid #444', color: '#fff', borderRadius: 3, width: 120 }}
                />
              </label>
            )}
          </div>
        </div>
      )}

      <h4>New epic</h4>
      <form onSubmit={handleCreate}>
        <label htmlFor="epic-title">Title</label>
        <input id="epic-title" value={title} onChange={e => setTitle(e.target.value)} required disabled={creating} placeholder="Epic name" />
        <label htmlFor="epic-desc">Description</label>
        <textarea id="epic-desc" value={description} onChange={e => setDescription(e.target.value)} disabled={creating} placeholder="Optional description" />
        <label htmlFor="epic-priority">Priority</label>
        <select id="epic-priority" value={priority} onChange={e => setPriority(e.target.value as EpicPriority)} disabled={creating}>
          {EPIC_PRIORITIES.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
        {createError && <div className="error">{createError}</div>}
        <button type="submit" disabled={creating}>{creating ? 'Creating…' : 'Create epic'}</button>
      </form>
    </section>
  )
}
