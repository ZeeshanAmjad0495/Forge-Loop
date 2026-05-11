import { useEffect, useState } from 'react'
import {
  createCheckDefinition,
  generateCheckDefinitionsFromSafetyProfile,
  listProjectCheckDefinitions,
  listProjectCheckRuns,
  recordCheckRun,
  updateCheckDefinition,
} from '../../api'
import type {
  CheckDefinition,
  CheckRun,
  CheckRunConclusion,
  CheckRunStatus,
  CheckRunTargetType,
  CheckSeverity,
  CheckType,
  CodeRepository,
} from '../../types'
import {
  CHECK_RUN_CONCLUSIONS,
  CHECK_RUN_STATUSES,
  CHECK_RUN_TARGET_TYPES,
  CHECK_SEVERITIES,
  CHECK_TYPES,
} from '../../lib/constants'
import { CheckBadge } from '../StatusBadge'

export function ChecksPanel({ projectId, codeRepos }: { projectId: string; codeRepos: CodeRepository[] }) {
  const [definitions, setDefinitions] = useState<CheckDefinition[]>([])
  const [runs, setRuns] = useState<CheckRun[]>([])
  const [open, setOpen] = useState(false)
  const [genBusy, setGenBusy] = useState(false)
  const [genError, setGenError] = useState('')
  const [genMsg, setGenMsg] = useState('')

  const [defName, setDefName] = useState('')
  const [defType, setDefType] = useState<CheckType>('tests')
  const [defCommand, setDefCommand] = useState('')
  const [defSeverity, setDefSeverity] = useState<CheckSeverity>('blocking')
  const [defRequired, setDefRequired] = useState(true)
  const [defEnabled, setDefEnabled] = useState(true)
  const [defDesc, setDefDesc] = useState('')
  const [defCreating, setDefCreating] = useState(false)
  const [defError, setDefError] = useState('')

  const [runTargetType, setRunTargetType] = useState<CheckRunTargetType>('manual')
  const [runTargetId, setRunTargetId] = useState('')
  const [runStatus, setRunStatus] = useState<CheckRunStatus>('completed')
  const [runConclusion, setRunConclusion] = useState<CheckRunConclusion>('success')
  const [runSummary, setRunSummary] = useState('')
  const [runOutput, setRunOutput] = useState('')
  const [runRecording, setRunRecording] = useState(false)
  const [runError, setRunError] = useState('')

  useEffect(() => {
    if (!open) return
    listProjectCheckDefinitions(projectId).then(setDefinitions).catch(() => {})
    listProjectCheckRuns(projectId).then(setRuns).catch(() => {})
  }, [open, projectId])

  async function handleGenerate() {
    setGenBusy(true)
    setGenError('')
    setGenMsg('')
    try {
      const repoId = codeRepos.length === 1 ? codeRepos[0].id : null
      const result = await generateCheckDefinitionsFromSafetyProfile(projectId, repoId)
      const refreshed = await listProjectCheckDefinitions(projectId)
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
      const created = await createCheckDefinition(projectId, {
        name: defName.trim(),
        check_type: defType,
        command: defCommand.trim(),
        required: defRequired,
        enabled: defEnabled,
        severity: defSeverity,
        description: defDesc.trim(),
      })
      setDefinitions(prev => [...prev, created])
      setDefName('')
      setDefCommand('')
      setDefDesc('')
    } catch (err) {
      setDefError((err as Error).message)
    } finally {
      setDefCreating(false)
    }
  }

  async function handleToggleEnabled(def: CheckDefinition) {
    try {
      const updated = await updateCheckDefinition(def.id, { enabled: !def.enabled })
      setDefinitions(prev => prev.map(d => d.id === updated.id ? updated : d))
    } catch { /* non-critical */ }
  }

  async function handleRecordRun(e: React.FormEvent) {
    e.preventDefault()
    setRunError('')
    setRunRecording(true)
    try {
      const recorded = await recordCheckRun({
        project_id: projectId,
        target_type: runTargetType,
        target_id: runTargetId.trim() || 'manual',
        status: runStatus,
        conclusion: runConclusion,
        summary: runSummary.trim(),
        output: runOutput.trim() || null,
      })
      setRuns(prev => [recorded, ...prev])
      setRunTargetId('')
      setRunSummary('')
      setRunOutput('')
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
        {open ? '▾' : '▸'} QA / Security checks ({definitions.length} definitions, {runs.length} runs)
      </button>

      {open && (
        <div style={{ marginTop: 12 }}>

          <h4 style={{ margin: '0 0 6px' }}>Check definitions</h4>
          <div style={{ marginBottom: 8, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <button
              onClick={handleGenerate}
              disabled={genBusy}
              style={{ fontSize: 12 }}
            >
              {genBusy ? 'Generating…' : 'Generate from safety profile'}
            </button>
            {genMsg && <span style={{ fontSize: 12, color: '#4caf50' }}>{genMsg}</span>}
            {genError && <span className="error" style={{ fontSize: 12 }}>{genError}</span>}
          </div>

          {definitions.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              {definitions.map(def => (
                <div key={def.id} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '4px 0', borderBottom: '1px solid #2a2a2a', flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 12, fontWeight: 600, minWidth: 120 }}>{def.name}</span>
                  <span className="status" style={{ fontSize: 11 }}>{def.check_type}</span>
                  <span className="status" style={{ fontSize: 11, color: def.severity === 'blocking' ? '#f44336' : def.severity === 'warning' ? '#ff9800' : '#aaa' }}>{def.severity}</span>
                  {def.command && <code style={{ fontSize: 11, color: '#888' }}>{def.command}</code>}
                  <span style={{ fontSize: 11, color: def.enabled ? '#4caf50' : '#888' }}>{def.enabled ? 'enabled' : 'disabled'}</span>
                  <button
                    onClick={() => handleToggleEnabled(def)}
                    style={{ fontSize: 11, padding: '1px 6px' }}
                  >
                    {def.enabled ? 'Disable' : 'Enable'}
                  </button>
                </div>
              ))}
            </div>
          )}

          <details style={{ marginBottom: 16 }}>
            <summary style={{ fontSize: 13, cursor: 'pointer', color: '#aaa' }}>Add check definition manually</summary>
            <form onSubmit={handleCreateDef} style={{ marginTop: 8 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
                <div>
                  <label style={{ fontSize: 12 }}>Name</label>
                  <input
                    value={defName}
                    onChange={e => setDefName(e.target.value)}
                    required
                    disabled={defCreating}
                    placeholder="e.g. Backend tests"
                    style={{ width: '100%', fontSize: 12 }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12 }}>Check type</label>
                  <select
                    value={defType}
                    onChange={e => setDefType(e.target.value as CheckType)}
                    disabled={defCreating}
                    style={{ width: '100%', fontSize: 12 }}
                  >
                    {CHECK_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 12 }}>Command (reference only)</label>
                  <input
                    value={defCommand}
                    onChange={e => setDefCommand(e.target.value)}
                    disabled={defCreating}
                    placeholder="e.g. pytest"
                    style={{ width: '100%', fontSize: 12 }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12 }}>Severity</label>
                  <select
                    value={defSeverity}
                    onChange={e => setDefSeverity(e.target.value as CheckSeverity)}
                    disabled={defCreating}
                    style={{ width: '100%', fontSize: 12 }}
                  >
                    {CHECK_SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 12, marginBottom: 8 }}>
                <label style={{ fontSize: 12 }}>
                  <input type="checkbox" checked={defRequired} onChange={e => setDefRequired(e.target.checked)} disabled={defCreating} />{' '}Required
                </label>
                <label style={{ fontSize: 12 }}>
                  <input type="checkbox" checked={defEnabled} onChange={e => setDefEnabled(e.target.checked)} disabled={defCreating} />{' '}Enabled
                </label>
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
                {defCreating ? 'Creating…' : 'Add definition'}
              </button>
            </form>
          </details>

          <h4 style={{ margin: '8px 0 6px' }}>Check runs</h4>

          {runs.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              {runs.slice(0, 20).map(run => (
                <div key={run.id} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '4px 0', borderBottom: '1px solid #2a2a2a', flexWrap: 'wrap' }}>
                  <CheckBadge conclusion={run.conclusion} status={run.status} />
                  <span style={{ fontSize: 11, color: '#888' }}>{run.target_type}:{run.target_id.slice(0, 12)}</span>
                  <span style={{ fontSize: 12 }}>{run.summary}</span>
                </div>
              ))}
            </div>
          )}

          <details>
            <summary style={{ fontSize: 13, cursor: 'pointer', color: '#aaa' }}>Record check run manually</summary>
            <form onSubmit={handleRecordRun} style={{ marginTop: 8 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
                <div>
                  <label style={{ fontSize: 12 }}>Target type</label>
                  <select
                    value={runTargetType}
                    onChange={e => setRunTargetType(e.target.value as CheckRunTargetType)}
                    disabled={runRecording}
                    style={{ width: '100%', fontSize: 12 }}
                  >
                    {CHECK_RUN_TARGET_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
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
                    onChange={e => setRunStatus(e.target.value as CheckRunStatus)}
                    disabled={runRecording}
                    style={{ width: '100%', fontSize: 12 }}
                  >
                    {CHECK_RUN_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 12 }}>Conclusion</label>
                  <select
                    value={runConclusion}
                    onChange={e => setRunConclusion(e.target.value as CheckRunConclusion)}
                    disabled={runRecording}
                    style={{ width: '100%', fontSize: 12 }}
                  >
                    {CHECK_RUN_CONCLUSIONS.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
              </div>
              <div style={{ marginBottom: 8 }}>
                <label style={{ fontSize: 12 }}>Summary</label>
                <input
                  value={runSummary}
                  onChange={e => setRunSummary(e.target.value)}
                  disabled={runRecording}
                  placeholder="e.g. Tests passed: 42/42"
                  style={{ width: '100%', fontSize: 12 }}
                />
              </div>
              <div style={{ marginBottom: 8 }}>
                <label style={{ fontSize: 12 }}>Output (optional)</label>
                <textarea
                  value={runOutput}
                  onChange={e => setRunOutput(e.target.value)}
                  disabled={runRecording}
                  rows={3}
                  style={{ width: '100%', fontSize: 12, fontFamily: 'monospace' }}
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
