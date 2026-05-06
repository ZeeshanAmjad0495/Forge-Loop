import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { clearToken, getToken, setToken } from './auth'
import {
  createPlanningRun,
  createProject,
  createProjectRequirement,
  createProjectTicket,
  createRequirementAnalysis,
  createRequirementAnalysisForRequirement,
  getProjectContext,
  listProjectRequirements,
  listProjectTickets,
  listProjects,
  listProviders,
  login,
  updateProjectContext,
} from './api'
import './App.css'
import type {
  Project,
  ProjectContext,
  ProviderInfo,
  Requirement,
  RequirementAnalysis,
  Ticket,
} from './types'

// ---------------------------------------------------------------------------
// View state — discriminated union, no router
// ---------------------------------------------------------------------------

type View =
  | { view: 'projects' }
  | { view: 'project'; project: Project }
  | { view: 'ticket'; project: Project; ticket: Ticket }
  | { view: 'requirement'; project: Project; requirement: Requirement }

function splitLines(value: string): string[] {
  return value
    .split('\n')
    .map(s => s.trim())
    .filter(Boolean)
}


// ---------------------------------------------------------------------------
// Login screen
// ---------------------------------------------------------------------------

function LoginScreen({ onLogin }: { onLogin: () => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await login(email.trim(), password)
      setToken(res.access_token)
      onLogin()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1>ForgeLoop</h1>
      <form onSubmit={handleSubmit}>
        <label htmlFor="login-email">Email</label>
        <input
          id="login-email"
          type="email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          placeholder="admin@example.com"
          required
          disabled={loading}
        />
        <label htmlFor="login-password">Password</label>
        <input
          id="login-password"
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          required
          disabled={loading}
        />
        {error && <div className="error">{error}</div>}
        <button type="submit" disabled={loading}>
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Projects list view
// ---------------------------------------------------------------------------

function ProjectsView({
  onSelectProject,
}: {
  onSelectProject: (project: Project) => void
}) {
  const [projects, setProjects] = useState<Project[]>([])
  const [loadError, setLoadError] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [repoUrl, setRepoUrl] = useState('')
  const [techStack, setTechStack] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')

  useEffect(() => {
    listProjects()
      .then(setProjects)
      .catch(err => setLoadError((err as Error).message))
  }, [])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setCreateError('')
    setCreating(true)
    try {
      const stack = techStack
        .split(',')
        .map(s => s.trim())
        .filter(Boolean)
      const project = await createProject({
        name: name.trim(),
        description: description.trim(),
        repo_url: repoUrl.trim() || null,
        tech_stack: stack,
      })
      setProjects(prev => [...prev, project])
      setName('')
      setDescription('')
      setRepoUrl('')
      setTechStack('')
    } catch (err) {
      setCreateError((err as Error).message)
    } finally {
      setCreating(false)
    }
  }

  return (
    <div>
      <h2>Projects</h2>
      {loadError && <div className="error">{loadError}</div>}

      {projects.length > 0 && (
        <div className="project-list">
          {projects.map(p => (
            <button
              key={p.id}
              className="project-card"
              onClick={() => onSelectProject(p)}
            >
              <strong>{p.name}</strong>
              <p>{p.description}</p>
              {p.tech_stack.length > 0 && (
                <div className="tech-stack">
                  {p.tech_stack.map(t => (
                    <span key={t} className="tech-badge">{t}</span>
                  ))}
                </div>
              )}
            </button>
          ))}
        </div>
      )}

      <h3>New project</h3>
      <form onSubmit={handleCreate}>
        <label htmlFor="proj-name">Name</label>
        <input
          id="proj-name"
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="e.g. ForgeLoop API"
          required
          disabled={creating}
        />
        <label htmlFor="proj-desc">Description</label>
        <textarea
          id="proj-desc"
          value={description}
          onChange={e => setDescription(e.target.value)}
          placeholder="What does this project do?"
          required
          disabled={creating}
        />
        <label htmlFor="proj-repo">Repo URL (optional)</label>
        <input
          id="proj-repo"
          value={repoUrl}
          onChange={e => setRepoUrl(e.target.value)}
          placeholder="https://github.com/org/repo"
          disabled={creating}
        />
        <label htmlFor="proj-stack">Tech stack (comma-separated, optional)</label>
        <input
          id="proj-stack"
          value={techStack}
          onChange={e => setTechStack(e.target.value)}
          placeholder="python, react, postgresql"
          disabled={creating}
        />
        {createError && <div className="error">{createError}</div>}
        <button type="submit" disabled={creating}>
          {creating ? 'Creating…' : 'Create project'}
        </button>
      </form>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Project detail view — context editor + ticket list + create ticket
// ---------------------------------------------------------------------------

function ProjectView({
  project,
  onBack,
  onSelectTicket,
  onSelectRequirement,
  providers,
  selectedProvider,
  onProviderChange,
}: {
  project: Project
  onBack: () => void
  onSelectTicket: (ticket: Ticket) => void
  onSelectRequirement: (requirement: Requirement) => void
  providers: ProviderInfo[]
  selectedProvider: string
  onProviderChange: (name: string) => void
}) {
  // Context state
  const [ctx, setCtx] = useState<ProjectContext | null>(null)
  const [ctxSaving, setCtxSaving] = useState(false)
  const [ctxError, setCtxError] = useState('')
  const [ctxSaved, setCtxSaved] = useState(false)

  // Tickets state
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [ticketError, setTicketError] = useState('')

  // Create ticket form
  const [ticketTitle, setTicketTitle] = useState('')
  const [ticketDesc, setTicketDesc] = useState('')
  const [ticketCreating, setTicketCreating] = useState(false)
  const [ticketCreateError, setTicketCreateError] = useState('')

  // Requirements state
  const [requirements, setRequirements] = useState<Requirement[]>([])
  const [reqLoadError, setReqLoadError] = useState('')

  // Create requirement form
  const [reqTitle, setReqTitle] = useState('')
  const [reqProblem, setReqProblem] = useState('')
  const [reqGoal, setReqGoal] = useState('')
  const [reqUsers, setReqUsers] = useState('')
  const [reqFunc, setReqFunc] = useState('')
  const [reqNonFunc, setReqNonFunc] = useState('')
  const [reqAccept, setReqAccept] = useState('')
  const [reqConstraints, setReqConstraints] = useState('')
  const [reqNonGoals, setReqNonGoals] = useState('')
  const [reqAssumptions, setReqAssumptions] = useState('')
  const [reqCreating, setReqCreating] = useState(false)
  const [reqCreateError, setReqCreateError] = useState('')

  useEffect(() => {
    getProjectContext(project.id)
      .then(setCtx)
      .catch(err => setCtxError((err as Error).message))
    listProjectTickets(project.id)
      .then(setTickets)
      .catch(err => setTicketError((err as Error).message))
    listProjectRequirements(project.id)
      .then(setRequirements)
      .catch(err => setReqLoadError((err as Error).message))
  }, [project.id])

  function updateCtxField(field: keyof Omit<ProjectContext, 'project_id' | 'updated_at'>, value: string) {
    setCtx(prev =>
      prev
        ? { ...prev, [field]: value }
        : {
            project_id: project.id,
            architecture_notes: '',
            coding_standards: '',
            test_commands: '',
            deployment_commands: '',
            domain_rules: '',
            safety_rules: '',
            updated_at: null,
            [field]: value,
          },
    )
    setCtxSaved(false)
  }

  async function handleSaveContext(e: React.FormEvent) {
    e.preventDefault()
    if (!ctx) return
    setCtxSaving(true)
    setCtxError('')
    setCtxSaved(false)
    try {
      const saved = await updateProjectContext(project.id, {
        architecture_notes: ctx.architecture_notes,
        coding_standards: ctx.coding_standards,
        test_commands: ctx.test_commands,
        deployment_commands: ctx.deployment_commands,
        domain_rules: ctx.domain_rules,
        safety_rules: ctx.safety_rules,
      })
      setCtx(saved)
      setCtxSaved(true)
    } catch (err) {
      setCtxError((err as Error).message)
    } finally {
      setCtxSaving(false)
    }
  }

  async function handleCreateRequirement(e: React.FormEvent) {
    e.preventDefault()
    setReqCreateError('')
    setReqCreating(true)
    try {
      const created = await createProjectRequirement(project.id, {
        title: reqTitle.trim(),
        problem_statement: reqProblem.trim(),
        business_goal: reqGoal.trim(),
        target_users: splitLines(reqUsers),
        functional_requirements: splitLines(reqFunc),
        non_functional_requirements: splitLines(reqNonFunc),
        acceptance_criteria: splitLines(reqAccept),
        constraints: splitLines(reqConstraints),
        non_goals: splitLines(reqNonGoals),
        assumptions: splitLines(reqAssumptions),
      })
      setRequirements(prev => [...prev, created])
      setReqTitle('')
      setReqProblem('')
      setReqGoal('')
      setReqUsers('')
      setReqFunc('')
      setReqNonFunc('')
      setReqAccept('')
      setReqConstraints('')
      setReqNonGoals('')
      setReqAssumptions('')
    } catch (err) {
      setReqCreateError((err as Error).message)
    } finally {
      setReqCreating(false)
    }
  }

  async function handleCreateTicket(e: React.FormEvent) {
    e.preventDefault()
    setTicketCreateError('')
    setTicketCreating(true)
    try {
      const ticket = await createProjectTicket(project.id, ticketTitle.trim(), ticketDesc.trim())
      setTickets(prev => [...prev, ticket])
      setTicketTitle('')
      setTicketDesc('')
    } catch (err) {
      setTicketCreateError((err as Error).message)
    } finally {
      setTicketCreating(false)
    }
  }

  return (
    <div>
      <button className="back-link" onClick={onBack}>← Projects</button>
      <h2>{project.name}</h2>
      <p className="project-description">{project.description}</p>
      {project.tech_stack.length > 0 && (
        <div className="tech-stack">
          {project.tech_stack.map(t => (
            <span key={t} className="tech-badge">{t}</span>
          ))}
        </div>
      )}

      {/* Context editor */}
      <section className="context-section">
        <h3>Project context</h3>
        <p className="section-hint">
          This context is injected into planning prompts for every ticket in this project.
        </p>
        {ctxError && <div className="error">{ctxError}</div>}
        <form onSubmit={handleSaveContext}>
          {(
            [
              ['architecture_notes', 'Architecture notes'],
              ['coding_standards', 'Coding standards'],
              ['test_commands', 'Test commands'],
              ['deployment_commands', 'Deployment commands'],
              ['domain_rules', 'Domain rules'],
              ['safety_rules', 'Safety rules'],
            ] as const
          ).map(([field, label]) => (
            <div key={field}>
              <label htmlFor={`ctx-${field}`}>{label}</label>
              <textarea
                id={`ctx-${field}`}
                className="ctx-textarea"
                value={ctx?.[field] ?? ''}
                onChange={e => updateCtxField(field, e.target.value)}
                disabled={ctxSaving}
                placeholder="Leave blank if not applicable"
              />
            </div>
          ))}
          <div className="ctx-actions">
            <button type="submit" disabled={ctxSaving}>
              {ctxSaving ? 'Saving…' : 'Save context'}
            </button>
            {ctxSaved && <span className="ctx-saved">Saved</span>}
          </div>
        </form>
      </section>

      {/* Ticket list */}
      <section className="tickets-section">
        <h3>Tickets</h3>
        {ticketError && <div className="error">{ticketError}</div>}
        {tickets.length > 0 && (
          <div className="ticket-list">
            {tickets.map(t => (
              <button
                key={t.id}
                className={`ticket-row ${t.status === 'brief_generated' ? 'done' : ''}`}
                onClick={() => onSelectTicket(t)}
              >
                <span className="ticket-row-title">{t.title}</span>
                <span className="ticket-row-status">
                  {t.status === 'brief_generated' ? 'Brief generated' : 'Created'}
                </span>
              </button>
            ))}
          </div>
        )}

        <h4>New ticket</h4>
        <form onSubmit={handleCreateTicket}>
          <label htmlFor="ticket-title">Title</label>
          <input
            id="ticket-title"
            value={ticketTitle}
            onChange={e => setTicketTitle(e.target.value)}
            placeholder="Short description of the work"
            required
            disabled={ticketCreating}
          />
          <label htmlFor="ticket-desc">Description</label>
          <textarea
            id="ticket-desc"
            value={ticketDesc}
            onChange={e => setTicketDesc(e.target.value)}
            placeholder="Provide enough context for the planning agent"
            required
            disabled={ticketCreating}
          />
          {providers.length > 0 && (
            <div className="provider-select">
              <label htmlFor="provider">LLM provider</label>
              <select
                id="provider"
                value={selectedProvider}
                onChange={e => onProviderChange(e.target.value)}
                disabled={ticketCreating}
              >
                {providers.map(p => (
                  <option key={p.name} value={p.name} disabled={!p.configured}>
                    {p.name} ({p.default_model}){p.configured ? '' : ' — not configured'}
                  </option>
                ))}
              </select>
            </div>
          )}
          {ticketCreateError && <div className="error">{ticketCreateError}</div>}
          <button type="submit" disabled={ticketCreating}>
            {ticketCreating ? 'Creating…' : 'Create ticket'}
          </button>
        </form>
      </section>

      {/* Requirements list + create */}
      <section className="requirements-section">
        <h3>Requirements</h3>
        <p className="section-hint">
          Structured requirements capture richer intake (problem, goal, criteria, constraints).
        </p>
        {reqLoadError && <div className="error">{reqLoadError}</div>}
        {requirements.length > 0 && (
          <div className="ticket-list">
            {requirements.map(r => (
              <button
                key={r.id}
                className={`ticket-row ${r.status === 'analyzed' ? 'done' : ''}`}
                onClick={() => onSelectRequirement(r)}
              >
                <span className="ticket-row-title">{r.title}</span>
                <span className="ticket-row-status">{r.status}</span>
              </button>
            ))}
          </div>
        )}

        <h4>New requirement</h4>
        <form onSubmit={handleCreateRequirement}>
          <label htmlFor="req-title">Title</label>
          <input
            id="req-title"
            value={reqTitle}
            onChange={e => setReqTitle(e.target.value)}
            placeholder="Short name for the requirement"
            required
            disabled={reqCreating}
          />
          <label htmlFor="req-problem">Problem statement</label>
          <textarea
            id="req-problem"
            value={reqProblem}
            onChange={e => setReqProblem(e.target.value)}
            placeholder="What problem are we solving?"
            disabled={reqCreating}
          />
          <label htmlFor="req-goal">Business goal</label>
          <textarea
            id="req-goal"
            value={reqGoal}
            onChange={e => setReqGoal(e.target.value)}
            placeholder="Why does this matter?"
            disabled={reqCreating}
          />
          {(
            [
              ['req-users', 'Target users (one per line)', reqUsers, setReqUsers],
              ['req-func', 'Functional requirements (one per line)', reqFunc, setReqFunc],
              ['req-nonfunc', 'Non-functional requirements (one per line)', reqNonFunc, setReqNonFunc],
              ['req-accept', 'Acceptance criteria (one per line)', reqAccept, setReqAccept],
              ['req-constraints', 'Constraints (one per line)', reqConstraints, setReqConstraints],
              ['req-nongoals', 'Non-goals (one per line)', reqNonGoals, setReqNonGoals],
              ['req-assumptions', 'Assumptions (one per line)', reqAssumptions, setReqAssumptions],
            ] as const
          ).map(([id, label, value, setter]) => (
            <div key={id}>
              <label htmlFor={id}>{label}</label>
              <textarea
                id={id}
                value={value}
                onChange={e => setter(e.target.value)}
                disabled={reqCreating}
              />
            </div>
          ))}
          {reqCreateError && <div className="error">{reqCreateError}</div>}
          <button type="submit" disabled={reqCreating}>
            {reqCreating ? 'Creating…' : 'Create requirement'}
          </button>
        </form>
      </section>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Ticket view — requirement analysis + planning brief
// ---------------------------------------------------------------------------

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

function ReadinessBadge({ readiness }: { readiness: RequirementAnalysis['readiness'] }) {
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

function RequirementAnalysisPanel({ analysis }: { analysis: RequirementAnalysis }) {
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

function TicketView({
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

      {/* Requirement analysis */}
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

      {/* Planning brief */}
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

// ---------------------------------------------------------------------------
// Requirement view — structured requirement details + analysis
// ---------------------------------------------------------------------------

function RequirementBulletList({ label, items }: { label: string; items: string[] }) {
  if (items.length === 0) return null
  return (
    <>
      <strong>{label}</strong>
      <ul>
        {items.map((x, i) => <li key={i}>{x}</li>)}
      </ul>
    </>
  )
}

function RequirementView({
  requirement: initialRequirement,
  project,
  onBack,
  providers,
  selectedProvider,
  onProviderChange,
}: {
  requirement: Requirement
  project: Project
  onBack: () => void
  providers: ProviderInfo[]
  selectedProvider: string
  onProviderChange: (name: string) => void
}) {
  const [requirement, setRequirement] = useState(initialRequirement)
  const [phase, setPhase] = useState<AnalysisPhase>({ name: 'idle' })

  async function handleAnalyze() {
    setPhase({ name: 'analyzing' })
    try {
      const result = await createRequirementAnalysisForRequirement(
        requirement.id,
        selectedProvider || undefined,
      )
      setRequirement(prev => ({ ...prev, status: 'analyzed' }))
      setPhase({ name: 'done', analysis: result.requirement_analysis })
    } catch (err) {
      setPhase({ name: 'error', message: (err as Error).message })
    }
  }

  return (
    <div>
      <button className="back-link" onClick={onBack}>← {project.name}</button>
      <h2>{requirement.title}</h2>
      <p>
        <span className={`status ${requirement.status === 'analyzed' ? 'done' : ''}`}>
          {requirement.status}
        </span>
      </p>

      {requirement.problem_statement && (
        <>
          <strong>Problem statement</strong>
          <p>{requirement.problem_statement}</p>
        </>
      )}
      {requirement.business_goal && (
        <>
          <strong>Business goal</strong>
          <p>{requirement.business_goal}</p>
        </>
      )}
      <RequirementBulletList label="Target users" items={requirement.target_users} />
      <RequirementBulletList label="Functional requirements" items={requirement.functional_requirements} />
      <RequirementBulletList label="Non-functional requirements" items={requirement.non_functional_requirements} />
      <RequirementBulletList label="Acceptance criteria" items={requirement.acceptance_criteria} />
      <RequirementBulletList label="Constraints" items={requirement.constraints} />
      <RequirementBulletList label="Non-goals" items={requirement.non_goals} />
      <RequirementBulletList label="Assumptions" items={requirement.assumptions} />

      {providers.length > 0 && phase.name !== 'done' && (
        <div className="provider-select">
          <label htmlFor="req-provider">LLM provider</label>
          <select
            id="req-provider"
            value={selectedProvider}
            onChange={e => onProviderChange(e.target.value)}
            disabled={phase.name === 'analyzing'}
          >
            {providers.map(p => (
              <option key={p.name} value={p.name} disabled={!p.configured}>
                {p.name} ({p.default_model}){p.configured ? '' : ' — not configured'}
              </option>
            ))}
          </select>
        </div>
      )}

      {phase.name === 'error' && <div className="error">{phase.message}</div>}
      {phase.name !== 'done' && (
        <button onClick={handleAnalyze} disabled={phase.name === 'analyzing'}>
          {phase.name === 'analyzing' ? 'Analyzing…' : 'Analyze requirement'}
        </button>
      )}
      {phase.name === 'done' && (
        <>
          <h3>Requirement Analysis</h3>
          <RequirementAnalysisPanel analysis={phase.analysis} />
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Root App — auth gate + view router
// ---------------------------------------------------------------------------

export default function App() {
  const [authed, setAuthed] = useState<boolean>(() => Boolean(getToken()))
  const [currentView, setCurrentView] = useState<View>({ view: 'projects' })
  const [providers, setProviders] = useState<ProviderInfo[]>([])
  const [selectedProvider, setSelectedProvider] = useState<string>('')

  useEffect(() => {
    if (!authed) return
    listProviders()
      .then(res => {
        setProviders(res.providers)
        setSelectedProvider(res.default_provider)
      })
      .catch(err => {
        if ((err as Error).message.startsWith('401')) setAuthed(false)
        setProviders([])
        setSelectedProvider('')
      })
  }, [authed])

  function handleLogout() {
    clearToken()
    setAuthed(false)
    setCurrentView({ view: 'projects' })
    setProviders([])
    setSelectedProvider('')
  }

  if (!authed) {
    return <LoginScreen onLogin={() => setAuthed(true)} />
  }

  return (
    <>
      <div className="app-header">
        <h1>ForgeLoop</h1>
        <button className="logout" onClick={handleLogout}>Sign out</button>
      </div>

      {currentView.view === 'projects' && (
        <ProjectsView
          onSelectProject={project => setCurrentView({ view: 'project', project })}
        />
      )}

      {currentView.view === 'project' && (
        <ProjectView
          project={currentView.project}
          onBack={() => setCurrentView({ view: 'projects' })}
          onSelectTicket={ticket =>
            setCurrentView({ view: 'ticket', project: currentView.project, ticket })
          }
          onSelectRequirement={requirement =>
            setCurrentView({ view: 'requirement', project: currentView.project, requirement })
          }
          providers={providers}
          selectedProvider={selectedProvider}
          onProviderChange={setSelectedProvider}
        />
      )}

      {currentView.view === 'ticket' && (
        <TicketView
          ticket={currentView.ticket}
          project={currentView.project}
          onBack={_updatedTicket =>
            setCurrentView({ view: 'project', project: currentView.project })
          }
          providers={providers}
          selectedProvider={selectedProvider}
          onProviderChange={setSelectedProvider}
        />
      )}

      {currentView.view === 'requirement' && (
        <RequirementView
          requirement={currentView.requirement}
          project={currentView.project}
          onBack={() => setCurrentView({ view: 'project', project: currentView.project })}
          providers={providers}
          selectedProvider={selectedProvider}
          onProviderChange={setSelectedProvider}
        />
      )}
    </>
  )
}
