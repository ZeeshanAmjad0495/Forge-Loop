import { useState } from 'react'
import {
  createApproval,
  decideApproval,
  executeOpenHands,
  listDevTaskCheckRuns,
  listDevTaskToolRuns,
  listProjectCodeRepositories,
  listProjectWorkspaces,
  prepareOpenHandsPackage,
  preparePullRequestDraft,
  recordOpenHandsResult,
  updateDevTask,
} from '../api'
import type {
  Approval,
  AssigneeType,
  CheckRun,
  DevTask,
  DevTaskStatus,
  OpenHandsExecutionSummary,
  OpenHandsInstructionPackage,
  PullRequestDraft,
  Subtask,
  ToolRun,
  ToolRunConclusion,
  Workspace,
} from '../types'
import { ALL_STATUSES, ASSIGNEE_TYPES } from '../lib/constants'
import { CheckBadge, ToolRunBadge } from './StatusBadge'
import { SubtaskList } from './SubtaskCard'

export function DevTaskCard({
  task,
  allSubtasks,
  taskApproval,
  projectId,
  onTaskUpdate,
  onSubtaskUpdate,
  onApprovalChange,
}: {
  task: DevTask
  allSubtasks: Subtask[]
  taskApproval: Approval | undefined
  projectId: string
  onTaskUpdate: (updated: DevTask) => void
  onSubtaskUpdate: (updated: Subtask) => void
  onApprovalChange: () => void
}) {
  const subtasks = allSubtasks.filter(st => st.dev_task_id === task.id)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [approvalBusy, setApprovalBusy] = useState(false)
  const [approvalFeedback, setApprovalFeedback] = useState('')
  const [approvalError, setApprovalError] = useState<string | null>(null)

  const [checksOpen, setChecksOpen] = useState(false)
  const [taskCheckRuns, setTaskCheckRuns] = useState<CheckRun[]>([])
  const [checksLoaded, setChecksLoaded] = useState(false)

  async function handleOpenChecks() {
    const next = !checksOpen
    setChecksOpen(next)
    if (next && !checksLoaded) {
      try {
        const runs = await listDevTaskCheckRuns(task.id)
        setTaskCheckRuns(runs)
        setChecksLoaded(true)
      } catch { /* non-critical */ }
    }
  }

  const [toolRunsOpen, setToolRunsOpen] = useState(false)
  const [taskToolRuns, setTaskToolRuns] = useState<ToolRun[]>([])
  const [toolRunsLoaded, setToolRunsLoaded] = useState(false)

  async function handleOpenToolRuns() {
    const next = !toolRunsOpen
    setToolRunsOpen(next)
    if (next && !toolRunsLoaded) {
      try {
        const runs = await listDevTaskToolRuns(task.id)
        setTaskToolRuns(runs)
        setToolRunsLoaded(true)
      } catch { /* non-critical */ }
    }
  }

  const [ohBusy, setOhBusy] = useState(false)
  const [ohError, setOhError] = useState<string | null>(null)
  const [ohPackage, setOhPackage] = useState<OpenHandsInstructionPackage | null>(null)
  const [ohRun, setOhRun] = useState<ToolRun | null>(null)
  const [ohResultText, setOhResultText] = useState('')
  const [ohResultConclusion, setOhResultConclusion] = useState<ToolRunConclusion>('success')
  const [ohRecording, setOhRecording] = useState(false)
  const [ohExecutionEnabled, setOhExecutionEnabled] = useState(false)
  const [ohWorkspaces, setOhWorkspaces] = useState<Workspace[]>([])
  const [ohSelectedWorkspace, setOhSelectedWorkspace] = useState<string>('')
  const [ohExecuting, setOhExecuting] = useState(false)
  const [ohSummary, setOhSummary] = useState<OpenHandsExecutionSummary | null>(null)

  const [prBusy, setPrBusy] = useState(false)
  const [prError, setPrError] = useState<string | null>(null)
  const [prDraft, setPrDraft] = useState<PullRequestDraft | null>(null)

  async function handlePreparePrDraft() {
    setPrError(null)
    setPrBusy(true)
    try {
      const repos = await listProjectCodeRepositories(projectId)
      if (repos.length === 0) {
        throw new Error('No code repository registered for project. Add a repo first.')
      }
      const draft = await preparePullRequestDraft(projectId, {
        code_repository_id: repos[0].id,
        dev_task_id: task.id,
        tool_run_id: ohRun?.id ?? null,
      })
      setPrDraft(draft)
    } catch (e) {
      setPrError((e as Error).message)
    } finally {
      setPrBusy(false)
    }
  }

  async function handlePrepareOpenHands() {
    setOhError(null)
    setOhBusy(true)
    try {
      const resp = await prepareOpenHandsPackage(task.id, {})
      setOhPackage(resp.instruction_package)
      setOhRun(resp.tool_run)
      setOhExecutionEnabled(resp.execution_enabled)
      setOhSummary(null)
      try {
        const ws = await listProjectWorkspaces(projectId)
        const ready = ws.filter(w => w.status === 'ready')
        setOhWorkspaces(ready)
        if (ready.length === 1) setOhSelectedWorkspace(ready[0].id)
      } catch { /* non-critical */ }
      if (toolRunsLoaded) {
        try {
          const runs = await listDevTaskToolRuns(task.id)
          setTaskToolRuns(runs)
        } catch { /* non-critical */ }
      }
    } catch (e) {
      setOhError((e as Error).message)
    } finally {
      setOhBusy(false)
    }
  }

  async function handleExecuteOpenHands() {
    if (!ohSelectedWorkspace) return
    setOhError(null)
    setOhExecuting(true)
    setOhSummary(null)
    try {
      const resp = await executeOpenHands(task.id, {
        workspace_id: ohSelectedWorkspace,
        mode: 'local',
      })
      setOhRun(resp.tool_run)
      setOhSummary(resp.execution_summary)
      if (toolRunsLoaded) {
        try {
          const runs = await listDevTaskToolRuns(task.id)
          setTaskToolRuns(runs)
        } catch { /* non-critical */ }
      }
    } catch (e) {
      setOhError((e as Error).message)
    } finally {
      setOhExecuting(false)
    }
  }

  async function handleRecordOpenHandsResult() {
    if (!ohRun) return
    setOhError(null)
    setOhRecording(true)
    try {
      const updated = await recordOpenHandsResult(ohRun.id, {
        summary: ohResultText.split('\n')[0]?.slice(0, 200) || 'Recorded result',
        output: ohResultText,
        conclusion: ohResultConclusion,
      })
      setOhRun(updated)
      setOhResultText('')
    } catch (e) {
      setOhError((e as Error).message)
    } finally {
      setOhRecording(false)
    }
  }

  const needsApproval = task.status === 'proposed' && (!taskApproval || taskApproval.status !== 'approved')

  async function handleStatusChange(next: string) {
    setError(null)
    setBusy(true)
    try {
      const updated = await updateDevTask(task.id, { status: next as DevTaskStatus })
      onTaskUpdate(updated)
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
      const updated = await updateDevTask(task.id, { assignee_type: next })
      onTaskUpdate(updated)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function handleAssigneeNameBlur(name: string) {
    if (name === (task.assignee_name ?? '')) return
    setBusy(true)
    try {
      const updated = await updateDevTask(task.id, { assignee_name: name || null })
      onTaskUpdate(updated)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function handleRequestApproval() {
    setApprovalError(null)
    setApprovalBusy(true)
    try {
      await createApproval({ project_id: projectId, target_type: 'dev_task', target_id: task.id })
      onApprovalChange()
    } catch (e) {
      setApprovalError((e as Error).message)
    } finally {
      setApprovalBusy(false)
    }
  }

  async function handleDecide(status: 'approved' | 'rejected' | 'needs_revision') {
    if (!taskApproval) return
    setApprovalError(null)
    setApprovalBusy(true)
    try {
      await decideApproval(taskApproval.id, { status, feedback: approvalFeedback || null })
      onApprovalChange()
    } catch (e) {
      setApprovalError((e as Error).message)
    } finally {
      setApprovalBusy(false)
    }
  }

  return (
    <div style={{ border: '1px solid #333', borderRadius: 6, padding: '10px 14px', marginBottom: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <strong>{task.title}</strong>
        <span className="status">{task.task_type}</span>
        <span className="status">{task.priority}</span>
        <select
          value={task.status}
          onChange={e => handleStatusChange(e.target.value)}
          disabled={busy}
          style={{ fontSize: 12 }}
        >
          {ALL_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        {task.qa_required && <span className="status done">QA required</span>}
        {task.blocked_by && task.blocked_by.length > 0 && (
          <span className="status" style={{ color: '#f87171', fontSize: 11 }}>blocked</span>
        )}
        {needsApproval && (
          <span className="status" style={{ color: '#facc15', fontSize: 11 }}>approval required</span>
        )}
        {taskApproval?.status === 'approved' && (
          <span className="status done" style={{ fontSize: 11 }}>approved</span>
        )}
      </div>
      {error && <div className="error" style={{ marginTop: 4 }}>{error}</div>}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 6, alignItems: 'center' }}>
        {task.epic_id && (
          <span style={{ fontSize: 11, color: '#aaa' }}>Epic: {task.epic_id.slice(0, 8)}…</span>
        )}
        <label style={{ fontSize: 11 }}>Assign:
          <select
            value={task.assignee_type}
            onChange={e => handleAssigneeTypeChange(e.target.value as AssigneeType)}
            disabled={busy}
            style={{ marginLeft: 4, fontSize: 11 }}
          >
            {ASSIGNEE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
        {task.assignee_type !== 'unassigned' && (
          <input
            defaultValue={task.assignee_name ?? ''}
            onBlur={e => handleAssigneeNameBlur(e.target.value)}
            placeholder="name"
            disabled={busy}
            style={{ fontSize: 11, padding: '2px 4px', background: '#1a1a1a', border: '1px solid #444', color: '#fff', borderRadius: 3, width: 100 }}
          />
        )}
      </div>

      {task.status === 'proposed' && !taskApproval && (
        <div style={{ marginTop: 6 }}>
          <button onClick={handleRequestApproval} disabled={approvalBusy} style={{ fontSize: 12 }}>
            Request approval
          </button>
          {approvalError && <div className="error" style={{ marginTop: 4 }}>{approvalError}</div>}
        </div>
      )}
      {task.status === 'proposed' && taskApproval && taskApproval.status === 'pending' && (
        <div style={{ marginTop: 6, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: '#aaa' }}>Decision:</span>
          <input
            placeholder="Feedback (optional)"
            value={approvalFeedback}
            onChange={e => setApprovalFeedback(e.target.value)}
            style={{ fontSize: 12, padding: '2px 6px', background: '#1a1a1a', border: '1px solid #444', color: '#fff', borderRadius: 3 }}
          />
          <button onClick={() => handleDecide('approved')} disabled={approvalBusy} style={{ fontSize: 12 }}>Approve</button>
          <button onClick={() => handleDecide('rejected')} disabled={approvalBusy} style={{ fontSize: 12 }}>Reject</button>
          <button onClick={() => handleDecide('needs_revision')} disabled={approvalBusy} style={{ fontSize: 12 }}>Needs revision</button>
          {approvalError && <div className="error">{approvalError}</div>}
        </div>
      )}
      {task.description && <p style={{ margin: '6px 0 4px', fontSize: 13 }}>{task.description}</p>}
      {task.depends_on.length > 0 && (
        <p style={{ margin: '4px 0', fontSize: 12, color: '#aaa' }}>
          Depends on: {task.depends_on.length} task(s)
        </p>
      )}
      {task.acceptance_criteria.length > 0 && (
        <>
          <p style={{ margin: '6px 0 2px', fontSize: 12 }}><strong>Acceptance criteria</strong></p>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12 }}>
            {task.acceptance_criteria.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
        </>
      )}
      {subtasks.length > 0 && (
        <>
          <p style={{ margin: '6px 0 2px', fontSize: 12 }}><strong>Subtasks</strong></p>
          <SubtaskList subtasks={subtasks} onSubtaskUpdate={onSubtaskUpdate} />
        </>
      )}
      <div style={{ marginTop: 6 }}>
        <button
          onClick={handleOpenChecks}
          style={{ background: 'none', border: '1px solid #333', borderRadius: 3, padding: '2px 8px', cursor: 'pointer', fontSize: 11, color: '#aaa' }}
        >
          {checksOpen ? '▾' : '▸'} Checks{checksLoaded ? ` (${taskCheckRuns.length})` : ''}
        </button>
        {checksOpen && (
          <div style={{ marginTop: 4, paddingLeft: 8 }}>
            {taskCheckRuns.length === 0
              ? <p style={{ fontSize: 11, color: '#666', margin: '4px 0' }}>No check runs recorded for this task.</p>
              : taskCheckRuns.map(run => (
                  <div key={run.id} style={{ display: 'flex', gap: 6, alignItems: 'center', padding: '2px 0', flexWrap: 'wrap' }}>
                    <CheckBadge conclusion={run.conclusion} status={run.status} />
                    <span style={{ fontSize: 11 }}>{run.summary}</span>
                  </div>
                ))
            }
          </div>
        )}
      </div>
      <div style={{ marginTop: 4 }}>
        <button
          onClick={handleOpenToolRuns}
          style={{ background: 'none', border: '1px solid #333', borderRadius: 3, padding: '2px 8px', cursor: 'pointer', fontSize: 11, color: '#aaa' }}
        >
          {toolRunsOpen ? '▾' : '▸'} Tool runs{toolRunsLoaded ? ` (${taskToolRuns.length})` : ''}
        </button>
        {toolRunsOpen && (
          <div style={{ marginTop: 4, paddingLeft: 8 }}>
            {taskToolRuns.length === 0
              ? <p style={{ fontSize: 11, color: '#666', margin: '4px 0' }}>No tool runs recorded for this task.</p>
              : taskToolRuns.map(run => (
                  <div key={run.id} style={{ display: 'flex', gap: 6, alignItems: 'center', padding: '2px 0', flexWrap: 'wrap' }}>
                    <ToolRunBadge conclusion={run.conclusion} status={run.status} />
                    <span style={{ fontSize: 11, color: '#888' }}>{run.runner_type}</span>
                    <span style={{ fontSize: 11 }}>{run.summary}</span>
                  </div>
                ))
            }
          </div>
        )}
      </div>

      <div style={{ marginTop: 6, padding: '6px 8px', border: '1px dashed #2c2c2c', borderRadius: 4 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <strong style={{ fontSize: 11, color: '#aaa' }}>OpenHands</strong>
          <button
            onClick={handlePrepareOpenHands}
            disabled={ohBusy}
            style={{ fontSize: 11, padding: '2px 8px' }}
          >
            {ohBusy ? 'Preparing…' : 'Prepare OpenHands package'}
          </button>
          {ohRun && (
            <>
              <ToolRunBadge conclusion={ohRun.conclusion} status={ohRun.status} />
              <span style={{ fontSize: 11, color: '#888' }}>{ohRun.summary}</span>
            </>
          )}
        </div>
        {ohError && <div className="error" style={{ marginTop: 4, fontSize: 11 }}>{ohError}</div>}
        {ohPackage && (
          <>
            <p style={{ fontSize: 10, color: '#666', margin: '6px 0 2px' }}>
              Dry-run package — copy to OpenHands manually, or use Execute (local) below
              when enabled.
            </p>
            <pre style={{
              maxHeight: 220,
              overflow: 'auto',
              background: '#0e0e0e',
              border: '1px solid #222',
              borderRadius: 3,
              padding: 6,
              fontSize: 10,
              margin: 0,
            }}>{JSON.stringify(ohPackage, null, 2)}</pre>
          </>
        )}
        {ohRun && (
          <div style={{ marginTop: 6, padding: '6px 8px', border: '1px solid #3a1d1d', borderRadius: 3, background: '#1a1010' }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <strong style={{ fontSize: 11, color: '#e58' }}>Execute (local)</strong>
              <select
                value={ohSelectedWorkspace}
                onChange={e => setOhSelectedWorkspace(e.target.value)}
                disabled={ohExecuting || !ohExecutionEnabled || ohWorkspaces.length === 0}
                style={{ fontSize: 11 }}
              >
                <option value="">— select ready workspace —</option>
                {ohWorkspaces.map(w => (
                  <option key={w.id} value={w.id}>{w.name} ({w.root_path})</option>
                ))}
              </select>
              <button
                onClick={handleExecuteOpenHands}
                disabled={ohExecuting || !ohExecutionEnabled || !ohSelectedWorkspace}
                title={
                  !ohExecutionEnabled
                    ? 'OpenHands local execution is disabled (OPENHANDS_EXECUTION_ENABLED=false).'
                    : !ohSelectedWorkspace
                      ? 'Select a ready workspace first.'
                      : 'Run OpenHands inside the selected workspace.'
                }
                style={{ fontSize: 11, padding: '2px 8px' }}
              >
                {ohExecuting ? 'Executing…' : 'Execute (local)'}
              </button>
              <span style={{ fontSize: 10, color: '#c66' }}>
                Modifies files in workspace. No branch/PR. Review changes manually.
              </span>
            </div>
            {ohSummary && (
              <div style={{ marginTop: 6, fontSize: 11 }}>
                <div>
                  exit_code: <code>{String(ohSummary.exit_code)}</code> · timed_out:{' '}
                  <code>{String(ohSummary.timed_out)}</code> · duration:{' '}
                  <code>{ohSummary.duration_seconds.toFixed(2)}s</code>
                </div>
                {ohSummary.blocked_path_changes.length > 0 && (
                  <div style={{ color: '#f88', marginTop: 2 }}>
                    Blocked-path changes: {ohSummary.blocked_path_changes.join(', ')}
                  </div>
                )}
                {ohSummary.changed_paths.length > 0 && (
                  <details style={{ marginTop: 4 }}>
                    <summary style={{ cursor: 'pointer', fontSize: 11 }}>
                      Changed paths ({ohSummary.changed_paths.length})
                    </summary>
                    <ul style={{ margin: '4px 0 0 16px', padding: 0, fontSize: 11 }}>
                      {ohSummary.changed_paths.slice(0, 200).map(c => (
                        <li key={c.path}><code>{c.change_type}</code> {c.path}</li>
                      ))}
                    </ul>
                  </details>
                )}
                {(ohSummary.stdout_tail || ohSummary.stderr_tail) && (
                  <details style={{ marginTop: 4 }}>
                    <summary style={{ cursor: 'pointer', fontSize: 11 }}>Output tail</summary>
                    <pre style={{
                      maxHeight: 160,
                      overflow: 'auto',
                      background: '#0e0e0e',
                      border: '1px solid #222',
                      borderRadius: 3,
                      padding: 6,
                      fontSize: 10,
                      margin: 4,
                    }}>{ohSummary.stdout_tail}{ohSummary.stderr_tail ? '\n--- stderr ---\n' + ohSummary.stderr_tail : ''}</pre>
                  </details>
                )}
              </div>
            )}
          </div>
        )}
        {ohRun && (
          <div style={{ marginTop: 6 }}>
            <textarea
              value={ohResultText}
              onChange={e => setOhResultText(e.target.value)}
              placeholder="Paste OpenHands result/output here…"
              rows={3}
              disabled={ohRecording}
              style={{ width: '100%', fontSize: 11, background: '#1a1a1a', border: '1px solid #444', color: '#fff', borderRadius: 3 }}
            />
            <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginTop: 4, flexWrap: 'wrap' }}>
              <label style={{ fontSize: 11 }}>Conclusion:
                <select
                  value={ohResultConclusion}
                  onChange={e => setOhResultConclusion(e.target.value as ToolRunConclusion)}
                  disabled={ohRecording}
                  style={{ marginLeft: 4, fontSize: 11 }}
                >
                  <option value="success">success</option>
                  <option value="failure">failure</option>
                  <option value="neutral">neutral</option>
                  <option value="requires_human_action">requires_human_action</option>
                </select>
              </label>
              <button
                onClick={handleRecordOpenHandsResult}
                disabled={ohRecording || !ohResultText.trim()}
                style={{ fontSize: 11 }}
              >
                {ohRecording ? 'Recording…' : 'Record result'}
              </button>
            </div>
          </div>
        )}
      </div>

      <div style={{ marginTop: 6, padding: '6px 8px', border: '1px dashed #2c2c2c', borderRadius: 4 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <strong style={{ fontSize: 11, color: '#aaa' }}>PR draft</strong>
          <button
            onClick={handlePreparePrDraft}
            disabled={prBusy}
            style={{ fontSize: 11, padding: '2px 8px' }}
          >
            {prBusy ? 'Preparing…' : 'Prepare PR draft'}
          </button>
          {prDraft && (
            <>
              <span className="status" style={{ fontSize: 11 }}>{prDraft.status}</span>
              <span style={{ fontSize: 11, color: '#888' }}>
                {prDraft.source_branch} → {prDraft.target_branch}
              </span>
            </>
          )}
        </div>
        {prError && <div className="error" style={{ marginTop: 4, fontSize: 11 }}>{prError}</div>}
        {prDraft && (
          <>
            <p style={{ fontSize: 10, color: '#666', margin: '6px 0 2px' }}>
              {prDraft.title} — metadata only, no GitHub call. View/approve in the project's PR drafts panel.
            </p>
            <pre style={{
              maxHeight: 180,
              overflow: 'auto',
              background: '#0e0e0e',
              border: '1px solid #222',
              borderRadius: 3,
              padding: 6,
              fontSize: 10,
              margin: 0,
            }}>{prDraft.body.slice(0, 1200)}{prDraft.body.length > 1200 ? '…' : ''}</pre>
          </>
        )}
      </div>
    </div>
  )
}
