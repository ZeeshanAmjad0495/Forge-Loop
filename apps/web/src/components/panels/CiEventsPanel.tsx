import { useEffect, useState } from 'react'
import {
  createCIAnalysis,
  listCIEventAnalyses,
  listProjectCIEvents,
  recordCIEvent,
} from '../../api'
import type {
  CIAnalysis,
  CIEvent,
  CIEventConclusion,
  CIEventProvider,
  CIEventStatus,
} from '../../types'
import { ciConclusionStyle } from '../../lib/status'

export function CIEventsPanel({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState(false)
  const [events, setEvents] = useState<CIEvent[]>([])
  const [analysesByEvent, setAnalysesByEvent] = useState<Record<string, CIAnalysis[]>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const [provider, setProvider] = useState<CIEventProvider>('github_actions')
  const [workflow, setWorkflow] = useState('')
  const [job, setJob] = useState('')
  const [branch, setBranch] = useState('')
  const [status, setStatus] = useState<CIEventStatus>('completed')
  const [conclusion, setConclusion] = useState<CIEventConclusion>('failure')
  const [failureSummary, setFailureSummary] = useState('')
  const [logsExcerpt, setLogsExcerpt] = useState('')

  useEffect(() => {
    if (!open) return
    listProjectCIEvents(projectId).then(setEvents).catch(() => {})
  }, [open, projectId])

  async function refresh() {
    try {
      setEvents(await listProjectCIEvents(projectId))
    } catch { /* non-critical */ }
  }

  async function loadAnalyses(eventId: string) {
    try {
      const analyses = await listCIEventAnalyses(eventId)
      setAnalysesByEvent(prev => ({ ...prev, [eventId]: analyses }))
    } catch { /* non-critical */ }
  }

  async function handleRecord(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await recordCIEvent(projectId, {
        provider,
        workflow_name: workflow || null,
        job_name: job || null,
        branch: branch || null,
        status,
        conclusion,
        failure_summary: failureSummary || null,
        logs_excerpt: logsExcerpt || null,
      })
      setWorkflow('')
      setJob('')
      setBranch('')
      setFailureSummary('')
      setLogsExcerpt('')
      await refresh()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function handleRequestAnalysis(event: CIEvent) {
    setBusy(true)
    setError('')
    try {
      const analysis = await createCIAnalysis(event.id, {})
      setAnalysesByEvent(prev => ({
        ...prev,
        [event.id]: [analysis, ...(prev[event.id] || [])],
      }))
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
        {open ? '▾' : '▸'} CI events ({events.length})
      </button>
      {open && (
        <div style={{ marginTop: 12 }}>
          <p style={{ fontSize: 12, color: '#888', margin: '0 0 8px' }}>
            CI events are recorded manually or programmatically. ForgeLoop does
            not call GitHub Actions, GitLab CI, or any CI provider. Analyses are
            advisory only — no auto-fix and no auto-merge.
          </p>
          {error && <div className="error" style={{ marginBottom: 6, fontSize: 12 }}>{error}</div>}

          <form onSubmit={handleRecord} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
            <label style={{ fontSize: 12 }}>
              Provider
              <select value={provider} onChange={e => setProvider(e.target.value as CIEventProvider)} disabled={busy} style={{ width: '100%' }}>
                <option value="github_actions">github_actions</option>
                <option value="gitlab_ci">gitlab_ci</option>
                <option value="circleci">circleci</option>
                <option value="manual">manual</option>
                <option value="custom">custom</option>
              </select>
            </label>
            <label style={{ fontSize: 12 }}>
              Workflow
              <input value={workflow} onChange={e => setWorkflow(e.target.value)} disabled={busy} placeholder="Backend CI" style={{ width: '100%' }} />
            </label>
            <label style={{ fontSize: 12 }}>
              Job
              <input value={job} onChange={e => setJob(e.target.value)} disabled={busy} placeholder="pytest" style={{ width: '100%' }} />
            </label>
            <label style={{ fontSize: 12 }}>
              Branch
              <input value={branch} onChange={e => setBranch(e.target.value)} disabled={busy} placeholder="feature/example" style={{ width: '100%' }} />
            </label>
            <label style={{ fontSize: 12 }}>
              Status
              <select value={status} onChange={e => setStatus(e.target.value as CIEventStatus)} disabled={busy} style={{ width: '100%' }}>
                <option value="queued">queued</option>
                <option value="in_progress">in_progress</option>
                <option value="completed">completed</option>
                <option value="failed">failed</option>
              </select>
            </label>
            <label style={{ fontSize: 12 }}>
              Conclusion
              <select value={conclusion} onChange={e => setConclusion(e.target.value as CIEventConclusion)} disabled={busy} style={{ width: '100%' }}>
                <option value="failure">failure</option>
                <option value="success">success</option>
                <option value="cancelled">cancelled</option>
                <option value="skipped">skipped</option>
                <option value="timed_out">timed_out</option>
                <option value="neutral">neutral</option>
                <option value="unknown">unknown</option>
              </select>
            </label>
            <label style={{ fontSize: 12, gridColumn: '1 / span 2' }}>
              Failure summary
              <input value={failureSummary} onChange={e => setFailureSummary(e.target.value)} disabled={busy} placeholder="pytest failed" style={{ width: '100%' }} />
            </label>
            <label style={{ fontSize: 12, gridColumn: '1 / span 2' }}>
              Logs excerpt
              <textarea
                value={logsExcerpt}
                onChange={e => setLogsExcerpt(e.target.value)}
                disabled={busy}
                rows={3}
                placeholder="Short logs excerpt (no secrets)"
                style={{ width: '100%', fontFamily: 'monospace', fontSize: 12 }}
              />
            </label>
            <div style={{ gridColumn: '1 / span 2' }}>
              <button type="submit" disabled={busy} className="primary">Record CI event</button>
            </div>
          </form>

          {events.length === 0
            ? <p style={{ fontSize: 12, color: '#666' }}>No CI events yet.</p>
            : events.map(ev => (
                <CIEventCard
                  key={ev.id}
                  event={ev}
                  analyses={analysesByEvent[ev.id] || []}
                  busy={busy}
                  onLoadAnalyses={() => loadAnalyses(ev.id)}
                  onRequestAnalysis={() => handleRequestAnalysis(ev)}
                />
              ))
          }
        </div>
      )}
    </section>
  )
}

function CIEventCard({
  event,
  analyses,
  busy,
  onLoadAnalyses,
  onRequestAnalysis,
}: {
  event: CIEvent
  analyses: CIAnalysis[]
  busy: boolean
  onLoadAnalyses: () => void
  onRequestAnalysis: () => void
}) {
  const [open, setOpen] = useState(false)
  useEffect(() => {
    if (open) onLoadAnalyses()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const latest = analyses[0]

  return (
    <div style={{ border: '1px solid #333', borderRadius: 4, padding: 8, marginBottom: 8, fontSize: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <strong>{event.workflow_name || '(no workflow)'}</strong>
        <span style={{ color: '#888' }}>{event.job_name || '(no job)'}</span>
        <span style={{ color: '#888' }}>{event.branch || ''}</span>
        <span style={ciConclusionStyle(event.conclusion)}>{event.conclusion}</span>
        <span style={{ marginLeft: 'auto', color: '#666', fontSize: 11 }}>
          {new Date(event.created_at).toLocaleString()}
        </span>
      </div>
      {event.failure_summary && (
        <div style={{ marginTop: 4, color: '#ccc' }}>{event.failure_summary}</div>
      )}
      <div style={{ marginTop: 6, display: 'flex', gap: 6 }}>
        <button
          onClick={() => setOpen(o => !o)}
          style={{ background: 'none', border: '1px solid #444', borderRadius: 4, padding: '2px 8px', cursor: 'pointer', fontSize: 11 }}
        >
          {open ? 'Hide' : 'Show'} analyses ({analyses.length})
        </button>
        <button
          onClick={onRequestAnalysis}
          disabled={busy}
          style={{ background: 'none', border: '1px solid #444', borderRadius: 4, padding: '2px 8px', cursor: 'pointer', fontSize: 11 }}
        >
          Request analysis
        </button>
      </div>
      {open && (
        <div style={{ marginTop: 8 }}>
          {!latest && <p style={{ color: '#666' }}>No analyses yet.</p>}
          {latest && (
            <div style={{ borderLeft: '2px solid #444', paddingLeft: 8 }}>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <span className="status">{latest.status}</span>
                {latest.conclusion && <span className="status">{latest.conclusion}</span>}
                <span style={{ color: '#888' }}>{latest.provider}/{latest.model}</span>
              </div>
              {latest.summary && (
                <p style={{ margin: '6px 0' }}>{latest.summary}</p>
              )}
              {latest.likely_root_causes.length > 0 && (
                <div>
                  <strong>Likely root causes</strong>
                  <ul style={{ margin: '4px 0 4px 16px' }}>
                    {latest.likely_root_causes.map((c, i) => <li key={i}>{c}</li>)}
                  </ul>
                </div>
              )}
              {latest.suggested_fixes.length > 0 && (
                <div>
                  <strong>Suggested debugging steps</strong>
                  <ul style={{ margin: '4px 0 4px 16px' }}>
                    {latest.suggested_fixes.map((c, i) => <li key={i}>{c}</li>)}
                  </ul>
                </div>
              )}
              {latest.recommended_next_action && (
                <p style={{ margin: '6px 0' }}>
                  <strong>Recommended next action:</strong> {latest.recommended_next_action}
                </p>
              )}
              {latest.error_message && (
                <p className="error" style={{ marginTop: 6 }}>{latest.error_message}</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
