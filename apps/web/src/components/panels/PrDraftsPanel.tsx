import { useEffect, useState } from 'react'
import {
  approvePullRequestDraft,
  createGitHubDraftPr,
  listProjectPullRequestDrafts,
  listProjectWorkspaces,
  listWorkspaceBranches,
  updatePullRequestDraft,
} from '../../api'
import type {
  CodeRepository,
  GitHubPublicationSummary,
  PullRequestDraft,
  Workspace,
  WorkspaceBranch,
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

  function handleDraftReplaced(updated: PullRequestDraft) {
    setDrafts(prev => prev.map(d => d.id === updated.id ? updated : d))
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
                  projectId={projectId}
                  draft={d}
                  busy={busy}
                  onApprove={() => handleApprove(d)}
                  onSaveUrl={(url, num) => handleSaveUrl(d, url, num)}
                  onMarkCreated={() => handleMarkCreated(d)}
                  onRefresh={refresh}
                  onDraftReplaced={handleDraftReplaced}
                />
              ))
          }
        </div>
      )}
    </section>
  )
}

function PullRequestDraftCard({
  projectId,
  draft,
  busy,
  onApprove,
  onSaveUrl,
  onMarkCreated,
  onRefresh,
  onDraftReplaced,
}: {
  projectId: string
  draft: PullRequestDraft
  busy: boolean
  onApprove: () => void
  onSaveUrl: (url: string, num: string) => void
  onMarkCreated: () => void
  onRefresh: () => void
  onDraftReplaced: (updated: PullRequestDraft) => void
}) {
  const [showBody, setShowBody] = useState(false)
  const [url, setUrl] = useState(draft.external_pr_url ?? '')
  const [num, setNum] = useState(draft.external_pr_number ? String(draft.external_pr_number) : '')

  const [ghWorkspaces, setGhWorkspaces] = useState<Workspace[]>([])
  const [ghBranches, setGhBranches] = useState<WorkspaceBranch[]>([])
  const [ghWorkspaceId, setGhWorkspaceId] = useState('')
  const [ghBranchId, setGhBranchId] = useState('')
  const [ghPushBranch, setGhPushBranch] = useState(true)
  const [ghBusy, setGhBusy] = useState(false)
  const [ghError, setGhError] = useState('')
  const [ghSummary, setGhSummary] = useState<GitHubPublicationSummary | null>(null)

  async function loadGhContext() {
    setGhError('')
    try {
      const ws = await listProjectWorkspaces(projectId)
      const ready = ws.filter(w => w.status === 'ready')
      setGhWorkspaces(ready)
      if (ready.length === 1) setGhWorkspaceId(ready[0].id)
    } catch (e) {
      setGhError((e as Error).message)
    }
  }

  async function loadGhBranches(workspaceId: string) {
    if (!workspaceId) {
      setGhBranches([])
      setGhBranchId('')
      return
    }
    try {
      const bs = await listWorkspaceBranches(workspaceId)
      const live = bs.filter(b => b.status !== 'failed' && b.status !== 'archived')
      setGhBranches(live)
      if (live.length === 1) setGhBranchId(live[0].id)
    } catch (e) {
      setGhBranches([])
      setGhError((e as Error).message)
    }
  }

  async function handleCreateGitHubDraft() {
    if (!ghWorkspaceId || !ghBranchId) return
    setGhBusy(true)
    setGhError('')
    setGhSummary(null)
    try {
      const resp = await createGitHubDraftPr(draft.id, {
        workspace_id: ghWorkspaceId,
        workspace_branch_id: ghBranchId,
        push_branch: ghPushBranch,
        draft: true,
      })
      setGhSummary(resp.publication_summary)
      onDraftReplaced(resp.pr_draft)
    } catch (e) {
      setGhError((e as Error).message)
    } finally {
      setGhBusy(false)
    }
  }

  return (
    <div style={{ border: '1px solid #333', borderRadius: 4, padding: '8px 12px', marginBottom: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <strong style={{ fontSize: 13 }}>{draft.title}</strong>
        <span className="status" style={{ fontSize: 11 }}>{draft.status}</span>
        <span className="status" style={{ fontSize: 11 }}>{draft.provider}</span>
        <span style={{ fontSize: 11, color: '#888' }}>
          {draft.source_branch} → {draft.target_branch}
        </span>
        {draft.external_pr_url && (
          <a
            href={draft.external_pr_url}
            target="_blank"
            rel="noreferrer"
            style={{ fontSize: 11, color: '#9ad3ff' }}
          >
            PR #{draft.external_pr_number}
          </a>
        )}
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
      {draft.status === 'approved_for_creation' && (
        <div
          style={{
            marginTop: 8,
            padding: '6px 8px',
            border: '1px solid #3a1d1d',
            borderRadius: 3,
            background: '#1a1010',
          }}
        >
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <strong style={{ fontSize: 11, color: '#e58' }}>Create GitHub draft PR</strong>
            <button
              type="button"
              onClick={loadGhContext}
              disabled={ghBusy}
              style={{ fontSize: 11, padding: '2px 8px' }}
            >
              Load workspaces
            </button>
            {ghWorkspaces.length > 0 && (
              <>
                <select
                  value={ghWorkspaceId}
                  onChange={e => {
                    setGhWorkspaceId(e.target.value)
                    loadGhBranches(e.target.value)
                  }}
                  disabled={ghBusy}
                  style={{ fontSize: 11 }}
                >
                  <option value="">— select workspace —</option>
                  {ghWorkspaces.map(w => (
                    <option key={w.id} value={w.id}>{w.name}</option>
                  ))}
                </select>
                <select
                  value={ghBranchId}
                  onChange={e => setGhBranchId(e.target.value)}
                  disabled={ghBusy || !ghWorkspaceId}
                  style={{ fontSize: 11 }}
                >
                  <option value="">— select branch —</option>
                  {ghBranches.map(b => (
                    <option key={b.id} value={b.id}>{b.name} [{b.status}]</option>
                  ))}
                </select>
                <label style={{ fontSize: 11 }}>
                  <input
                    type="checkbox"
                    checked={ghPushBranch}
                    onChange={e => setGhPushBranch(e.target.checked)}
                    disabled={ghBusy}
                  />{' '}
                  push branch
                </label>
                <button
                  type="button"
                  onClick={handleCreateGitHubDraft}
                  disabled={ghBusy || !ghWorkspaceId || !ghBranchId}
                  style={{ fontSize: 11 }}
                >
                  {ghBusy ? 'Publishing…' : 'Create GitHub draft PR'}
                </button>
              </>
            )}
          </div>
          <div style={{ marginTop: 4, fontSize: 10, color: '#c66' }}>
            Creates a remote branch and a GitHub draft PR. Does not merge or deploy. Human review still required.
          </div>
          {ghError && (
            <div className="error" style={{ marginTop: 4, fontSize: 11 }}>{ghError}</div>
          )}
          {ghSummary && (
            <div style={{ marginTop: 4, fontSize: 11 }}>
              Pushed: <code>{String(ghSummary.pushed)}</code> · PR{' '}
              <a href={ghSummary.external_pr_url} target="_blank" rel="noreferrer" style={{ color: '#9ad3ff' }}>
                #{ghSummary.external_pr_number}
              </a>{' '}
              ({ghSummary.github_owner}/{ghSummary.github_repo}) head={ghSummary.head} base={ghSummary.base}
            </div>
          )}
        </div>
      )}
      <PullRequestReviewsPanel prDraftId={draft.id} />
    </div>
  )
}
