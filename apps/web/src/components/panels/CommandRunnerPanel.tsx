import { useEffect, useState } from 'react'
import {
  createCommandDefinition,
  listProjectCommandDefinitions,
  listProjectCommandRuns,
  patchCommandDefinition,
  runCommandInWorkspace,
} from '../../api'
import type {
  CommandDefinition,
  CommandRun,
  CommandRunStatus,
  CommandType,
  Workspace,
} from '../../types'
import { StatusBadge } from '../StatusBadge'

const TYPE_OPTIONS: CommandType[] = [
  'test',
  'build',
  'lint',
  'typecheck',
  'coverage',
  'security_scan',
  'utility',
  'custom',
]

const STATUS_COLORS: Record<CommandRunStatus, string> = {
  pending: '#9ad3ff',
  running: '#9ad3ff',
  completed: '#5cd97a',
  failed: '#ff6b6b',
  timed_out: '#ff9b66',
  blocked: '#ff9b66',
  cancelled: '#888',
}

export function CommandRunnerPanel({
  projectId,
  workspaces,
}: {
  projectId: string
  workspaces: Workspace[]
}) {
  const [definitions, setDefinitions] = useState<CommandDefinition[]>([])
  const [runs, setRuns] = useState<CommandRun[]>([])
  const [loadError, setLoadError] = useState('')

  const [name, setName] = useState('')
  const [command, setCommand] = useState('')
  const [argsRaw, setArgsRaw] = useState('')
  const [commandType, setCommandType] = useState<CommandType>('custom')
  const [timeoutSeconds, setTimeoutSeconds] = useState<number>(60)
  const [workingDirectory, setWorkingDirectory] = useState<string>('')
  const [description, setDescription] = useState<string>('')
  const [workspaceForDef, setWorkspaceForDef] = useState<string>('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')

  const [runWorkspace, setRunWorkspace] = useState<Record<string, string>>({})
  const [running, setRunning] = useState<Record<string, boolean>>({})
  const [runError, setRunError] = useState<Record<string, string>>({})

  function refresh() {
    listProjectCommandDefinitions(projectId)
      .then(setDefinitions)
      .catch(err => setLoadError((err as Error).message))
    listProjectCommandRuns(projectId)
      .then(rs => setRuns([...rs].sort((a, b) => b.created_at.localeCompare(a.created_at))))
      .catch(err => setLoadError((err as Error).message))
  }

  useEffect(() => {
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  function parseArgs(raw: string): string[] {
    return raw
      .split(',')
      .map(s => s.trim())
      .filter(s => s.length > 0)
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setCreateError('')
    setCreating(true)
    try {
      await createCommandDefinition(projectId, {
        name: name.trim(),
        command: command.trim(),
        args: parseArgs(argsRaw),
        command_type: commandType,
        timeout_seconds: timeoutSeconds,
        working_directory: workingDirectory.trim() || null,
        description: description.trim() || null,
        workspace_id: workspaceForDef || null,
      })
      setName('')
      setCommand('')
      setArgsRaw('')
      setCommandType('custom')
      setTimeoutSeconds(60)
      setWorkingDirectory('')
      setDescription('')
      setWorkspaceForDef('')
      refresh()
    } catch (err) {
      setCreateError((err as Error).message)
    } finally {
      setCreating(false)
    }
  }

  async function toggleEnabled(def: CommandDefinition) {
    try {
      await patchCommandDefinition(def.id, { enabled: !def.enabled })
      refresh()
    } catch (err) {
      setLoadError((err as Error).message)
    }
  }

  async function handleRun(def: CommandDefinition) {
    const workspaceId = runWorkspace[def.id] || def.workspace_id || ''
    if (!workspaceId) {
      setRunError(prev => ({ ...prev, [def.id]: 'select a workspace' }))
      return
    }
    setRunError(prev => ({ ...prev, [def.id]: '' }))
    setRunning(prev => ({ ...prev, [def.id]: true }))
    try {
      await runCommandInWorkspace(workspaceId, { command_definition_id: def.id })
      refresh()
    } catch (err) {
      setRunError(prev => ({ ...prev, [def.id]: (err as Error).message }))
    } finally {
      setRunning(prev => ({ ...prev, [def.id]: false }))
    }
  }

  function workspaceName(id: string | null): string {
    if (!id) return '(any)'
    const w = workspaces.find(x => x.id === id)
    return w ? w.name : id
  }

  return (
    <section>
      <h3>Command Runner</h3>
      <p style={{ fontSize: '0.85rem', color: '#888', marginTop: 0 }}>
        Workspace-scoped, allowlist-based commands. Disabled by default — set
        COMMAND_RUNNER_ENABLED=true in backend env to execute runs. No shell, no git, no
        deploy.
      </p>
      {loadError && <div className="error">{loadError}</div>}

      <h4 style={{ marginBottom: 6 }}>Command definitions</h4>
      {definitions.length > 0 ? (
        <ul style={{ listStyle: 'none', padding: 0 }}>
          {definitions.map(def => (
            <li
              key={def.id}
              style={{
                padding: 8,
                marginBottom: 8,
                border: '1px solid #333',
                borderRadius: 4,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <strong>{def.name}</strong>
                <StatusBadge label={def.command_type} color="#9ad3ff" />
                <StatusBadge
                  label={def.enabled ? 'enabled' : 'disabled'}
                  color={def.enabled ? '#5cd97a' : '#777'}
                />
                <span style={{ fontSize: '0.8rem', color: '#aaa' }}>
                  workspace: {workspaceName(def.workspace_id)}
                </span>
              </div>
              <div style={{ fontFamily: 'monospace', fontSize: '0.8rem', marginTop: 4 }}>
                {def.command} {def.args.join(' ')}
              </div>
              {def.working_directory && (
                <div style={{ fontSize: '0.75rem', color: '#888', marginTop: 2 }}>
                  cwd: {def.working_directory}
                </div>
              )}
              {def.description && (
                <div style={{ fontSize: '0.85rem', color: '#bbb', marginTop: 4 }}>
                  {def.description}
                </div>
              )}
              <div style={{ marginTop: 8, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <button type="button" onClick={() => toggleEnabled(def)}>
                  {def.enabled ? 'Disable' : 'Enable'}
                </button>
                <select
                  value={runWorkspace[def.id] ?? def.workspace_id ?? ''}
                  onChange={e => setRunWorkspace(prev => ({ ...prev, [def.id]: e.target.value }))}
                >
                  <option value="">(select workspace)</option>
                  {workspaces.map(w => (
                    <option key={w.id} value={w.id}>
                      {w.name}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => handleRun(def)}
                  disabled={!def.enabled || !!running[def.id]}
                >
                  {running[def.id] ? 'Running…' : 'Run'}
                </button>
                {runError[def.id] && <span className="error">{runError[def.id]}</span>}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p style={{ fontSize: '0.85rem', color: '#888' }}>No command definitions yet.</p>
      )}

      <form onSubmit={handleCreate} style={{ marginTop: 12 }}>
        <h4 style={{ marginBottom: 6 }}>New command definition</h4>
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
              value={commandType}
              onChange={e => setCommandType(e.target.value as CommandType)}
              disabled={creating}
              style={{ width: '100%' }}
            >
              {TYPE_OPTIONS.map(t => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <label style={{ fontSize: '0.85rem' }}>
            Command (executable name only)
            <input
              value={command}
              onChange={e => setCommand(e.target.value)}
              disabled={creating}
              required
              placeholder="pytest"
              style={{ width: '100%', fontFamily: 'monospace' }}
            />
          </label>
          <label style={{ fontSize: '0.85rem' }}>
            Args (comma-separated)
            <input
              value={argsRaw}
              onChange={e => setArgsRaw(e.target.value)}
              disabled={creating}
              placeholder="-q, --tb=short"
              style={{ width: '100%', fontFamily: 'monospace' }}
            />
          </label>
          <label style={{ fontSize: '0.85rem' }}>
            Timeout (seconds)
            <input
              type="number"
              min={1}
              max={3600}
              value={timeoutSeconds}
              onChange={e => setTimeoutSeconds(Number(e.target.value) || 60)}
              disabled={creating}
              style={{ width: '100%' }}
            />
          </label>
          <label style={{ fontSize: '0.85rem' }}>
            Working directory (relative, optional)
            <input
              value={workingDirectory}
              onChange={e => setWorkingDirectory(e.target.value)}
              disabled={creating}
              style={{ width: '100%', fontFamily: 'monospace' }}
            />
          </label>
          <label style={{ fontSize: '0.85rem' }}>
            Bound workspace (optional)
            <select
              value={workspaceForDef}
              onChange={e => setWorkspaceForDef(e.target.value)}
              disabled={creating}
              style={{ width: '100%' }}
            >
              <option value="">(any workspace in project)</option>
              {workspaces.map(w => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
          </label>
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
        <div style={{ marginTop: 8 }}>
          <button type="submit" disabled={creating || !name.trim() || !command.trim()}>
            {creating ? 'Creating…' : 'Create command definition'}
          </button>
          {createError && <span className="error" style={{ marginLeft: 8 }}>{createError}</span>}
        </div>
      </form>

      <h4 style={{ marginTop: 16, marginBottom: 6 }}>Recent command runs</h4>
      {runs.length > 0 ? (
        <ul style={{ listStyle: 'none', padding: 0 }}>
          {runs.slice(0, 20).map(run => (
            <li
              key={run.id}
              style={{
                padding: 8,
                marginBottom: 8,
                border: '1px solid #333',
                borderRadius: 4,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <StatusBadge label={run.status} color={STATUS_COLORS[run.status] ?? '#aaa'} />
                {run.conclusion && (
                  <StatusBadge label={run.conclusion} color="#9ad3ff" />
                )}
                {typeof run.exit_code === 'number' && (
                  <span style={{ fontSize: '0.8rem', color: '#aaa' }}>
                    exit: {run.exit_code}
                  </span>
                )}
                <span style={{ fontSize: '0.8rem', color: '#aaa' }}>
                  workspace: {workspaceName(run.workspace_id)}
                </span>
              </div>
              <div style={{ fontFamily: 'monospace', fontSize: '0.8rem', marginTop: 4 }}>
                {run.command} {run.args.join(' ')}
              </div>
              {run.error_message && (
                <div style={{ fontSize: '0.8rem', color: '#ff9b66', marginTop: 4 }}>
                  {run.error_message}
                </div>
              )}
              {(run.stdout || run.stderr) && (
                <details style={{ marginTop: 6 }}>
                  <summary style={{ cursor: 'pointer', fontSize: '0.8rem' }}>output</summary>
                  {run.stdout && (
                    <pre
                      style={{
                        background: '#1c1c1c',
                        padding: 6,
                        fontSize: '0.75rem',
                        whiteSpace: 'pre-wrap',
                        marginTop: 4,
                      }}
                    >
                      {run.stdout}
                    </pre>
                  )}
                  {run.stderr && (
                    <pre
                      style={{
                        background: '#1c1c1c',
                        padding: 6,
                        fontSize: '0.75rem',
                        whiteSpace: 'pre-wrap',
                        marginTop: 4,
                        color: '#ff9b66',
                      }}
                    >
                      {run.stderr}
                    </pre>
                  )}
                </details>
              )}
              <div style={{ fontSize: '0.75rem', color: '#888', marginTop: 4 }}>
                {new Date(run.created_at).toLocaleString()}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p style={{ fontSize: '0.85rem', color: '#888' }}>No command runs yet.</p>
      )}
    </section>
  )
}
