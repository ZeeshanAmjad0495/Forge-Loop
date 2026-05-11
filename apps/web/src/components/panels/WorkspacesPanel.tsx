import { useEffect, useState } from 'react'
import {
  archiveWorkspace,
  commitWorkspaceBranch,
  createWorkspace,
  createWorkspaceBranch,
  inspectWorkspace,
  inspectWorkspaceGit,
  listProjectWorkspaces,
  listWorkspaceBranches,
} from '../../api'
import type {
  CodeRepository,
  GitInspectionResponse,
  WorkspaceBranch,
  Workspace,
  WorkspaceInspection,
  WorkspaceStatus,
  WorkspaceType,
} from '../../types'
import { StatusBadge } from '../StatusBadge'

const STATUS_COLORS: Record<WorkspaceStatus, string> = {
  ready: '#5cd97a',
  registered: '#9ad3ff',
  missing: '#ff9b66',
  invalid: '#ff6b6b',
  archived: '#777',
}

const TYPE_OPTIONS: WorkspaceType[] = ['local_created', 'local_existing', 'manual']

export function WorkspacesPanel({
  projectId,
  codeRepos,
}: {
  projectId: string
  codeRepos: CodeRepository[]
}) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [loadError, setLoadError] = useState('')

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [codeRepositoryId, setCodeRepositoryId] = useState<string>('')
  const [workspaceType, setWorkspaceType] = useState<WorkspaceType>('local_created')
  const [rootPath, setRootPath] = useState('')
  const [createDirectory, setCreateDirectory] = useState(true)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')

  const [inspections, setInspections] = useState<Record<string, WorkspaceInspection>>({})
  const [inspecting, setInspecting] = useState<Record<string, boolean>>({})

  const [gitInspections, setGitInspections] = useState<Record<string, GitInspectionResponse>>({})
  const [gitInspecting, setGitInspecting] = useState<Record<string, boolean>>({})
  const [gitError, setGitError] = useState<Record<string, string>>({})
  const [branches, setBranches] = useState<Record<string, WorkspaceBranch[]>>({})
  const [branchBusy, setBranchBusy] = useState<Record<string, boolean>>({})
  const [branchDevTaskId, setBranchDevTaskId] = useState<Record<string, string>>({})
  const [branchName, setBranchName] = useState<Record<string, string>>({})
  const [commitMessage, setCommitMessage] = useState<Record<string, string>>({})
  const [commitBusy, setCommitBusy] = useState<Record<string, boolean>>({})
  const [commitError, setCommitError] = useState<Record<string, string>>({})

  useEffect(() => {
    listProjectWorkspaces(projectId)
      .then(setWorkspaces)
      .catch(err => setLoadError((err as Error).message))
  }, [projectId])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setCreateError('')
    setCreating(true)
    try {
      const created = await createWorkspace(projectId, {
        name: name.trim(),
        description: description.trim() || null,
        code_repository_id: codeRepositoryId || null,
        workspace_type: workspaceType,
        root_path: rootPath.trim() || null,
        create_directory: workspaceType === 'local_created' ? createDirectory : false,
      })
      setWorkspaces([...workspaces, created])
      setName('')
      setDescription('')
      setRootPath('')
      setCodeRepositoryId('')
      setWorkspaceType('local_created')
      setCreateDirectory(true)
    } catch (err) {
      setCreateError((err as Error).message)
    } finally {
      setCreating(false)
    }
  }

  async function handleInspect(workspace: Workspace) {
    setInspecting(prev => ({ ...prev, [workspace.id]: true }))
    try {
      const result = await inspectWorkspace(workspace.id)
      setInspections(prev => ({ ...prev, [workspace.id]: result }))
      const refreshed = await listProjectWorkspaces(projectId)
      setWorkspaces(refreshed)
    } catch (err) {
      setInspections(prev => ({
        ...prev,
        [workspace.id]: {
          workspace_id: workspace.id,
          exists: false,
          is_directory: false,
          is_git_repo: false,
          current_branch: null,
          dirty: false,
          file_count_estimate: 0,
          blocked_path_hits: [],
          notes: [(err as Error).message],
        },
      }))
    } finally {
      setInspecting(prev => ({ ...prev, [workspace.id]: false }))
    }
  }

  async function handleGitInspect(workspace: Workspace) {
    setGitError(prev => ({ ...prev, [workspace.id]: '' }))
    setGitInspecting(prev => ({ ...prev, [workspace.id]: true }))
    try {
      const result = await inspectWorkspaceGit(workspace.id)
      setGitInspections(prev => ({ ...prev, [workspace.id]: result }))
      try {
        const list = await listWorkspaceBranches(workspace.id)
        setBranches(prev => ({ ...prev, [workspace.id]: list }))
      } catch { /* non-critical */ }
    } catch (err) {
      setGitError(prev => ({ ...prev, [workspace.id]: (err as Error).message }))
    } finally {
      setGitInspecting(prev => ({ ...prev, [workspace.id]: false }))
    }
  }

  async function handleCreateBranch(workspace: Workspace) {
    setGitError(prev => ({ ...prev, [workspace.id]: '' }))
    setBranchBusy(prev => ({ ...prev, [workspace.id]: true }))
    try {
      const created = await createWorkspaceBranch(workspace.id, {
        dev_task_id: branchDevTaskId[workspace.id]?.trim() || null,
        name: branchName[workspace.id]?.trim() || null,
      })
      setBranches(prev => ({
        ...prev,
        [workspace.id]: [...(prev[workspace.id] ?? []), created.workspace_branch],
      }))
      setGitInspections(prev => ({ ...prev, [workspace.id]: created.inspection }))
      setBranchDevTaskId(prev => ({ ...prev, [workspace.id]: '' }))
      setBranchName(prev => ({ ...prev, [workspace.id]: '' }))
    } catch (err) {
      setGitError(prev => ({ ...prev, [workspace.id]: (err as Error).message }))
    } finally {
      setBranchBusy(prev => ({ ...prev, [workspace.id]: false }))
    }
  }

  async function handleCommitBranch(workspace: Workspace, branch: WorkspaceBranch) {
    const key = branch.id
    setCommitError(prev => ({ ...prev, [key]: '' }))
    setCommitBusy(prev => ({ ...prev, [key]: true }))
    try {
      await commitWorkspaceBranch(branch.id, {
        message: commitMessage[key]?.trim() || '',
      })
      setCommitMessage(prev => ({ ...prev, [key]: '' }))
      // Refresh branch list to pick up "committed" status.
      const list = await listWorkspaceBranches(workspace.id)
      setBranches(prev => ({ ...prev, [workspace.id]: list }))
      const gi = await inspectWorkspaceGit(workspace.id)
      setGitInspections(prev => ({ ...prev, [workspace.id]: gi }))
    } catch (err) {
      setCommitError(prev => ({ ...prev, [key]: (err as Error).message }))
    } finally {
      setCommitBusy(prev => ({ ...prev, [key]: false }))
    }
  }

  async function handleArchive(workspace: Workspace) {
    if (!window.confirm(`Archive workspace "${workspace.name}"? The directory is not deleted.`)) {
      return
    }
    try {
      const updated = await archiveWorkspace(workspace.id)
      setWorkspaces(workspaces.map(w => (w.id === updated.id ? updated : w)))
    } catch (err) {
      setLoadError((err as Error).message)
    }
  }

  function repoName(id: string | null): string {
    if (!id) return ''
    const r = codeRepos.find(c => c.id === id)
    return r ? r.name : id
  }

  return (
    <section>
      <h3>Workspaces</h3>
      <p style={{ fontSize: '0.85rem', color: '#888', marginTop: 0 }}>
        Local workspace metadata only. ForgeLoop does not run shell, git, or external tools here.
      </p>
      {loadError && <div className="error">{loadError}</div>}
      {workspaces.length > 0 ? (
        <ul style={{ listStyle: 'none', padding: 0 }}>
          {workspaces.map(w => {
            const inspection = inspections[w.id]
            return (
              <li
                key={w.id}
                style={{
                  padding: '8px',
                  marginBottom: '8px',
                  border: '1px solid #333',
                  borderRadius: 4,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <strong>{w.name}</strong>
                  <StatusBadge label={w.status} color={STATUS_COLORS[w.status] ?? '#aaa'} />
                  <StatusBadge label={w.workspace_type} color="#9ad3ff" />
                  {w.code_repository_id && (
                    <span style={{ fontSize: '0.8rem', color: '#aaa' }}>
                      repo: {repoName(w.code_repository_id)}
                    </span>
                  )}
                </div>
                <div style={{ fontFamily: 'monospace', fontSize: '0.8rem', marginTop: 4 }}>
                  {w.root_path}
                </div>
                {w.description && (
                  <div style={{ fontSize: '0.85rem', color: '#bbb', marginTop: 4 }}>{w.description}</div>
                )}
                {w.error_message && (
                  <div style={{ fontSize: '0.8rem', color: '#ff9b66', marginTop: 4 }}>
                    {w.error_message}
                  </div>
                )}
                {w.last_inspected_at && (
                  <div style={{ fontSize: '0.75rem', color: '#888', marginTop: 4 }}>
                    Last inspected: {new Date(w.last_inspected_at).toLocaleString()}
                  </div>
                )}
                <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
                  <button
                    type="button"
                    onClick={() => handleInspect(w)}
                    disabled={!!inspecting[w.id] || w.status === 'archived'}
                  >
                    {inspecting[w.id] ? 'Inspecting…' : 'Inspect'}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleArchive(w)}
                    disabled={w.status === 'archived'}
                  >
                    Archive
                  </button>
                </div>
                {inspection && (
                  <div
                    style={{
                      marginTop: 8,
                      padding: 8,
                      background: '#1c1c1c',
                      borderRadius: 4,
                      fontSize: '0.8rem',
                    }}
                  >
                    <div>exists: {String(inspection.exists)}</div>
                    <div>is_directory: {String(inspection.is_directory)}</div>
                    <div>is_git_repo: {String(inspection.is_git_repo)}</div>
                    <div>file_count_estimate: {inspection.file_count_estimate}</div>
                    {inspection.blocked_path_hits.length > 0 && (
                      <div>blocked_path_hits: {inspection.blocked_path_hits.join(', ')}</div>
                    )}
                    {inspection.notes.length > 0 && (
                      <div>notes: {inspection.notes.join('; ')}</div>
                    )}
                  </div>
                )}
                {/* Task 37: Git workflow */}
                <div
                  style={{
                    marginTop: 8,
                    padding: 8,
                    border: '1px dashed #2c2c2c',
                    borderRadius: 4,
                  }}
                >
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                    <strong style={{ fontSize: '0.8rem', color: '#aaa' }}>Git</strong>
                    <button
                      type="button"
                      onClick={() => handleGitInspect(w)}
                      disabled={!!gitInspecting[w.id] || w.status === 'archived'}
                      style={{ fontSize: 11, padding: '2px 8px' }}
                    >
                      {gitInspecting[w.id] ? 'Inspecting…' : 'Inspect git'}
                    </button>
                    <span style={{ fontSize: 10, color: '#c66' }}>
                      Local git only. No push, no GitHub PR, no merge — that is Task 38.
                    </span>
                  </div>
                  {gitError[w.id] && (
                    <div className="error" style={{ marginTop: 4, fontSize: 11 }}>
                      {gitError[w.id]}
                    </div>
                  )}
                  {gitInspections[w.id] && (
                    <div style={{ marginTop: 6, fontSize: 11, fontFamily: 'monospace' }}>
                      <div>is_git_repo: {String(gitInspections[w.id].is_git_repo)}</div>
                      <div>current_branch: {gitInspections[w.id].current_branch ?? '—'}</div>
                      <div>dirty: {String(gitInspections[w.id].dirty)}</div>
                      <div>changed: {gitInspections[w.id].changed_files.length} · untracked: {gitInspections[w.id].untracked_files.length}</div>
                      {gitInspections[w.id].diff_stat && (
                        <pre style={{
                          maxHeight: 140,
                          overflow: 'auto',
                          background: '#0e0e0e',
                          border: '1px solid #222',
                          borderRadius: 3,
                          padding: 6,
                          fontSize: 10,
                          margin: '4px 0 0',
                        }}>{gitInspections[w.id].diff_stat}</pre>
                      )}
                    </div>
                  )}
                  {gitInspections[w.id]?.is_git_repo && (
                    <div style={{ marginTop: 8, display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                      <input
                        placeholder="dev_task_id (optional)"
                        value={branchDevTaskId[w.id] ?? ''}
                        onChange={e => setBranchDevTaskId(prev => ({ ...prev, [w.id]: e.target.value }))}
                        disabled={!gitInspections[w.id].git_workflow_enabled || !!branchBusy[w.id]}
                        style={{ fontSize: 11, width: 200 }}
                      />
                      <input
                        placeholder="custom branch name (optional)"
                        value={branchName[w.id] ?? ''}
                        onChange={e => setBranchName(prev => ({ ...prev, [w.id]: e.target.value }))}
                        disabled={!gitInspections[w.id].git_workflow_enabled || !!branchBusy[w.id]}
                        style={{ fontSize: 11, width: 240 }}
                      />
                      <button
                        type="button"
                        onClick={() => handleCreateBranch(w)}
                        disabled={!gitInspections[w.id].git_workflow_enabled || !!branchBusy[w.id]}
                        title={
                          !gitInspections[w.id].git_workflow_enabled
                            ? 'Branch creation is disabled (GIT_WORKFLOW_ENABLED=false).'
                            : 'Create a ForgeLoop-scoped local branch.'
                        }
                        style={{ fontSize: 11 }}
                      >
                        {branchBusy[w.id] ? 'Creating…' : 'Create branch'}
                      </button>
                    </div>
                  )}
                  {(branches[w.id]?.length ?? 0) > 0 && (
                    <ul style={{ listStyle: 'none', padding: 0, marginTop: 8 }}>
                      {branches[w.id].map(b => (
                        <li
                          key={b.id}
                          style={{
                            padding: 6,
                            marginBottom: 6,
                            border: '1px solid #222',
                            borderRadius: 3,
                            fontSize: 11,
                          }}
                        >
                          <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                            <code>{b.name}</code>
                            <StatusBadge label={b.status} color="#9ad3ff" />
                            {b.base_branch && <span style={{ color: '#888' }}>base: {b.base_branch}</span>}
                          </div>
                          {b.error_message && (
                            <div className="error" style={{ marginTop: 2 }}>{b.error_message}</div>
                          )}
                          {b.status !== 'failed' && b.status !== 'archived' && (
                            <div style={{ marginTop: 4, display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                              <input
                                placeholder="commit message"
                                value={commitMessage[b.id] ?? ''}
                                onChange={e => setCommitMessage(prev => ({ ...prev, [b.id]: e.target.value }))}
                                disabled={!gitInspections[w.id]?.git_commit_enabled || !!commitBusy[b.id]}
                                style={{ fontSize: 11, width: 320 }}
                              />
                              <button
                                type="button"
                                onClick={() => handleCommitBranch(w, b)}
                                disabled={
                                  !gitInspections[w.id]?.git_commit_enabled
                                  || !!commitBusy[b.id]
                                  || !(commitMessage[b.id]?.trim())
                                }
                                title={
                                  !gitInspections[w.id]?.git_commit_enabled
                                    ? 'Commit is disabled (GIT_COMMIT_ENABLED=false).'
                                    : 'Local commit. No push, no PR.'
                                }
                                style={{ fontSize: 11 }}
                              >
                                {commitBusy[b.id] ? 'Committing…' : 'Commit (local)'}
                              </button>
                              {commitError[b.id] && (
                                <span className="error" style={{ fontSize: 11 }}>{commitError[b.id]}</span>
                              )}
                            </div>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      ) : (
        <p style={{ fontSize: '0.85rem', color: '#888' }}>No workspaces yet.</p>
      )}

      <form onSubmit={handleCreate} style={{ marginTop: 12 }}>
        <h4 style={{ marginBottom: 6 }}>Create workspace</h4>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          <label style={{ fontSize: '0.85rem' }}>
            Name
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              disabled={creating}
              required
              style={{ width: '100%' }}
            />
          </label>
          <label style={{ fontSize: '0.85rem' }}>
            Type
            <select
              value={workspaceType}
              onChange={e => setWorkspaceType(e.target.value as WorkspaceType)}
              disabled={creating}
              style={{ width: '100%' }}
            >
              {TYPE_OPTIONS.map(t => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </label>
          <label style={{ fontSize: '0.85rem' }}>
            Code repository (optional)
            <select
              value={codeRepositoryId}
              onChange={e => setCodeRepositoryId(e.target.value)}
              disabled={creating}
              style={{ width: '100%' }}
            >
              <option value="">(none)</option>
              {codeRepos.map(r => (
                <option key={r.id} value={r.id}>{r.name}</option>
              ))}
            </select>
          </label>
          <label style={{ fontSize: '0.85rem' }}>
            Root path {workspaceType === 'local_existing' ? '(required)' : '(optional)'}
            <input
              value={rootPath}
              onChange={e => setRootPath(e.target.value)}
              disabled={creating}
              placeholder={workspaceType === 'local_created' ? 'leave blank to use workspace root' : ''}
              style={{ width: '100%', fontFamily: 'monospace' }}
            />
          </label>
        </div>
        <div style={{ marginTop: 6 }}>
          <label style={{ fontSize: '0.85rem' }}>
            Description
            <input
              value={description}
              onChange={e => setDescription(e.target.value)}
              disabled={creating}
              style={{ width: '100%' }}
            />
          </label>
        </div>
        {workspaceType === 'local_created' && (
          <label style={{ fontSize: '0.85rem', marginTop: 6, display: 'block' }}>
            <input
              type="checkbox"
              checked={createDirectory}
              onChange={e => setCreateDirectory(e.target.checked)}
              disabled={creating}
            />{' '}
            Create empty directory now
          </label>
        )}
        <div style={{ marginTop: 8 }}>
          <button type="submit" disabled={creating || !name.trim()}>
            {creating ? 'Creating…' : 'Create workspace'}
          </button>
          {createError && <span className="error" style={{ marginLeft: 8 }}>{createError}</span>}
        </div>
      </form>
    </section>
  )
}
