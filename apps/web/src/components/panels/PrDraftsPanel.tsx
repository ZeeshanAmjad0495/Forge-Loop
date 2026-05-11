import { useEffect, useState } from 'react'
import {
  approvePullRequestDraft,
  listProjectPullRequestDrafts,
  updatePullRequestDraft,
} from '../../api'
import type {
  CodeRepository,
  PullRequestDraft,
} from '../../types'
import { PullRequestReviewsPanel } from './PrReviewsPanel'

export function PullRequestDraftsPanel({
  projectId,
  codeRepos,
}: {
  projectId: string
  codeRepos: CodeRepository[]
}) {
  const [open, setOpen] = useState(false)
  const [drafts, setDrafts] = useState<PullRequestDraft[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    listProjectPullRequestDrafts(projectId).then(setDrafts).catch(() => {})
  }, [open, projectId])

  async function refresh() {
    try {
      setDrafts(await listProjectPullRequestDrafts(projectId))
    } catch { /* non-critical */ }
  }

  async function handleApprove(draft: PullRequestDraft) {
    setBusy(true)
    setError('')
    try {
      const updated = await approvePullRequestDraft(draft.id)
      setDrafts(prev => prev.map(d => d.id === updated.id ? updated : d))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function handleSaveUrl(draft: PullRequestDraft, url: string, num: string) {
    setBusy(true)
    setError('')
    try {
      const updated = await updatePullRequestDraft(draft.id, {
        external_pr_url: url || null,
        external_pr_number: num ? Number(num) : null,
      })
      setDrafts(prev => prev.map(d => d.id === updated.id ? updated : d))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function handleMarkCreated(draft: PullRequestDraft) {
    setBusy(true)
    setError('')
    try {
      const updated = await updatePullRequestDraft(draft.id, { status: 'created' })
      setDrafts(prev => prev.map(d => d.id === updated.id ? updated : d))
    } catch (e) {
      setError((e as Error).message)
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
        {open ? '▾' : '▸'} PR drafts ({drafts.length})
      </button>
      {open && (
        <div style={{ marginTop: 12 }}>
          <p style={{ fontSize: 12, color: '#888', margin: '0 0 8px' }}>
            ForgeLoop tracks PR drafts as metadata only — no GitHub API is called.
            Use the generated title/body when opening the PR manually. Codebase has {codeRepos.length} repo(s) registered.
          </p>
          {error && <div className="error" style={{ marginBottom: 6, fontSize: 12 }}>{error}</div>}
          {drafts.length === 0
            ? <p style={{ fontSize: 12, color: '#666' }}>No PR drafts yet. Use the "Prepare PR draft" button on a dev task.</p>
            : drafts.map(d => (
                <PullRequestDraftCard
                  key={d.id}
                  draft={d}
                  busy={busy}
                  onApprove={() => handleApprove(d)}
                  onSaveUrl={(url, num) => handleSaveUrl(d, url, num)}
                  onMarkCreated={() => handleMarkCreated(d)}
                  onRefresh={refresh}
                />
              ))
          }
        </div>
      )}
    </section>
  )
}

function PullRequestDraftCard({
  draft,
  busy,
  onApprove,
  onSaveUrl,
  onMarkCreated,
  onRefresh,
}: {
  draft: PullRequestDraft
  busy: boolean
  onApprove: () => void
  onSaveUrl: (url: string, num: string) => void
  onMarkCreated: () => void
  onRefresh: () => void
}) {
  const [showBody, setShowBody] = useState(false)
  const [url, setUrl] = useState(draft.external_pr_url ?? '')
  const [num, setNum] = useState(draft.external_pr_number ? String(draft.external_pr_number) : '')

  return (
    <div style={{ border: '1px solid #333', borderRadius: 4, padding: '8px 12px', marginBottom: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <strong style={{ fontSize: 13 }}>{draft.title}</strong>
        <span className="status" style={{ fontSize: 11 }}>{draft.status}</span>
        <span className="status" style={{ fontSize: 11 }}>{draft.provider}</span>
        <span style={{ fontSize: 11, color: '#888' }}>
          {draft.source_branch} → {draft.target_branch}
        </span>
      </div>
      <div style={{ marginTop: 6 }}>
        <button
          onClick={() => setShowBody(s => !s)}
          style={{ fontSize: 11, padding: '2px 6px' }}
        >
          {showBody ? 'Hide body' : 'Show body'}
        </button>
        {draft.status === 'draft_prepared' && (
          <button onClick={onApprove} disabled={busy} style={{ fontSize: 11, marginLeft: 6 }}>
            Approve for creation
          </button>
        )}
        {draft.status === 'approved_for_creation' && (
          <button onClick={onMarkCreated} disabled={busy} style={{ fontSize: 11, marginLeft: 6 }}>
            Mark created
          </button>
        )}
        <button onClick={onRefresh} disabled={busy} style={{ fontSize: 11, marginLeft: 6 }}>
          Refresh
        </button>
      </div>
      {showBody && (
        <pre style={{
          marginTop: 6,
          maxHeight: 260,
          overflow: 'auto',
          background: '#0e0e0e',
          border: '1px solid #222',
          borderRadius: 3,
          padding: 6,
          fontSize: 11,
        }}>{draft.body}</pre>
      )}
      <div style={{ marginTop: 6, display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
        <label style={{ fontSize: 11 }}>External PR URL:
          <input
            value={url}
            onChange={e => setUrl(e.target.value)}
            placeholder="https://github.com/org/repo/pull/123"
            style={{ marginLeft: 4, fontSize: 11, padding: '2px 4px', background: '#1a1a1a', border: '1px solid #444', color: '#fff', borderRadius: 3, width: 280 }}
          />
        </label>
        <label style={{ fontSize: 11 }}>#:
          <input
            value={num}
            onChange={e => setNum(e.target.value)}
            placeholder="123"
            style={{ marginLeft: 4, fontSize: 11, padding: '2px 4px', background: '#1a1a1a', border: '1px solid #444', color: '#fff', borderRadius: 3, width: 60 }}
          />
        </label>
        <button onClick={() => onSaveUrl(url, num)} disabled={busy} style={{ fontSize: 11 }}>
          Save URL
        </button>
      </div>
      <PullRequestReviewsPanel prDraftId={draft.id} />
    </div>
  )
}
