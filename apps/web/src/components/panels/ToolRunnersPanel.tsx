import { useEffect, useState } from 'react'
import {
  createToolRunnerDefinition,
  generateDefaultToolRunnerDefinitions,
  listProjectToolRunnerDefinitions,
  listProjectToolRuns,
  recordToolRun,
  updateToolRunnerDefinition,
} from '../../api'
import type {
  CodeRepository,
  RunnerType,
  ToolRun,
  ToolRunConclusion,
  ToolRunStatus,
  ToolRunTargetType,
  ToolRunnerDefinition,
  ToolRunnerMode,
} from '../../types'
import {
  RUNNER_MODES,
  RUNNER_TYPES,
  TOOL_RUN_CONCLUSIONS,
  TOOL_RUN_STATUSES,
  TOOL_RUN_TARGET_TYPES,
} from '../../lib/constants'
import { ToolRunBadge } from '../StatusBadge'

export function ToolRunnersPanel({ projectId, codeRepos }: { projectId: string; codeRepos: CodeRepository[] }) {
  const [definitions, setDefinitions] = useState<ToolRunnerDefinition[]>([])
  const [runs, setRuns] = useState<ToolRun[]>([])
  const [open, setOpen] = useState(false)
  const [genBusy, setGenBusy] = useState(false)
  const [genError, setGenError] = useState('')
  const [genMsg, setGenMsg] = useState('')

  const [defName, setDefName] = useState('')
  const [defType, setDefType] = useState<RunnerType>('manual')
  const [defMode, setDefMode] = useState<ToolRunnerMode>('dry_run')
  const [defEnabled, setDefEnabled] = useState(true)
  const [defDesc, setDefDesc] = useState('')
  const [defCreating, setDefCreating] = useState(false)
  const [defError, setDefError] = useState('')

  const [runTargetType, setRunTargetType] = useState<ToolRunTargetType>('manual')
  const [runTargetId, setRunTargetId] = useState('')
  const [runRunnerType, setRunRunnerType] = useState<RunnerType>('manual')
  const [runMode, setRunMode] = useState<ToolRunnerMode>('manual')
  const [runStatus, setRunStatus] = useState<ToolRunStatus>('completed')
  const [runConclusion, setRunConclusion] = useState<ToolRunConclusion>('success')
  const [runSummary, setRunSummary] = useState('')
  const [runRecording, setRunRecording] = useState(false)
  const [runError, setRunError] = useState('')

  useEffect(() => {
    if (!open) return
    listProjectToolRunnerDefinitions(projectId).then(setDefinitions).catch(() => {})
    listProjectToolRuns(projectId).then(setRuns).catch(() => {})
  }, [open, projectId])

  async function handleGenerate() {
    setGenBusy(true)
    setGenError('')
    setGenMsg('')
    try {
      const repoId = codeRepos.length === 1 ? codeRepos[0].id : null
      const result = await generateDefaultToolRunnerDefinitions(projectId, repoId)
      const refreshed = await listProjectToolRunnerDefinitions(projectId)
      setDefinitions(refreshed)
      setGenMsg(`Created ${result.created.length}, existing ${result.existing.length}`)
    } catch (err) {
      setGenError((err as Error).message)
    } finally {
      setGenBusy(false)
    }
  }

  async function handleCreateDef(e: React.FormEvent) {
    e.preventDefault()
    setDefError('')
    setDefCreating(true)
    try {
      const created = await createToolRunnerDefinition(projectId, {
        name: defName.trim(),
        runner_type: defType,
        enabled: defEnabled,
        mode: defMode,
        description: defDesc.trim(),
        config: {},
      })
      setDefinitions(prev => [...prev, created])
      setDefName('')
      setDefDesc('')
    } catch (err) {
      setDefError((err as Error).message)
    } finally {
      setDefCreating(false)
    }
  }

  async function handleToggleEnabled(def: ToolRunnerDefinition) {
    try {
      const updated = await updateToolRunnerDefinition(def.id, { enabled: !def.enabled })
      setDefinitions(prev => prev.map(d => d.id === updated.id ? updated : d))
    } catch { /* non-critical */ }
  }

  async function handleRecordRun(e: React.FormEvent) {
    e.preventDefault()
    setRunError('')
    setRunRecording(true)
    try {
      const recorded = await recordToolRun({
        project_id: projectId,
        target_type: runTargetType,
        target_id: runTargetId.trim() || 'manual',
        runner_type: runRunnerType,
        mode: runMode,
        status: runStatus,
        conclusion: runConclusion,
        summary: runSummary.trim(),
      })
      setRuns(prev => [recorded, ...prev])
      setRunTargetId('')
      setRunSummary('')
    } catch (err) {
      setRunError((err as Error).message)
    } finally {
      setRunRecording(false)
    }
  }

  return (
    <section style={{ marginTop: 24 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{ background: 'none', border: '1px solid #444', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: 13 }}
      >
        {open ? '▾' : '▸'} Tool runners ({definitions.length} runners, {runs.length} runs)
      </button>

      {open && (
        <div style={{ marginTop: 12 }}>
          <p style={{ fontSize: 12, color: '#888', margin: '0 0 8px' }}>
            Tracking only — no external tools execute from ForgeLoop yet. Tool runner invocation is planned for Release 5.
          </p>

          <h4 style={{ margin: '0 0 6px' }}>Runner definitions</h4>
          <div style={{ marginBottom: 8, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <button onClick={handleGenerate} disabled={genBusy} style={{ fontSize: 12 }}>
              {genBusy ? 'Generating…' : 'Generate suggested runners'}
            </button>
            {genMsg && <span style={{ fontSize: 12, color: '#4caf50' }}>{genMsg}</span>}
            {genError && <span className="error" style={{ fontSize: 12 }}>{genError}</span>}
          </div>

          {definitions.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              {definitions.map(def => (
                <div key={def.id} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '4px 0', borderBottom: '1px solid #2a2a2a', flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 12, fontWeight: 600, minWidth: 120 }}>{def.name}</span>
                  <span className="status" style={{ fontSize: 11 }}>{def.runner_type}</span>
                  <span className="status" style={{ fontSize: 11 }}>{def.mode}</span>
                  <span style={{ fontSize: 11, color: def.enabled ? '#4caf50' : '#888' }}>{def.enabled ? 'enabled' : 'disabled'}</span>
                  <button onClick={() => handleToggleEnabled(def)} style={{ fontSize: 11, padding: '1px 6px' }}>
                    {def.enabled ? 'Disable' : 'Enable'}
                  </button>
                </div>
              ))}
            </div>
          )}

          <details style={{ marginBottom: 16 }}>
            <summary style={{ fontSize: 13, cursor: 'pointer', color: '#aaa' }}>Add runner definition manually</summary>
            <form onSubmit={handleCreateDef} style={{ marginTop: 8 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
                <div>
                  <label style={{ fontSize: 12 }}>Name</label>
                  <input
                    value={defName}
                    onChange={e => setDefName(e.target.value)}
                    required
                    disabled={defCreating}
                    placeholder="e.g. OpenHands"
                    style={{ width: '100%', fontSize: 12 }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12 }}>Runner type</label>
                  <select
                    value={defType}
                    onChange={e => setDefType(e.target.value as RunnerType)}
                    disabled={defCreating}
                    style={{ width: '100%', fontSize: 12 }}
                  >
                    {RUNNER_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 12 }}>Mode</label>
                  <select
                    value={defMode}
                    onChange={e => setDefMode(e.target.value as ToolRunnerMode)}
                    disabled={defCreating}
                    style={{ width: '100%', fontSize: 12 }}
                  >
                    {RUNNER_MODES.map(m => <option key={m} value={m}>{m}</option>)}
                  </select>
                </div>
                <div style={{ display: 'flex', alignItems: 'flex-end' }}>
                  <label style={{ fontSize: 12 }}>
                    <input type="checkbox" checked={defEnabled} onChange={e => setDefEnabled(e.target.checked)} disabled={defCreating} />{' '}Enabled
                  </label>
                </div>
              </div>
              <div style={{ marginBottom: 8 }}>
                <label style={{ fontSize: 12 }}>Description</label>
                <textarea
                  value={defDesc}
                  onChange={e => setDefDesc(e.target.value)}
                  disabled={defCreating}
                  rows={2}
                  style={{ width: '100%', fontSize: 12 }}
                />
              </div>
              {defError && <div className="error" style={{ marginBottom: 4 }}>{defError}</div>}
              <button type="submit" disabled={defCreating} style={{ fontSize: 12 }}>
                {defCreating ? 'Creating…' : 'Add runner'}
              </button>
            </form>
          </details>

          <h4 style={{ margin: '8px 0 6px' }}>Tool runs</h4>

          {runs.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              {runs.slice(0, 20).map(run => (
                <div key={run.id} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '4px 0', borderBottom: '1px solid #2a2a2a', flexWrap: 'wrap' }}>
                  <ToolRunBadge conclusion={run.conclusion} status={run.status} />
                  <span style={{ fontSize: 11, color: '#888' }}>{run.runner_type}</span>
                  <span style={{ fontSize: 11, color: '#888' }}>{run.target_type}:{run.target_id.slice(0, 12)}</span>
                  <span style={{ fontSize: 12 }}>{run.summary}</span>
                </div>
              ))}
            </div>
          )}

          <details>
            <summary style={{ fontSize: 13, cursor: 'pointer', color: '#aaa' }}>Record tool run manually</summary>
            <form onSubmit={handleRecordRun} style={{ marginTop: 8 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
                <div>
                  <label style={{ fontSize: 12 }}>Runner type</label>
                  <select
                    value={runRunnerType}
                    onChange={e => setRunRunnerType(e.target.value as RunnerType)}
                    disabled={runRecording}
                    style={{ width: '100%', fontSize: 12 }}
                  >
                    {RUNNER_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 12 }}>Mode</label>
                  <select
                    value={runMode}
                    onChange={e => setRunMode(e.target.value as ToolRunnerMode)}
                    disabled={runRecording}
                    style={{ width: '100%', fontSize: 12 }}
                  >
                    {RUNNER_MODES.map(m => <option key={m} value={m}>{m}</option>)}
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 12 }}>Target type</label>
                  <select
                    value={runTargetType}
                    onChange={e => setRunTargetType(e.target.value as ToolRunTargetType)}
                    disabled={runRecording}
                    style={{ width: '100%', fontSize: 12 }}
                  >
                    {TOOL_RUN_TARGET_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 12 }}>Target ID</label>
                  <input
                    value={runTargetId}
                    onChange={e => setRunTargetId(e.target.value)}
                    disabled={runRecording}
                    placeholder="leave blank for manual"
                    style={{ width: '100%', fontSize: 12 }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12 }}>Status</label>
                  <select
                    value={runStatus}
                    onChange={e => setRunStatus(e.target.value as ToolRunStatus)}
                    disabled={runRecording}
                    style={{ width: '100%', fontSize: 12 }}
                  >
                    {TOOL_RUN_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 12 }}>Conclusion</label>
                  <select
                    value={runConclusion}
                    onChange={e => setRunConclusion(e.target.value as ToolRunConclusion)}
                    disabled={runRecording}
                    style={{ width: '100%', fontSize: 12 }}
                  >
                    {TOOL_RUN_CONCLUSIONS.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
              </div>
              <div style={{ marginBottom: 8 }}>
                <label style={{ fontSize: 12 }}>Summary</label>
                <input
                  value={runSummary}
                  onChange={e => setRunSummary(e.target.value)}
                  disabled={runRecording}
                  placeholder="e.g. Manual implementation completed"
                  style={{ width: '100%', fontSize: 12 }}
                />
              </div>
              {runError && <div className="error" style={{ marginBottom: 4 }}>{runError}</div>}
              <button type="submit" disabled={runRecording} style={{ fontSize: 12 }}>
                {runRecording ? 'Recording…' : 'Record run'}
              </button>
            </form>
          </details>
        </div>
      )}
    </section>
  )
}
