import { useEffect, useState } from 'react'
import {
  createCodeRepository,
  getRepoSafetyProfile,
  updateCodeRepository,
  updateRepoSafetyProfile,
} from '../../api'
import type {
  CodeRepository,
  CodeRepositoryProvider,
  RepoSafetyProfile,
} from '../../types'
import { splitLines } from '../../lib/formatting'

function RepoSafetyProfileEditor({ repoId }: { repoId: string }) {
  const [profile, setProfile] = useState<RepoSafetyProfile | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')

  const [workSafeMode, setWorkSafeMode] = useState(true)
  const [allowedActions, setAllowedActions] = useState('')
  const [blockedPaths, setBlockedPaths] = useState('')
  const [requiredChecks, setRequiredChecks] = useState('')
  const [requiresApprovalFor, setRequiresApprovalFor] = useState('')
  const [protectedBranches, setProtectedBranches] = useState('')
  const [notes, setNotes] = useState('')

  useEffect(() => {
    getRepoSafetyProfile(repoId)
      .then(p => {
        setProfile(p)
        setWorkSafeMode(p.work_safe_mode)
        setAllowedActions(p.allowed_actions.join('\n'))
        setBlockedPaths(p.blocked_paths.join('\n'))
        setRequiredChecks(p.required_checks.join('\n'))
        setRequiresApprovalFor(p.requires_approval_for.join('\n'))
        setProtectedBranches(p.protected_branches.join('\n'))
        setNotes(p.notes)
      })
      .catch(() => setError('Failed to load safety profile'))
  }, [repoId])

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setSaved(false)
    setError('')
    try {
      const updated = await updateRepoSafetyProfile(repoId, {
        work_safe_mode: workSafeMode,
        allowed_actions: splitLines(allowedActions),
        blocked_paths: splitLines(blockedPaths),
        required_checks: splitLines(requiredChecks),
        requires_approval_for: splitLines(requiresApprovalFor),
        protected_branches: splitLines(protectedBranches),
        notes: notes.trim(),
      })
      setProfile(updated)
      setSaved(true)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  if (!profile && !error) return <p style={{ fontSize: '0.85rem', color: '#888' }}>Loading safety profile…</p>

  return (
    <div style={{ marginTop: '8px', paddingLeft: '12px', borderLeft: '2px solid #444' }}>
      <h5 style={{ margin: '0 0 8px' }}>Safety profile</h5>
      {error && <div className="error">{error}</div>}
      <form onSubmit={handleSave}>
        <label>
          <input
            type="checkbox"
            checked={workSafeMode}
            onChange={e => setWorkSafeMode(e.target.checked)}
            disabled={saving}
          />{' '}
          Work-safe mode
        </label>
        {(
          [
            ['Allowed actions', allowedActions, setAllowedActions],
            ['Blocked paths', blockedPaths, setBlockedPaths],
            ['Required checks', requiredChecks, setRequiredChecks],
            ['Requires approval for', requiresApprovalFor, setRequiresApprovalFor],
            ['Protected branches', protectedBranches, setProtectedBranches],
          ] as [string, string, (v: string) => void][]
        ).map(([label, value, setter]) => (
          <div key={label} style={{ marginTop: '6px' }}>
            <label style={{ fontSize: '0.85rem' }}>{label} (one per line)</label>
            <textarea
              value={value}
              onChange={e => setter(e.target.value)}
              disabled={saving}
              rows={3}
              style={{ width: '100%', fontFamily: 'monospace', fontSize: '0.8rem' }}
            />
          </div>
        ))}
        <div style={{ marginTop: '6px' }}>
          <label style={{ fontSize: '0.85rem' }}>Notes</label>
          <textarea
            value={notes}
            onChange={e => setNotes(e.target.value)}
            disabled={saving}
            rows={2}
            style={{ width: '100%', fontSize: '0.85rem' }}
          />
        </div>
        <div style={{ marginTop: '8px' }}>
          <button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save profile'}</button>
          {saved && <span className="ctx-saved" style={{ marginLeft: '8px' }}>Saved</span>}
        </div>
      </form>
    </div>
  )
}

export function CodeRepositoriesPanel({
  projectId,
  repos,
  onReposChange,
}: {
  projectId: string
  repos: CodeRepository[]
  onReposChange: (repos: CodeRepository[]) => void
}) {
  const [provider, setProvider] = useState<CodeRepositoryProvider>('github')
  const [repoUrl, setRepoUrl] = useState('')
  const [name, setName] = useState('')
  const [defaultBranch, setDefaultBranch] = useState('main')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')
  const [expandedRepoId, setExpandedRepoId] = useState<string | null>(null)

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setCreateError('')
    setCreating(true)
    try {
      const created = await createCodeRepository(projectId, {
        provider,
        repo_url: repoUrl.trim(),
        name: name.trim(),
        default_branch: defaultBranch.trim() || 'main',
      })
      onReposChange([...repos, created])
      setRepoUrl('')
      setName('')
      setDefaultBranch('main')
    } catch (err) {
      setCreateError((err as Error).message)
    } finally {
      setCreating(false)
    }
  }

  async function handleDisable(repo: CodeRepository) {
    try {
      const updated = await updateCodeRepository(repo.id, { status: 'disabled' })
      onReposChange(repos.map(r => r.id === updated.id ? updated : r))
    } catch { /* non-critical */ }
  }

  async function handleEnable(repo: CodeRepository) {
    try {
      const updated = await updateCodeRepository(repo.id, { status: 'active' })
      onReposChange(repos.map(r => r.id === updated.id ? updated : r))
    } catch { /* non-critical */ }
  }

  return (
    <section>
      <h3>Code repositories</h3>
      {repos.length > 0 && (
        <div style={{ marginBottom: '16px' }}>
          {repos.map(r => (
            <div key={r.id} style={{ marginBottom: '12px', padding: '10px', background: '#1e1e1e', borderRadius: '6px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <strong>{r.name}</strong>{' '}
                  <span style={{ fontSize: '0.8rem', color: '#888' }}>{r.provider} · {r.default_branch}</span>{' '}
                  <span style={{ fontSize: '0.8rem', color: r.status === 'active' ? '#4caf50' : '#f44336' }}>
                    {r.status}
                  </span>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    style={{ fontSize: '0.8rem' }}
                    onClick={() => setExpandedRepoId(expandedRepoId === r.id ? null : r.id)}
                  >
                    {expandedRepoId === r.id ? 'Hide profile' : 'Safety profile'}
                  </button>
                  {r.status === 'active'
                    ? <button style={{ fontSize: '0.8rem' }} onClick={() => handleDisable(r)}>Disable</button>
                    : <button style={{ fontSize: '0.8rem' }} onClick={() => handleEnable(r)}>Enable</button>
                  }
                </div>
              </div>
              <div style={{ fontSize: '0.8rem', color: '#888', marginTop: '4px' }}>{r.repo_url}</div>
              {expandedRepoId === r.id && <RepoSafetyProfileEditor repoId={r.id} />}
            </div>
          ))}
        </div>
      )}

      <h4>Add repository</h4>
      <form onSubmit={handleCreate}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
          <div>
            <label htmlFor="repo-provider">Provider</label>
            <select
              id="repo-provider"
              value={provider}
              onChange={e => setProvider(e.target.value as CodeRepositoryProvider)}
              disabled={creating}
            >
              <option value="github">GitHub</option>
              <option value="gitlab">GitLab</option>
              <option value="bitbucket">Bitbucket</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div>
            <label htmlFor="repo-branch">Default branch</label>
            <input
              id="repo-branch"
              value={defaultBranch}
              onChange={e => setDefaultBranch(e.target.value)}
              placeholder="main"
              disabled={creating}
            />
          </div>
        </div>
        <label htmlFor="repo-name">Name</label>
        <input
          id="repo-name"
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="my-repo"
          required
          disabled={creating}
        />
        <label htmlFor="repo-url">Repository URL</label>
        <input
          id="repo-url"
          value={repoUrl}
          onChange={e => setRepoUrl(e.target.value)}
          placeholder="https://github.com/org/repo"
          required
          disabled={creating}
        />
        {createError && <div className="error">{createError}</div>}
        <button type="submit" disabled={creating}>{creating ? 'Adding…' : 'Add repository'}</button>
      </form>
    </section>
  )
}
