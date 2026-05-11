import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { createPlanningRun, createRequirementAnalysis } from '../api'
import type {
  Project,
  ProviderInfo,
  RequirementAnalysis,
  Ticket,
} from '../types'

type AnalysisPhase =
  | { name: 'idle' }
  | { name: 'analyzing' }
  | { name: 'done'; analysis: RequirementAnalysis }
  | { name: 'error'; message: string }

type BriefPhase =
  | { name: 'idle' }
  | { name: 'generating' }
  | { name: 'done'; brief: string }
  | { name: 'error'; message: string }

export function ReadinessBadge({ readiness }: { readiness: RequirementAnalysis['readiness'] }) {
  const ready = readiness === 'ready_for_planning'
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        borderRadius: 4,
        fontSize: 12,
        fontWeight: 600,
        background: ready ? '#d4edda' : '#fff3cd',
        color: ready ? '#155724' : '#856404',
        border: `1px solid ${ready ? '#c3e6cb' : '#ffeeba'}`,
        marginBottom: 8,
      }}
    >
      {ready ? '✓ Ready for planning' : '⚠ Needs clarification'}
    </span>
  )
}

export function RequirementAnalysisPanel({ analysis }: { analysis: RequirementAnalysis }) {
  return (
    <div style={{ marginTop: 12, marginBottom: 16 }}>
      <ReadinessBadge readiness={analysis.readiness} />

      {analysis.summary && (
        <p style={{ margin: '6px 0', fontStyle: 'italic' }}>{analysis.summary}</p>
      )}

      {analysis.ambiguities.length > 0 && (
        <>
          <strong>Ambiguities</strong>
          <ul>
            {analysis.ambiguities.map((a, i) => <li key={i}>{a}</li>)}
          </ul>
        </>
      )}

      {analysis.clarification_questions.length > 0 && (
        <>
          <strong>Clarification questions</strong>
          <ul>
            {analysis.clarification_questions.map((q, i) => <li key={i}>{q}</li>)}
          </ul>
        </>
      )}

      {analysis.risks.length > 0 && (
        <>
          <strong>Risks</strong>
          <ul>
            {analysis.risks.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </>
      )}

      {analysis.affected_areas.length > 0 && (
        <>
          <strong>Affected areas</strong>
          <ul>
            {analysis.affected_areas.map((a, i) => <li key={i}>{a}</li>)}
          </ul>
        </>
      )}
    </div>
  )
}

export function TicketView({
  ticket: initialTicket,
  project,
  onBack,
  providers,
  selectedProvider,
  onProviderChange,
}: {
  ticket: Ticket
  project: Project
  onBack: (updatedTicket: Ticket) => void
  providers: ProviderInfo[]
  selectedProvider: string
  onProviderChange: (name: string) => void
}) {
  const [ticket, setTicket] = useState(initialTicket)
  const [analysisPhase, setAnalysisPhase] = useState<AnalysisPhase>({ name: 'idle' })
  const [briefPhase, setBriefPhase] = useState<BriefPhase>({ name: 'idle' })

  const busy = analysisPhase.name === 'analyzing' || briefPhase.name === 'generating'

  async function handleAnalyzeRequirement() {
    setAnalysisPhase({ name: 'analyzing' })
    try {
      const result = await createRequirementAnalysis(ticket.id, selectedProvider || undefined)
      setAnalysisPhase({ name: 'done', analysis: result.requirement_analysis })
    } catch (err) {
      setAnalysisPhase({ name: 'error', message: (err as Error).message })
    }
  }

  async function handleGenerateBrief() {
    setBriefPhase({ name: 'generating' })
    try {
      const result = await createPlanningRun(ticket.id, selectedProvider || undefined)
      setTicket(prev => ({ ...prev, status: 'brief_generated' }))
      setBriefPhase({ name: 'done', brief: result.artifact.content })
    } catch (err) {
      setBriefPhase({ name: 'error', message: (err as Error).message })
    }
  }

  return (
    <div>
      <button className="back-link" onClick={() => onBack(ticket)}>
        ← {project.name}
      </button>
      <div className="ticket-meta">
        <strong>{ticket.title}</strong>
        <p>{ticket.description}</p>
        <span className={`status ${ticket.status === 'brief_generated' ? 'done' : ''}`}>
          {ticket.status === 'brief_generated' ? 'Brief generated' : 'Created'}
        </span>
      </div>

      {providers.length > 0 && briefPhase.name !== 'done' && (
        <div className="provider-select">
          <label htmlFor="ticket-provider">LLM provider</label>
          <select
            id="ticket-provider"
            value={selectedProvider}
            onChange={e => onProviderChange(e.target.value)}
            disabled={busy}
          >
            {providers.map(p => (
              <option key={p.name} value={p.name} disabled={!p.configured}>
                {p.name} ({p.default_model}){p.configured ? '' : ' — not configured'}
              </option>
            ))}
          </select>
        </div>
      )}

      {analysisPhase.name === 'error' && (
        <div className="error">{analysisPhase.message}</div>
      )}
      {analysisPhase.name !== 'done' && briefPhase.name !== 'done' && (
        <button onClick={handleAnalyzeRequirement} disabled={busy} style={{ marginRight: 8 }}>
          {analysisPhase.name === 'analyzing' ? 'Analyzing…' : 'Analyze requirement'}
        </button>
      )}
      {analysisPhase.name === 'done' && (
        <>
          <h2>Requirement Analysis</h2>
          <RequirementAnalysisPanel analysis={analysisPhase.analysis} />
        </>
      )}

      {briefPhase.name === 'error' && (
        <div className="error">{briefPhase.message}</div>
      )}
      {briefPhase.name !== 'done' && (
        <button onClick={handleGenerateBrief} disabled={busy}>
          {briefPhase.name === 'generating' ? 'Generating brief…' : 'Generate planning brief'}
        </button>
      )}
      {briefPhase.name === 'done' && (
        <>
          <h2>Implementation Brief</h2>
          <div className="brief">
            <ReactMarkdown>{briefPhase.brief}</ReactMarkdown>
          </div>
        </>
      )}
    </div>
  )
}

export type { AnalysisPhase }
