import { useEffect, useState } from 'react'
import {
  approveMemoryCandidate,
  createMemoryCandidate,
  createMemoryLearningRun,
  listProjectMemoryCandidates,
  listProjectMemoryLearningRuns,
  rejectMemoryCandidate,
  updateMemoryCandidate,
} from '../../api'
import type {
  MemoryCandidateMemoryType,
  MemoryCandidateSourceType,
  MemoryLearningRun,
  ProjectMemoryCandidate,
} from '../../types'
import { LEARNING_SOURCE_TYPES, MEMORY_TYPES } from '../../lib/constants'
import { memoryCandidateStatusStyle } from '../../lib/status'

export function MemoryCandidatesPanel({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState(false)
  const [candidates, setCandidates] = useState<ProjectMemoryCandidate[]>([])
  const [runs, setRuns] = useState<MemoryLearningRun[]>([])
  const [showRuns, setShowRuns] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const [learningSource, setLearningSource] = useState<MemoryCandidateSourceType>('ci_analysis')
  const [learningSourceId, setLearningSourceId] = useState('')
  const [showManual, setShowManual] = useState(false)
  const [manualType, setManualType] = useState<MemoryCandidateMemoryType>('known_failure_pattern')
  const [manualTitle, setManualTitle] = useState('')
  const [manualContent, setManualContent] = useState('')
  const [manualTags, setManualTags] = useState('')

  useEffect(() => {
    if (!open) return
    listProjectMemoryCandidates(projectId).then(setCandidates).catch(() => {})
    listProjectMemoryLearningRuns(projectId).then(setRuns).catch(() => {})
  }, [open, projectId])

  async function refreshCandidates() {
    try {
      setCandidates(await listProjectMemoryCandidates(projectId))
    } catch { /* non-critical */ }
  }

  async function refreshRuns() {
    try {
      setRuns(await listProjectMemoryLearningRuns(projectId))
    } catch { /* non-critical */ }
  }

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault()
    if (!learningSourceId.trim()) {
      setError('Source id is required to generate candidates.')
      return
    }
    setBusy(true)
    setError('')
    try {
      await createMemoryLearningRun(projectId, {
        source_type: learningSource,
        source_id: learningSourceId.trim(),
      })
      setLearningSourceId('')
      await refreshCandidates()
      await refreshRuns()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function handleManualCreate(e: React.FormEvent) {
    e.preventDefault()
    if (!manualTitle.trim() || !manualContent.trim()) {
      setError('Title and content are required for a manual candidate.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const tags = manualTags
        .split(',')
        .map(t => t.trim())
        .filter(Boolean)
      await createMemoryCandidate(projectId, {
        memory_type: manualType,
        title: manualTitle.trim(),
        content: manualContent.trim(),
        tags,
      })
      setManualTitle('')
      setManualContent('')
      setManualTags('')
      await refreshCandidates()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function handleApprove(candidate: ProjectMemoryCandidate) {
    setBusy(true)
    setError('')
    try {
      const updated = await approveMemoryCandidate(candidate.id)
      setCandidates(prev => prev.map(c => (c.id === updated.id ? updated : c)))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function handleReject(candidate: ProjectMemoryCandidate, reason: string) {
    setBusy(true)
    setError('')
    try {
      const updated = await rejectMemoryCandidate(candidate.id, { reason: reason || null })
      setCandidates(prev => prev.map(c => (c.id === updated.id ? updated : c)))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function handleEdit(candidate: ProjectMemoryCandidate, patch: { title?: string; content?: string; tags?: string[]; memory_type?: MemoryCandidateMemoryType }) {
    setBusy(true)
    setError('')
    try {
      const updated = await updateMemoryCandidate(candidate.id, patch)
      setCandidates(prev => prev.map(c => (c.id === updated.id ? updated : c)))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section style={{ marginTop: 24 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{ background: 'none', border: '1px solid #444', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: 13 }}
      >
        {open ? '▾' : '▸'} Project memory candidates ({candidates.length})
      </button>
      {open && (
        <div style={{ marginTop: 12 }}>
          <p style={{ fontSize: 12, color: '#888', margin: '0 0 8px' }}>
            Memory candidates are LLM-distilled or human-authored lessons. Nothing
            is written to durable project memory until you approve it. ForgeLoop
            does not use vector search, embeddings, or background learning.
          </p>
          {error && <div className="error" style={{ marginBottom: 6, fontSize: 12 }}>{error}</div>}

          <form onSubmit={handleGenerate} style={{ display: 'grid', gridTemplateColumns: '1fr 2fr auto', gap: 8, marginBottom: 12 }}>
            <label style={{ fontSize: 12 }}>
              Source type
              <select
                value={learningSource}
                onChange={e => setLearningSource(e.target.value as MemoryCandidateSourceType)}
                disabled={busy}
                style={{ width: '100%' }}
              >
                {LEARNING_SOURCE_TYPES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
            <label style={{ fontSize: 12 }}>
              Source id
              <input
                value={learningSourceId}
                onChange={e => setLearningSourceId(e.target.value)}
                disabled={busy}
                placeholder="paste id of an existing CI analysis, incident analysis, etc."
                style={{ width: '100%' }}
              />
            </label>
            <div style={{ alignSelf: 'end' }}>
              <button type="submit" disabled={busy} className="primary">Generate candidates</button>
            </div>
          </form>

          <button
            onClick={() => setShowManual(s => !s)}
            style={{ background: 'none', border: '1px solid #444', borderRadius: 4, padding: '2px 8px', cursor: 'pointer', fontSize: 12, marginBottom: 8 }}
          >
            {showManual ? '▾' : '▸'} Add a manual candidate
          </button>
          {showManual && (
            <form onSubmit={handleManualCreate} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
              <label style={{ fontSize: 12 }}>
                Memory type
                <select value={manualType} onChange={e => setManualType(e.target.value as MemoryCandidateMemoryType)} disabled={busy} style={{ width: '100%' }}>
                  {MEMORY_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </label>
              <label style={{ fontSize: 12 }}>
                Tags (comma-separated)
                <input value={manualTags} onChange={e => setManualTags(e.target.value)} disabled={busy} placeholder="testing, regression" style={{ width: '100%' }} />
              </label>
              <label style={{ fontSize: 12, gridColumn: '1 / span 2' }}>
                Title
                <input value={manualTitle} onChange={e => setManualTitle(e.target.value)} disabled={busy} placeholder="Short label for this lesson" style={{ width: '100%' }} />
              </label>
              <label style={{ fontSize: 12, gridColumn: '1 / span 2' }}>
                Content
                <textarea
                  value={manualContent}
                  onChange={e => setManualContent(e.target.value)}
                  disabled={busy}
                  rows={3}
                  placeholder="Durable lesson — 1 to 4 sentences. No secrets, no raw logs."
                  style={{ width: '100%' }}
                />
              </label>
              <div style={{ gridColumn: '1 / span 2' }}>
                <button type="submit" disabled={busy} className="primary">Add candidate</button>
              </div>
            </form>
          )}

          {candidates.length === 0
            ? <p style={{ fontSize: 12, color: '#666' }}>No memory candidates yet.</p>
            : candidates.map(c => (
                <MemoryCandidateCard
                  key={c.id}
                  candidate={c}
                  busy={busy}
                  onApprove={() => handleApprove(c)}
                  onReject={reason => handleReject(c, reason)}
                  onEdit={patch => handleEdit(c, patch)}
                />
              ))
          }

          <button
            onClick={() => setShowRuns(s => !s)}
            style={{ background: 'none', border: '1px solid #444', borderRadius: 4, padding: '2px 8px', cursor: 'pointer', fontSize: 12, marginTop: 8 }}
          >
            {showRuns ? '▾' : '▸'} Learning runs ({runs.length})
          </button>
          {showRuns && (
            <div style={{ marginTop: 8 }}>
              {runs.length === 0
                ? <p style={{ fontSize: 12, color: '#666' }}>No learning runs yet.</p>
                : runs.map(r => (
                    <div key={r.id} style={{ border: '1px solid #333', borderRadius: 4, padding: 8, marginBottom: 6, fontSize: 12 }}>
                      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                        <span className="status">{r.status}</span>
                        <span style={{ color: '#888' }}>{r.source_type}/{r.source_id}</span>
                        <span style={{ color: '#888' }}>{r.provider}/{r.model}</span>
                        <span style={{ marginLeft: 'auto', color: '#666', fontSize: 11 }}>
                          {new Date(r.created_at).toLocaleString()}
                        </span>
                      </div>
                      {r.summary && <p style={{ margin: '4px 0' }}>{r.summary}</p>}
                      <p style={{ margin: '4px 0', color: '#888' }}>candidates created: {r.candidates_created}</p>
                      {r.error_message && (
                        <p className="error" style={{ marginTop: 4 }}>{r.error_message}</p>
                      )}
                    </div>
                  ))
              }
            </div>
          )}
        </div>
      )}
    </section>
  )
}

function MemoryCandidateCard({
  candidate,
  busy,
  onApprove,
  onReject,
  onEdit,
}: {
  candidate: ProjectMemoryCandidate
  busy: boolean
  onApprove: () => void
  onReject: (reason: string) => void
  onEdit: (patch: { title?: string; content?: string; tags?: string[]; memory_type?: MemoryCandidateMemoryType }) => void
}) {
  const [editing, setEditing] = useState(false)
  const [editTitle, setEditTitle] = useState(candidate.title)
  const [editContent, setEditContent] = useState(candidate.content)
  const [editTags, setEditTags] = useState(candidate.tags.join(', '))
  const [editType, setEditType] = useState<MemoryCandidateMemoryType>(candidate.memory_type)
  const [showReject, setShowReject] = useState(false)
  const [rejectReason, setRejectReason] = useState('')

  const proposed = candidate.status === 'proposed'

  function handleEditSave() {
    onEdit({
      title: editTitle,
      content: editContent,
      tags: editTags.split(',').map(t => t.trim()).filter(Boolean),
      memory_type: editType,
    })
    setEditing(false)
  }

  return (
    <div style={{ border: '1px solid #333', borderRadius: 4, padding: 8, marginBottom: 8, fontSize: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={memoryCandidateStatusStyle(candidate.status)}>{candidate.status}</span>
        <span style={{ color: '#888' }}>{candidate.memory_type}</span>
        <span style={{ color: '#888' }}>{candidate.source_type}{candidate.source_id ? `/${candidate.source_id.slice(0, 8)}` : ''}</span>
        {candidate.confidence !== null && (
          <span style={{ color: '#888' }}>conf {candidate.confidence.toFixed(2)}</span>
        )}
        <span style={{ marginLeft: 'auto', color: '#666', fontSize: 11 }}>
          {new Date(candidate.created_at).toLocaleString()}
        </span>
      </div>
      {!editing && (
        <>
          <div style={{ marginTop: 4 }}><strong>{candidate.title}</strong></div>
          <div style={{ marginTop: 4, color: '#ccc', whiteSpace: 'pre-wrap' }}>{candidate.content}</div>
          {candidate.tags.length > 0 && (
            <div style={{ marginTop: 4, color: '#888' }}>tags: {candidate.tags.join(', ')}</div>
          )}
          {candidate.rejection_reason && (
            <div style={{ marginTop: 4, color: '#888' }}>rejection reason: {candidate.rejection_reason}</div>
          )}
        </>
      )}
      {editing && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginTop: 6 }}>
          <label style={{ fontSize: 12 }}>
            Memory type
            <select value={editType} onChange={e => setEditType(e.target.value as MemoryCandidateMemoryType)} disabled={busy} style={{ width: '100%' }}>
              {MEMORY_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
          <label style={{ fontSize: 12 }}>
            Tags
            <input value={editTags} onChange={e => setEditTags(e.target.value)} disabled={busy} style={{ width: '100%' }} />
          </label>
          <label style={{ fontSize: 12, gridColumn: '1 / span 2' }}>
            Title
            <input value={editTitle} onChange={e => setEditTitle(e.target.value)} disabled={busy} style={{ width: '100%' }} />
          </label>
          <label style={{ fontSize: 12, gridColumn: '1 / span 2' }}>
            Content
            <textarea value={editContent} onChange={e => setEditContent(e.target.value)} disabled={busy} rows={3} style={{ width: '100%' }} />
          </label>
        </div>
      )}
      {proposed && (
        <div style={{ marginTop: 6, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <button
            onClick={onApprove}
            disabled={busy}
            style={{ background: 'none', border: '1px solid #444', borderRadius: 4, padding: '2px 8px', cursor: 'pointer', fontSize: 11 }}
          >
            Approve
          </button>
          <button
            onClick={() => setShowReject(s => !s)}
            disabled={busy}
            style={{ background: 'none', border: '1px solid #444', borderRadius: 4, padding: '2px 8px', cursor: 'pointer', fontSize: 11 }}
          >
            {showReject ? 'Hide reject' : 'Reject'}
          </button>
          <button
            onClick={() => (editing ? handleEditSave() : setEditing(true))}
            disabled={busy}
            style={{ background: 'none', border: '1px solid #444', borderRadius: 4, padding: '2px 8px', cursor: 'pointer', fontSize: 11 }}
          >
            {editing ? 'Save' : 'Edit'}
          </button>
        </div>
      )}
      {showReject && proposed && (
        <div style={{ marginTop: 6, display: 'flex', gap: 6, alignItems: 'center' }}>
          <input
            value={rejectReason}
            onChange={e => setRejectReason(e.target.value)}
            placeholder="optional reason"
            style={{ flex: 1 }}
            disabled={busy}
          />
          <button
            onClick={() => { onReject(rejectReason); setShowReject(false); setRejectReason('') }}
            disabled={busy}
            style={{ background: 'none', border: '1px solid #444', borderRadius: 4, padding: '2px 8px', cursor: 'pointer', fontSize: 11 }}
          >
            Confirm reject
          </button>
        </div>
      )}
    </div>
  )
}
