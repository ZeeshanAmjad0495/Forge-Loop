import { useEffect, useState } from 'react'
import {
  createIncidentAnalysis,
  listIncidentAnalyses,
  listProjectIncidents,
  prepareIncidentRemediation,
  recordIncident,
  updateIncident,
} from '../../api'
import type {
  Incident,
  IncidentAnalysis,
  IncidentSeverity,
  IncidentSource,
  IncidentStatus,
  RemediationWorkItemDraft,
} from '../../types'
import { INCIDENT_STATUSES } from '../../lib/constants'
import { incidentSeverityStyle, incidentStatusStyle } from '../../lib/status'

export function IncidentsPanel({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState(false)
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [analysesByIncident, setAnalysesByIncident] = useState<Record<string, IncidentAnalysis[]>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [severity, setSeverity] = useState<IncidentSeverity>('sev3')
  const [source, setSource] = useState<IncidentSource>('manual')
  const [environment, setEnvironment] = useState('production')
  const [affectedArea, setAffectedArea] = useState('')
  const [evidence, setEvidence] = useState('')

  useEffect(() => {
    if (!open) return
    listProjectIncidents(projectId).then(setIncidents).catch(() => {})
  }, [open, projectId])

  async function refresh() {
    try {
      setIncidents(await listProjectIncidents(projectId))
    } catch { /* non-critical */ }
  }

  async function loadAnalyses(incidentId: string) {
    try {
      const analyses = await listIncidentAnalyses(incidentId)
      setAnalysesByIncident(prev => ({ ...prev, [incidentId]: analyses }))
    } catch { /* non-critical */ }
  }

  async function handleRecord(e: React.FormEvent) {
    e.preventDefault()
    if (!title.trim() || !description.trim()) {
      setError('Title and description are required.')
      return
    }
    setBusy(true)
    setError('')
    try {
      await recordIncident(projectId, {
        title: title.trim(),
        description: description.trim(),
        severity,
        source,
        environment: environment || null,
        affected_area: affectedArea || null,
        evidence: evidence || null,
      })
      setTitle('')
      setDescription('')
      setAffectedArea('')
      setEvidence('')
      await refresh()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function handleRequestAnalysis(incident: Incident) {
    setBusy(true)
    setError('')
    try {
      const analysis = await createIncidentAnalysis(incident.id, {})
      setAnalysesByIncident(prev => ({
        ...prev,
        [incident.id]: [analysis, ...(prev[incident.id] || [])],
      }))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function handleStatusChange(incident: Incident, status: IncidentStatus) {
    setBusy(true)
    setError('')
    try {
      const updated = await updateIncident(incident.id, { status })
      setIncidents(prev => prev.map(i => (i.id === updated.id ? updated : i)))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function handlePrepareRemediation(incident: Incident): Promise<RemediationWorkItemDraft | null> {
    setBusy(true)
    setError('')
    try {
      const draft = await prepareIncidentRemediation(incident.id)
      await refresh()
      return draft
    } catch (err) {
      setError((err as Error).message)
      return null
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
        {open ? '▾' : '▸'} Incidents ({incidents.length})
      </button>
      {open && (
        <div style={{ marginTop: 12 }}>
          <p style={{ fontSize: 12, color: '#888', margin: '0 0 8px' }}>
            Incidents are recorded manually or programmatically. ForgeLoop does
            not connect to monitoring providers (Cloud Logging, Sentry,
            Datadog, etc.) and does not auto-detect or auto-remediate. Triage
            analyses are advisory only — humans approve every remediation step.
          </p>
          {error && <div className="error" style={{ marginBottom: 6, fontSize: 12 }}>{error}</div>}

          <form onSubmit={handleRecord} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
            <label style={{ fontSize: 12, gridColumn: '1 / span 2' }}>
              Title
              <input value={title} onChange={e => setTitle(e.target.value)} disabled={busy} placeholder="Production API latency spike" style={{ width: '100%' }} />
            </label>
            <label style={{ fontSize: 12 }}>
              Severity
              <select value={severity} onChange={e => setSeverity(e.target.value as IncidentSeverity)} disabled={busy} style={{ width: '100%' }}>
                <option value="sev1">sev1</option>
                <option value="sev2">sev2</option>
                <option value="sev3">sev3</option>
                <option value="sev4">sev4</option>
                <option value="unknown">unknown</option>
              </select>
            </label>
            <label style={{ fontSize: 12 }}>
              Source
              <select value={source} onChange={e => setSource(e.target.value as IncidentSource)} disabled={busy} style={{ width: '100%' }}>
                <option value="manual">manual</option>
                <option value="ci_failure">ci_failure</option>
                <option value="production_log">production_log</option>
                <option value="monitoring">monitoring</option>
                <option value="user_report">user_report</option>
                <option value="support">support</option>
                <option value="custom">custom</option>
              </select>
            </label>
            <label style={{ fontSize: 12 }}>
              Environment
              <input value={environment} onChange={e => setEnvironment(e.target.value)} disabled={busy} placeholder="production" style={{ width: '100%' }} />
            </label>
            <label style={{ fontSize: 12 }}>
              Affected area
              <input value={affectedArea} onChange={e => setAffectedArea(e.target.value)} disabled={busy} placeholder="checkout-api" style={{ width: '100%' }} />
            </label>
            <label style={{ fontSize: 12, gridColumn: '1 / span 2' }}>
              Description
              <textarea
                value={description}
                onChange={e => setDescription(e.target.value)}
                disabled={busy}
                rows={2}
                placeholder="Users report increased latency on checkout API."
                style={{ width: '100%' }}
              />
            </label>
            <label style={{ fontSize: 12, gridColumn: '1 / span 2' }}>
              Evidence (logs, notes, support report — no secrets)
              <textarea
                value={evidence}
                onChange={e => setEvidence(e.target.value)}
                disabled={busy}
                rows={3}
                placeholder="p99 latency rose from 200ms to 1800ms over 10m."
                style={{ width: '100%', fontFamily: 'monospace', fontSize: 12 }}
              />
            </label>
            <div style={{ gridColumn: '1 / span 2' }}>
              <button type="submit" disabled={busy} className="primary">Record incident</button>
            </div>
          </form>

          {incidents.length === 0
            ? <p style={{ fontSize: 12, color: '#666' }}>No incidents yet.</p>
            : incidents.map(inc => (
                <IncidentCard
                  key={inc.id}
                  incident={inc}
                  analyses={analysesByIncident[inc.id] || []}
                  busy={busy}
                  onLoadAnalyses={() => loadAnalyses(inc.id)}
                  onRequestAnalysis={() => handleRequestAnalysis(inc)}
                  onStatusChange={status => handleStatusChange(inc, status)}
                  onPrepareRemediation={() => handlePrepareRemediation(inc)}
                />
              ))
          }
        </div>
      )}
    </section>
  )
}

function IncidentCard({
  incident,
  analyses,
  busy,
  onLoadAnalyses,
  onRequestAnalysis,
  onStatusChange,
  onPrepareRemediation,
}: {
  incident: Incident
  analyses: IncidentAnalysis[]
  busy: boolean
  onLoadAnalyses: () => void
  onRequestAnalysis: () => void
  onStatusChange: (status: IncidentStatus) => void
  onPrepareRemediation: () => Promise<RemediationWorkItemDraft | null>
}) {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState<RemediationWorkItemDraft | null>(null)
  useEffect(() => {
    if (open) onLoadAnalyses()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const latest = analyses[0]

  async function handlePrepare() {
    const result = await onPrepareRemediation()
    if (result) setDraft(result)
  }

  return (
    <div style={{ border: '1px solid #333', borderRadius: 4, padding: 8, marginBottom: 8, fontSize: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <strong>{incident.title}</strong>
        <span style={incidentSeverityStyle(incident.severity)}>{incident.severity}</span>
        <span style={incidentStatusStyle(incident.status)}>{incident.status}</span>
        <span style={{ color: '#888' }}>{incident.source}</span>
        {incident.environment && <span style={{ color: '#888' }}>{incident.environment}</span>}
        {incident.affected_area && <span style={{ color: '#888' }}>{incident.affected_area}</span>}
        <span style={{ marginLeft: 'auto', color: '#666', fontSize: 11 }}>
          {new Date(incident.created_at).toLocaleString()}
        </span>
      </div>
      {incident.description && (
        <div style={{ marginTop: 4, color: '#ccc' }}>{incident.description}</div>
      )}
      {(incident.ci_event_id || incident.pr_draft_id || incident.dev_task_id) && (
        <div style={{ marginTop: 4, color: '#888', fontSize: 11 }}>
          {incident.ci_event_id && <span>linked CI event: {incident.ci_event_id.slice(0, 8)} </span>}
          {incident.pr_draft_id && <span>linked PR draft: {incident.pr_draft_id.slice(0, 8)} </span>}
          {incident.dev_task_id && <span>linked dev task: {incident.dev_task_id.slice(0, 8)}</span>}
        </div>
      )}
      <div style={{ marginTop: 6, display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
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
        <button
          onClick={handlePrepare}
          disabled={busy}
          style={{ background: 'none', border: '1px solid #444', borderRadius: 4, padding: '2px 8px', cursor: 'pointer', fontSize: 11 }}
        >
          Prepare remediation
        </button>
        <label style={{ fontSize: 11, color: '#888' }}>
          Status:&nbsp;
          <select
            value={incident.status}
            onChange={e => onStatusChange(e.target.value as IncidentStatus)}
            disabled={busy}
          >
            {INCIDENT_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
      </div>
      {draft && (
        <div style={{ marginTop: 8, borderLeft: '2px solid #888', paddingLeft: 8 }}>
          <strong>Remediation work item draft</strong>
          <p style={{ margin: '4px 0', color: '#ccc' }}>{draft.title}</p>
          <p style={{ margin: '4px 0', whiteSpace: 'pre-wrap' }}>{draft.description}</p>
          <p style={{ margin: '4px 0', color: '#888', fontSize: 11 }}>
            Requires human approval. ForgeLoop did not create a DevTask, branch, PR, or deployment.
          </p>
        </div>
      )}
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
              {latest.impact_assessment && (
                <p style={{ margin: '6px 0' }}>
                  <strong>Impact:</strong> {latest.impact_assessment}
                </p>
              )}
              {latest.likely_root_causes.length > 0 && (
                <div>
                  <strong>Likely root causes</strong>
                  <ul style={{ margin: '4px 0 4px 16px' }}>
                    {latest.likely_root_causes.map((c, i) => <li key={i}>{c}</li>)}
                  </ul>
                </div>
              )}
              {latest.immediate_actions.length > 0 && (
                <div>
                  <strong>Immediate safe actions</strong>
                  <ul style={{ margin: '4px 0 4px 16px' }}>
                    {latest.immediate_actions.map((c, i) => <li key={i}>{c}</li>)}
                  </ul>
                </div>
              )}
              {latest.remediation_plan.length > 0 && (
                <div>
                  <strong>Remediation plan</strong>
                  <ul style={{ margin: '4px 0 4px 16px' }}>
                    {latest.remediation_plan.map((c, i) => <li key={i}>{c}</li>)}
                  </ul>
                </div>
              )}
              {latest.prevention_actions.length > 0 && (
                <div>
                  <strong>Prevention actions</strong>
                  <ul style={{ margin: '4px 0 4px 16px' }}>
                    {latest.prevention_actions.map((c, i) => <li key={i}>{c}</li>)}
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
