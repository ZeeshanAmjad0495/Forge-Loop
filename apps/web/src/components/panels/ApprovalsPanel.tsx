import { useState } from 'react'
import { decideApproval } from '../../api'
import type { Approval } from '../../types'

export function ApprovalsPanel({
  projectId,
  approvals,
  onApprovalChange,
}: {
  projectId: string
  approvals: Approval[]
  onApprovalChange: () => void
}) {
  const [open, setOpen] = useState(false)
  const pending = approvals.filter(a => a.status === 'pending')

  return (
    <div style={{ marginTop: 16 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{ background: 'none', border: '1px solid #444', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: 13 }}
      >
        {open ? '▾' : '▸'} Approvals ({approvals.length}, {pending.length} pending)
      </button>
      {open && (
        <div style={{ marginTop: 8 }}>
          {approvals.length === 0 && <p style={{ fontSize: 13, color: '#888' }}>No approvals yet.</p>}
          {approvals.map(a => (
            <ApprovalRow key={a.id} approval={a} projectId={projectId} onChange={onApprovalChange} />
          ))}
        </div>
      )}
    </div>
  )
}

function ApprovalRow({
  approval,
  projectId: _projectId,
  onChange,
}: {
  approval: Approval
  projectId: string
  onChange: () => void
}) {
  const [feedback, setFeedback] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const isFinal = approval.status !== 'pending'

  async function decide(status: 'approved' | 'rejected' | 'needs_revision') {
    setBusy(true)
    setError(null)
    try {
      await decideApproval(approval.id, { status, feedback: feedback || null })
      onChange()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{ border: '1px solid #333', borderRadius: 4, padding: '8px 12px', marginBottom: 8, fontSize: 13 }}>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ color: '#aaa' }}>{approval.target_type}</span>
        <code style={{ fontSize: 11, color: '#888' }}>{approval.target_id.slice(0, 12)}…</code>
        <span className={`status${approval.status === 'approved' ? ' done' : ''}`}>{approval.status}</span>
        {approval.feedback && <span style={{ color: '#aaa' }}>{approval.feedback}</span>}
      </div>
      {!isFinal && (
        <div style={{ marginTop: 6, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            placeholder="Feedback (optional)"
            value={feedback}
            onChange={e => setFeedback(e.target.value)}
            style={{ fontSize: 12, padding: '2px 6px', background: '#1a1a1a', border: '1px solid #444', color: '#fff', borderRadius: 3 }}
          />
          <button onClick={() => decide('approved')} disabled={busy} style={{ fontSize: 12 }}>Approve</button>
          <button onClick={() => decide('rejected')} disabled={busy} style={{ fontSize: 12 }}>Reject</button>
          <button onClick={() => decide('needs_revision')} disabled={busy} style={{ fontSize: 12 }}>Needs revision</button>
        </div>
      )}
      {error && <div className="error" style={{ marginTop: 4 }}>{error}</div>}
    </div>
  )
}
