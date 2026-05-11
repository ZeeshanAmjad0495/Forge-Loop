import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { clearToken, getToken, setToken } from './auth'
import {
  createApproval,
  createCheckDefinition,
  createCodeRepository,
  createToolRunnerDefinition,
  createPlanningRun,
  createProject,
  createProjectEpic,
  createProjectRequirement,
  createProjectRequirementGeneration,
  createProjectTicket,
  createRequirementAnalysis,
  createRequirementAnalysisForRequirement,
  createTaskDecomposition,
  decideApproval,
  generateCheckDefinitionsFromSafetyProfile,
  generateDefaultToolRunnerDefinitions,
  getProjectContext,
  getRepoSafetyProfile,
  listDevTaskCheckRuns,
  listDevTaskToolRuns,
  listProjectApprovals,
  listProjectAuditEvents,
  listProjectCheckDefinitions,
  listProjectCheckRuns,
  listProjectCodeRepositories,
  listProjectEpics,
  listProjectRequirements,
  listProjectTickets,
  listProjectToolRunnerDefinitions,
  listProjectToolRuns,
  listProjects,
  listProviders,
  login,
  prepareOpenHandsPackage,
  preparePullRequestDraft,
  listProjectPullRequestDrafts,
  updatePullRequestDraft,
  approvePullRequestDraft,
  createPullRequestReview,
  listPullRequestReviews,
  completePullRequestReview,
  recordCIEvent,
  listProjectCIEvents,
  createCIAnalysis,
  listCIEventAnalyses,
  recordCheckRun,
  recordOpenHandsResult,
  recordToolRun,
  updateCheckDefinition,
  updateCodeRepository,
  updateDevTask,
  updateEpic,
  updateProjectContext,
  updateRepoSafetyProfile,
  updateSubtask,
  updateToolRunnerDefinition,
} from './api'
import './App.css'
import type {
  Approval,
  AssigneeType,
  AuditEvent,
  CheckDefinition,
  CheckRun,
  CheckRunConclusion,
  CheckRunStatus,
  CheckRunTargetType,
  CheckSeverity,
  CheckType,
  CodeRepository,
  CodeRepositoryProvider,
  DevTask,
  DevTaskStatus,
  Epic,
  EpicStatus,
  EpicPriority,
  Project,
  ProjectContext,
  ProviderInfo,
  Requirement,
  RequirementAnalysis,
  RepoSafetyProfile,
  RunnerType,
  Subtask,
  Ticket,
  ToolRun,
  ToolRunConclusion,
  ToolRunnerDefinition,
  ToolRunnerMode,
  ToolRunStatus,
  ToolRunTargetType,
  OpenHandsInstructionPackage,
  PullRequestDraft,
  PullRequestReview,
  PullRequestReviewConclusion,
  CIAnalysis,
  CIEvent,
  CIEventConclusion,
  CIEventProvider,
  CIEventStatus,
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

  // Governance state
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([])

  async function loadGovernance() {
    try { setApprovals(await listProjectApprovals(project.id)) } catch { /* non-critical */ }
    try { setAuditEvents(await listProjectAuditEvents(project.id)) } catch { /* non-critical */ }
  }

  // Code repositories state
  const [codeRepos, setCodeRepos] = useState<CodeRepository[]>([])

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

  // Generate requirements (agent)
  const [genBusy, setGenBusy] = useState(false)
  const [genError, setGenError] = useState('')
  const [genStatus, setGenStatus] = useState('')

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
    listProjectCodeRepositories(project.id)
      .then(setCodeRepos)
      .catch(() => { /* non-critical */ })
    loadGovernance()
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

  async function handleGenerateRequirements() {
    setGenBusy(true)
    setGenError('')
    setGenStatus('')
    try {
      const result = await createProjectRequirementGeneration(
        project.id,
        selectedProvider || undefined,
      )
      const refreshed = await listProjectRequirements(project.id)
      setRequirements(refreshed)
      setGenStatus(
        `Generated ${result.requirements.length} requirement(s) using ${result.agent_run.provider}.`,
      )
      loadGovernance()
    } catch (err) {
      setGenError((err as Error).message)
    } finally {
      setGenBusy(false)
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

        <div className="generate-requirements" style={{ margin: '12px 0' }}>
          <h4>Generate requirements from project details</h4>
          <p className="section-hint">
            The requirement generator uses the project's name, description, and context to draft requirements.
            Generated requirements are saved as drafts so you can review and edit them before analysis.
          </p>
          {providers.length > 0 && (
            <div className="provider-select">
              <label htmlFor="gen-provider">LLM provider</label>
              <select
                id="gen-provider"
                value={selectedProvider}
                onChange={e => onProviderChange(e.target.value)}
                disabled={genBusy}
              >
                {providers.map(p => (
                  <option key={p.name} value={p.name} disabled={!p.configured}>
                    {p.name} ({p.default_model}){p.configured ? '' : ' — not configured'}
                  </option>
                ))}
              </select>
            </div>
          )}
          {genError && <div className="error">{genError}</div>}
          {genStatus && <div className="ctx-saved">{genStatus}</div>}
          <button type="button" onClick={handleGenerateRequirements} disabled={genBusy}>
            {genBusy ? 'Generating…' : 'Generate requirements'}
          </button>
        </div>

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

      <hr style={{ margin: '24px 0', borderColor: '#333' }} />
      <EpicsPanel projectId={project.id} />

      <hr style={{ margin: '24px 0', borderColor: '#333' }} />
      <CodeRepositoriesPanel
        projectId={project.id}
        repos={codeRepos}
        onReposChange={setCodeRepos}
      />

      <hr style={{ margin: '24px 0', borderColor: '#333' }} />
      <ChecksPanel projectId={project.id} codeRepos={codeRepos} />

      <hr style={{ margin: '24px 0', borderColor: '#333' }} />
      <ToolRunnersPanel projectId={project.id} codeRepos={codeRepos} />

      <hr style={{ margin: '24px 0', borderColor: '#333' }} />
      <PullRequestDraftsPanel projectId={project.id} codeRepos={codeRepos} />

      <hr style={{ margin: '24px 0', borderColor: '#333' }} />
      <CIEventsPanel projectId={project.id} />

      <hr style={{ margin: '24px 0', borderColor: '#333' }} />
      <ApprovalsPanel projectId={project.id} approvals={approvals} onApprovalChange={loadGovernance} />
      <AuditEventsPanel events={auditEvents} />
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

// ---------------------------------------------------------------------------
// Code repositories panel
// ---------------------------------------------------------------------------

function RepoSafetyProfileEditor({ repoId }: { repoId: string }) {
  const [profile, setProfile] = useState<RepoSafetyProfile | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')

  // Editable fields
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

function CodeRepositoriesPanel({
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

// ---------------------------------------------------------------------------
// QA/Security bundle panel (Task 25)
// ---------------------------------------------------------------------------

const CHECK_TYPES: CheckType[] = [
  'tests', 'build', 'lint', 'typecheck', 'coverage',
  'security_sast', 'dependency_scan', 'secret_scan', 'container_scan',
  'accessibility', 'e2e', 'custom',
]
const CHECK_SEVERITIES: CheckSeverity[] = ['info', 'warning', 'blocking']
const CHECK_RUN_TARGET_TYPES: CheckRunTargetType[] = [
  'project', 'requirement', 'epic', 'dev_task', 'subtask', 'pull_request', 'manual',
]
const CHECK_RUN_STATUSES: CheckRunStatus[] = ['pending', 'running', 'completed', 'failed']
const CHECK_RUN_CONCLUSIONS: CheckRunConclusion[] = ['success', 'failure', 'neutral', 'skipped', 'cancelled']

function conclusionColor(c: CheckRunConclusion | null | undefined): string {
  if (c === 'success') return '#4caf50'
  if (c === 'failure') return '#f44336'
  if (c === 'neutral') return '#aaa'
  if (c === 'skipped') return '#888'
  if (c === 'cancelled') return '#ff9800'
  return '#666'
}

function CheckBadge({ conclusion, status }: { conclusion: CheckRunConclusion | null; status: CheckRunStatus }) {
  const label = conclusion ?? status
  return (
    <span style={{
      fontSize: 11,
      padding: '1px 6px',
      borderRadius: 10,
      background: '#222',
      color: conclusionColor(conclusion),
      border: `1px solid ${conclusionColor(conclusion)}`,
    }}>
      {label}
    </span>
  )
}

function ChecksPanel({ projectId, codeRepos }: { projectId: string; codeRepos: CodeRepository[] }) {
  const [definitions, setDefinitions] = useState<CheckDefinition[]>([])
  const [runs, setRuns] = useState<CheckRun[]>([])
  const [open, setOpen] = useState(false)
  const [genBusy, setGenBusy] = useState(false)
  const [genError, setGenError] = useState('')
  const [genMsg, setGenMsg] = useState('')

  // Create definition form
  const [defName, setDefName] = useState('')
  const [defType, setDefType] = useState<CheckType>('tests')
  const [defCommand, setDefCommand] = useState('')
  const [defSeverity, setDefSeverity] = useState<CheckSeverity>('blocking')
  const [defRequired, setDefRequired] = useState(true)
  const [defEnabled, setDefEnabled] = useState(true)
  const [defDesc, setDefDesc] = useState('')
  const [defCreating, setDefCreating] = useState(false)
  const [defError, setDefError] = useState('')

  // Record check run form
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

          {/* Check definitions */}
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

          {/* Check runs */}
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

// ---------------------------------------------------------------------------
// Tool runner panel (Task 26)
// ---------------------------------------------------------------------------

const RUNNER_TYPES: RunnerType[] = [
  'openhands', 'aider', 'cline', 'opencode', 'hermes', 'openclaw', 'manual', 'custom',
]
const RUNNER_MODES: ToolRunnerMode[] = ['local', 'api', 'manual', 'dry_run']
const TOOL_RUN_TARGET_TYPES: ToolRunTargetType[] = [
  'requirement', 'epic', 'dev_task', 'subtask', 'check_run', 'manual',
]
const TOOL_RUN_STATUSES: ToolRunStatus[] = ['pending', 'running', 'completed', 'failed', 'cancelled']
const TOOL_RUN_CONCLUSIONS: ToolRunConclusion[] = [
  'success', 'failure', 'neutral', 'skipped', 'requires_human_action',
]

function toolRunConclusionColor(c: ToolRunConclusion | null | undefined): string {
  if (c === 'success') return '#4caf50'
  if (c === 'failure') return '#f44336'
  if (c === 'neutral') return '#aaa'
  if (c === 'skipped') return '#888'
  if (c === 'requires_human_action') return '#ff9800'
  return '#666'
}

function ToolRunBadge({ conclusion, status }: { conclusion: ToolRunConclusion | null; status: ToolRunStatus }) {
  const label = conclusion ?? status
  return (
    <span style={{
      fontSize: 11,
      padding: '1px 6px',
      borderRadius: 10,
      background: '#222',
      color: toolRunConclusionColor(conclusion),
      border: `1px solid ${toolRunConclusionColor(conclusion)}`,
    }}>
      {label}
    </span>
  )
}

function ToolRunnersPanel({ projectId, codeRepos }: { projectId: string; codeRepos: CodeRepository[] }) {
  const [definitions, setDefinitions] = useState<ToolRunnerDefinition[]>([])
  const [runs, setRuns] = useState<ToolRun[]>([])
  const [open, setOpen] = useState(false)
  const [genBusy, setGenBusy] = useState(false)
  const [genError, setGenError] = useState('')
  const [genMsg, setGenMsg] = useState('')

  // Create definition form
  const [defName, setDefName] = useState('')
  const [defType, setDefType] = useState<RunnerType>('manual')
  const [defMode, setDefMode] = useState<ToolRunnerMode>('dry_run')
  const [defEnabled, setDefEnabled] = useState(true)
  const [defDesc, setDefDesc] = useState('')
  const [defCreating, setDefCreating] = useState(false)
  const [defError, setDefError] = useState('')

  // Record tool run form
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

          {/* Runner definitions */}
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

          {/* Tool runs */}
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

// ---------------------------------------------------------------------------
// PR draft workflow panel (Task 28)
// ---------------------------------------------------------------------------

function PullRequestDraftsPanel({
  projectId,
  codeRepos,
}: {
  projectId: string
  codeRepos: CodeRepository[]
}) {
  const [open, setOpen] = useState(false)
  const [drafts, setDrafts] = useState<PullRequestDraft[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    listProjectPullRequestDrafts(projectId).then(setDrafts).catch(() => {})
  }, [open, projectId])

  async function refresh() {
    try {
      setDrafts(await listProjectPullRequestDrafts(projectId))
    } catch { /* non-critical */ }
  }

  async function handleApprove(draft: PullRequestDraft) {
    setBusy(true)
    setError('')
    try {
      const updated = await approvePullRequestDraft(draft.id)
      setDrafts(prev => prev.map(d => d.id === updated.id ? updated : d))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function handleSaveUrl(draft: PullRequestDraft, url: string, num: string) {
    setBusy(true)
    setError('')
    try {
      const updated = await updatePullRequestDraft(draft.id, {
        external_pr_url: url || null,
        external_pr_number: num ? Number(num) : null,
      })
      setDrafts(prev => prev.map(d => d.id === updated.id ? updated : d))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function handleMarkCreated(draft: PullRequestDraft) {
    setBusy(true)
    setError('')
    try {
      const updated = await updatePullRequestDraft(draft.id, { status: 'created' })
      setDrafts(prev => prev.map(d => d.id === updated.id ? updated : d))
    } catch (e) {
      setError((e as Error).message)
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
        {open ? '▾' : '▸'} PR drafts ({drafts.length})
      </button>
      {open && (
        <div style={{ marginTop: 12 }}>
          <p style={{ fontSize: 12, color: '#888', margin: '0 0 8px' }}>
            ForgeLoop tracks PR drafts as metadata only — no GitHub API is called.
            Use the generated title/body when opening the PR manually. Codebase has {codeRepos.length} repo(s) registered.
          </p>
          {error && <div className="error" style={{ marginBottom: 6, fontSize: 12 }}>{error}</div>}
          {drafts.length === 0
            ? <p style={{ fontSize: 12, color: '#666' }}>No PR drafts yet. Use the "Prepare PR draft" button on a dev task.</p>
            : drafts.map(d => (
                <PullRequestDraftCard
                  key={d.id}
                  draft={d}
                  busy={busy}
                  onApprove={() => handleApprove(d)}
                  onSaveUrl={(url, num) => handleSaveUrl(d, url, num)}
                  onMarkCreated={() => handleMarkCreated(d)}
                  onRefresh={refresh}
                />
              ))
          }
        </div>
      )}
    </section>
  )
}

// ---------------------------------------------------------------------------
// CI failure ingestion and analysis (Task 30)
// ---------------------------------------------------------------------------

function ciConclusionStyle(c: CIEventConclusion | null | undefined): React.CSSProperties {
  const map: Record<string, [string, string, string]> = {
    success:    ['#155724', '#d4edda', '#c3e6cb'],
    failure:    ['#721c24', '#f8d7da', '#f5c6cb'],
    timed_out:  ['#856404', '#fff3cd', '#ffeeba'],
    cancelled:  ['#383d41', '#e2e3e5', '#d6d8db'],
    skipped:    ['#383d41', '#e2e3e5', '#d6d8db'],
    neutral:    ['#383d41', '#e2e3e5', '#d6d8db'],
    unknown:    ['#856404', '#fff3cd', '#ffeeba'],
  }
  const [color, background, border] = map[c || 'unknown'] || map.unknown
  return {
    display: 'inline-block',
    padding: '1px 6px',
    borderRadius: 4,
    fontSize: 11,
    fontWeight: 600,
    color,
    background,
    border: `1px solid ${border}`,
  }
}

function CIEventsPanel({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState(false)
  const [events, setEvents] = useState<CIEvent[]>([])
  const [analysesByEvent, setAnalysesByEvent] = useState<Record<string, CIAnalysis[]>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  // Inline create form state
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

function PullRequestDraftCard({
  draft,
  busy,
  onApprove,
  onSaveUrl,
  onMarkCreated,
  onRefresh,
}: {
  draft: PullRequestDraft
  busy: boolean
  onApprove: () => void
  onSaveUrl: (url: string, num: string) => void
  onMarkCreated: () => void
  onRefresh: () => void
}) {
  const [showBody, setShowBody] = useState(false)
  const [url, setUrl] = useState(draft.external_pr_url ?? '')
  const [num, setNum] = useState(draft.external_pr_number ? String(draft.external_pr_number) : '')

  return (
    <div style={{ border: '1px solid #333', borderRadius: 4, padding: '8px 12px', marginBottom: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <strong style={{ fontSize: 13 }}>{draft.title}</strong>
        <span className="status" style={{ fontSize: 11 }}>{draft.status}</span>
        <span className="status" style={{ fontSize: 11 }}>{draft.provider}</span>
        <span style={{ fontSize: 11, color: '#888' }}>
          {draft.source_branch} → {draft.target_branch}
        </span>
      </div>
      <div style={{ marginTop: 6 }}>
        <button
          onClick={() => setShowBody(s => !s)}
          style={{ fontSize: 11, padding: '2px 6px' }}
        >
          {showBody ? 'Hide body' : 'Show body'}
        </button>
        {draft.status === 'draft_prepared' && (
          <button onClick={onApprove} disabled={busy} style={{ fontSize: 11, marginLeft: 6 }}>
            Approve for creation
          </button>
        )}
        {draft.status === 'approved_for_creation' && (
          <button onClick={onMarkCreated} disabled={busy} style={{ fontSize: 11, marginLeft: 6 }}>
            Mark created
          </button>
        )}
        <button onClick={onRefresh} disabled={busy} style={{ fontSize: 11, marginLeft: 6 }}>
          Refresh
        </button>
      </div>
      {showBody && (
        <pre style={{
          marginTop: 6,
          maxHeight: 260,
          overflow: 'auto',
          background: '#0e0e0e',
          border: '1px solid #222',
          borderRadius: 3,
          padding: 6,
          fontSize: 11,
        }}>{draft.body}</pre>
      )}
      <div style={{ marginTop: 6, display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
        <label style={{ fontSize: 11 }}>External PR URL:
          <input
            value={url}
            onChange={e => setUrl(e.target.value)}
            placeholder="https://github.com/org/repo/pull/123"
            style={{ marginLeft: 4, fontSize: 11, padding: '2px 4px', background: '#1a1a1a', border: '1px solid #444', color: '#fff', borderRadius: 3, width: 280 }}
          />
        </label>
        <label style={{ fontSize: 11 }}>#:
          <input
            value={num}
            onChange={e => setNum(e.target.value)}
            placeholder="123"
            style={{ marginLeft: 4, fontSize: 11, padding: '2px 4px', background: '#1a1a1a', border: '1px solid #444', color: '#fff', borderRadius: 3, width: 60 }}
          />
        </label>
        <button onClick={() => onSaveUrl(url, num)} disabled={busy} style={{ fontSize: 11 }}>
          Save URL
        </button>
      </div>
      <PullRequestReviewsPanel prDraftId={draft.id} />
    </div>
  )
}

function PullRequestReviewsPanel({ prDraftId }: { prDraftId: string }) {
  const [open, setOpen] = useState(false)
  const [reviews, setReviews] = useState<PullRequestReview[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [manualOpen, setManualOpen] = useState(false)
  const [manualSummary, setManualSummary] = useState('')
  const [manualRaw, setManualRaw] = useState('')
  const [manualConclusion, setManualConclusion] = useState<PullRequestReviewConclusion>('comment_only')

  async function refresh() {
    setBusy(true)
    setError(null)
    try {
      setReviews(await listPullRequestReviews(prDraftId))
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    if (open) {
      refresh()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, prDraftId])

  async function prepare() {
    setBusy(true)
    setError(null)
    try {
      await createPullRequestReview(prDraftId, { provider: 'kody', mode: 'prepare' })
      await refresh()
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  async function recordManual() {
    setBusy(true)
    setError(null)
    try {
      await createPullRequestReview(prDraftId, {
        provider: 'kody',
        mode: 'manual',
        summary: manualSummary,
        raw_output: manualRaw,
        conclusion: manualConclusion,
      })
      setManualOpen(false)
      setManualSummary('')
      setManualRaw('')
      await refresh()
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  async function markComplete(reviewId: string, conclusion: PullRequestReviewConclusion) {
    setBusy(true)
    setError(null)
    try {
      await completePullRequestReview(reviewId, { conclusion })
      await refresh()
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{ marginTop: 8, borderTop: '1px solid #222', paddingTop: 8 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{ background: 'none', border: '1px solid #444', borderRadius: 4, padding: '2px 8px', fontSize: 11 }}
      >
        {open ? '▾' : '▸'} Kody reviews{reviews.length ? ` (${reviews.length})` : ''}
      </button>
      {open && (
        <div style={{ marginTop: 6 }}>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <button onClick={prepare} disabled={busy} style={{ fontSize: 11 }}>
              Prepare Kody review package
            </button>
            <button onClick={() => setManualOpen(o => !o)} disabled={busy} style={{ fontSize: 11 }}>
              {manualOpen ? 'Cancel manual' : 'Record manual Kody result'}
            </button>
            <button onClick={refresh} disabled={busy} style={{ fontSize: 11 }}>
              Refresh
            </button>
          </div>
          {error && <div style={{ color: '#f88', fontSize: 11, marginTop: 4 }}>{error}</div>}
          {manualOpen && (
            <div style={{ marginTop: 6, padding: 6, border: '1px solid #333', borderRadius: 3 }}>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 4 }}>
                <label style={{ fontSize: 11 }}>Conclusion:
                  <select
                    value={manualConclusion}
                    onChange={e => setManualConclusion(e.target.value as PullRequestReviewConclusion)}
                    style={{ marginLeft: 4, fontSize: 11, background: '#1a1a1a', color: '#fff', border: '1px solid #444' }}
                  >
                    <option value="approved">approved</option>
                    <option value="changes_requested">changes_requested</option>
                    <option value="comment_only">comment_only</option>
                    <option value="failed">failed</option>
                    <option value="skipped">skipped</option>
                    <option value="requires_human_review">requires_human_review</option>
                  </select>
                </label>
              </div>
              <textarea
                value={manualSummary}
                onChange={e => setManualSummary(e.target.value)}
                placeholder="Summary"
                style={{ width: '100%', minHeight: 40, fontSize: 11, background: '#1a1a1a', color: '#fff', border: '1px solid #444', borderRadius: 3, padding: 4, marginBottom: 4 }}
              />
              <textarea
                value={manualRaw}
                onChange={e => setManualRaw(e.target.value)}
                placeholder="Pasted Kody output (optional)"
                style={{ width: '100%', minHeight: 60, fontSize: 11, background: '#1a1a1a', color: '#fff', border: '1px solid #444', borderRadius: 3, padding: 4 }}
              />
              <button onClick={recordManual} disabled={busy} style={{ fontSize: 11, marginTop: 4 }}>
                Save
              </button>
            </div>
          )}
          {reviews.length === 0 ? (
            <div style={{ fontSize: 11, color: '#888', marginTop: 6 }}>No reviews yet.</div>
          ) : (
            <div style={{ marginTop: 6 }}>
              {reviews.map(r => (
                <PullRequestReviewCard
                  key={r.id}
                  review={r}
                  busy={busy}
                  onMarkComplete={c => markComplete(r.id, c)}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function PullRequestReviewCard({
  review,
  busy,
  onMarkComplete,
}: {
  review: PullRequestReview
  busy: boolean
  onMarkComplete: (c: PullRequestReviewConclusion) => void
}) {
  const [conclusion, setConclusion] = useState<PullRequestReviewConclusion>('approved')
  return (
    <div style={{ border: '1px solid #2a2a2a', borderRadius: 3, padding: 6, marginBottom: 6 }}>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
        <span className="status" style={{ fontSize: 10 }}>{review.provider}</span>
        <span className="status" style={{ fontSize: 10 }}>{review.status}</span>
        {review.conclusion && (
          <span className="status" style={{ fontSize: 10 }}>{review.conclusion}</span>
        )}
        <span style={{ fontSize: 10, color: '#888' }}>{new Date(review.created_at).toLocaleString()}</span>
      </div>
      {review.summary && (
        <div style={{ fontSize: 11, marginTop: 4 }}>{review.summary}</div>
      )}
      {review.findings.length > 0 && (
        <ul style={{ fontSize: 11, marginTop: 4, paddingLeft: 16 }}>
          {review.findings.map((f, i) => (
            <li key={i}>
              {f.severity ? `[${f.severity}] ` : ''}
              {f.category ? `(${f.category}) ` : ''}
              {f.message}
              {f.file_path ? ` — ${f.file_path}${f.line ? `:${f.line}` : ''}` : ''}
            </li>
          ))}
        </ul>
      )}
      {review.external_review_url && (
        <div style={{ fontSize: 11, marginTop: 4 }}>
          <a href={review.external_review_url} target="_blank" rel="noreferrer">External review</a>
        </div>
      )}
      {review.status !== 'completed' && review.status !== 'cancelled' && (
        <div style={{ marginTop: 4, display: 'flex', gap: 6, alignItems: 'center' }}>
          <select
            value={conclusion}
            onChange={e => setConclusion(e.target.value as PullRequestReviewConclusion)}
            style={{ fontSize: 11, background: '#1a1a1a', color: '#fff', border: '1px solid #444' }}
          >
            <option value="approved">approved</option>
            <option value="changes_requested">changes_requested</option>
            <option value="comment_only">comment_only</option>
            <option value="failed">failed</option>
            <option value="skipped">skipped</option>
            <option value="requires_human_review">requires_human_review</option>
          </select>
          <button onClick={() => onMarkComplete(conclusion)} disabled={busy} style={{ fontSize: 11 }}>
            Mark complete
          </button>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Governance panels — approvals + audit events
// ---------------------------------------------------------------------------

function ApprovalsPanel({
  projectId,
  approvals,
  onApprovalChange,
}: {
  projectId: string
  approvals: Approval[]
  onApprovalChange: () => void
}) {
  const [open, setOpen] = useState(false)
  const pending = approvals.filter(a => a.status === 'pending')

  return (
    <div style={{ marginTop: 16 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{ background: 'none', border: '1px solid #444', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: 13 }}
      >
        {open ? '▾' : '▸'} Approvals ({approvals.length}, {pending.length} pending)
      </button>
      {open && (
        <div style={{ marginTop: 8 }}>
          {approvals.length === 0 && <p style={{ fontSize: 13, color: '#888' }}>No approvals yet.</p>}
          {approvals.map(a => (
            <ApprovalRow key={a.id} approval={a} projectId={projectId} onChange={onApprovalChange} />
          ))}
        </div>
      )}
    </div>
  )
}

function ApprovalRow({
  approval,
  projectId: _projectId,
  onChange,
}: {
  approval: Approval
  projectId: string
  onChange: () => void
}) {
  const [feedback, setFeedback] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const isFinal = approval.status !== 'pending'

  async function decide(status: 'approved' | 'rejected' | 'needs_revision') {
    setBusy(true)
    setError(null)
    try {
      await decideApproval(approval.id, { status, feedback: feedback || null })
      onChange()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{ border: '1px solid #333', borderRadius: 4, padding: '8px 12px', marginBottom: 8, fontSize: 13 }}>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ color: '#aaa' }}>{approval.target_type}</span>
        <code style={{ fontSize: 11, color: '#888' }}>{approval.target_id.slice(0, 12)}…</code>
        <span className={`status${approval.status === 'approved' ? ' done' : ''}`}>{approval.status}</span>
        {approval.feedback && <span style={{ color: '#aaa' }}>{approval.feedback}</span>}
      </div>
      {!isFinal && (
        <div style={{ marginTop: 6, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            placeholder="Feedback (optional)"
            value={feedback}
            onChange={e => setFeedback(e.target.value)}
            style={{ fontSize: 12, padding: '2px 6px', background: '#1a1a1a', border: '1px solid #444', color: '#fff', borderRadius: 3 }}
          />
          <button onClick={() => decide('approved')} disabled={busy} style={{ fontSize: 12 }}>Approve</button>
          <button onClick={() => decide('rejected')} disabled={busy} style={{ fontSize: 12 }}>Reject</button>
          <button onClick={() => decide('needs_revision')} disabled={busy} style={{ fontSize: 12 }}>Needs revision</button>
        </div>
      )}
      {error && <div className="error" style={{ marginTop: 4 }}>{error}</div>}
    </div>
  )
}

function AuditEventsPanel({ events }: { events: AuditEvent[] }) {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ marginTop: 8 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{ background: 'none', border: '1px solid #444', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: 13 }}
      >
        {open ? '▾' : '▸'} Audit log ({events.length})
      </button>
      {open && (
        <div style={{ marginTop: 8 }}>
          {events.length === 0 && <p style={{ fontSize: 13, color: '#888' }}>No events yet.</p>}
          {events.map(e => (
            <div key={e.id} style={{ fontSize: 12, color: '#aaa', marginBottom: 4 }}>
              <span style={{ color: '#888', marginRight: 6 }}>{e.created_at.slice(0, 19).replace('T', ' ')}</span>
              <span style={{ color: '#fff', marginRight: 6 }}>{e.action}</span>
              <span style={{ marginRight: 6 }}>{e.target_type}</span>
              <code style={{ fontSize: 11 }}>{e.target_id.slice(0, 12)}…</code>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// DevTask panel
// ---------------------------------------------------------------------------

const ALL_STATUSES: DevTaskStatus[] = ['proposed', 'ready', 'in_progress', 'blocked', 'completed']

// ---------------------------------------------------------------------------
// Epics panel
// ---------------------------------------------------------------------------

const EPIC_STATUSES: EpicStatus[] = ['proposed', 'ready', 'in_progress', 'blocked', 'completed']
const EPIC_PRIORITIES: EpicPriority[] = ['low', 'medium', 'high']
const ASSIGNEE_TYPES: AssigneeType[] = ['unassigned', 'human', 'agent']

function EpicsPanel({ projectId }: { projectId: string }) {
  const [epics, setEpics] = useState<Epic[]>([])
  const [selected, setSelected] = useState<Epic | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState<EpicPriority>('medium')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')

  useEffect(() => {
    listProjectEpics(projectId)
      .then(setEpics)
      .catch(err => setError((err as Error).message))
  }, [projectId])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setCreateError('')
    setCreating(true)
    try {
      const epic = await createProjectEpic(projectId, { title: title.trim(), description: description.trim(), priority })
      setEpics(prev => [...prev, epic])
      setTitle('')
      setDescription('')
      setPriority('medium')
    } catch (err) {
      setCreateError((err as Error).message)
    } finally {
      setCreating(false)
    }
  }

  async function handleEpicPatch(epicId: string, patch: Partial<{ status: EpicStatus; priority: EpicPriority; assignee_type: AssigneeType; assignee_name: string }>) {
    setBusy(true)
    try {
      const updated = await updateEpic(epicId, patch)
      setEpics(prev => prev.map(e => e.id === updated.id ? updated : e))
      setSelected(updated)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section style={{ marginTop: 24 }}>
      <h3>Epics</h3>
      {error && <div className="error">{error}</div>}

      {epics.length > 0 && (
        <div className="ticket-list" style={{ marginBottom: 12 }}>
          {epics.map(e => (
            <button
              key={e.id}
              className={`ticket-row ${e.status === 'completed' ? 'done' : ''}`}
              onClick={() => setSelected(selected?.id === e.id ? null : e)}
            >
              <span className="ticket-row-title">{e.title}</span>
              <span className="ticket-row-status">{e.status} · {e.priority}</span>
            </button>
          ))}
        </div>
      )}

      {selected && (
        <div style={{ border: '1px solid #444', borderRadius: 6, padding: '10px 14px', marginBottom: 12 }}>
          <strong>{selected.title}</strong>
          {selected.requirement_id && (
            <p style={{ fontSize: 12, color: '#aaa', margin: '4px 0' }}>Requirement: {selected.requirement_id}</p>
          )}
          {selected.business_goal && <p style={{ fontSize: 13, margin: '4px 0' }}>{selected.business_goal}</p>}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 6 }}>
            <label style={{ fontSize: 12 }}>Status:
              <select value={selected.status} onChange={e => handleEpicPatch(selected.id, { status: e.target.value as EpicStatus })} disabled={busy} style={{ marginLeft: 4, fontSize: 12 }}>
                {EPIC_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
            <label style={{ fontSize: 12 }}>Priority:
              <select value={selected.priority} onChange={e => handleEpicPatch(selected.id, { priority: e.target.value as EpicPriority })} disabled={busy} style={{ marginLeft: 4, fontSize: 12 }}>
                {EPIC_PRIORITIES.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </label>
            <label style={{ fontSize: 12 }}>Assignee:
              <select value={selected.assignee_type} onChange={e => handleEpicPatch(selected.id, { assignee_type: e.target.value as AssigneeType })} disabled={busy} style={{ marginLeft: 4, fontSize: 12 }}>
                {ASSIGNEE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </label>
            {selected.assignee_type !== 'unassigned' && (
              <label style={{ fontSize: 12 }}>Name:
                <input
                  defaultValue={selected.assignee_name ?? ''}
                  onBlur={e => { if (e.target.value !== (selected.assignee_name ?? '')) handleEpicPatch(selected.id, { assignee_name: e.target.value }) }}
                  disabled={busy}
                  style={{ marginLeft: 4, fontSize: 12, padding: '2px 4px', background: '#1a1a1a', border: '1px solid #444', color: '#fff', borderRadius: 3, width: 120 }}
                />
              </label>
            )}
          </div>
        </div>
      )}

      <h4>New epic</h4>
      <form onSubmit={handleCreate}>
        <label htmlFor="epic-title">Title</label>
        <input id="epic-title" value={title} onChange={e => setTitle(e.target.value)} required disabled={creating} placeholder="Epic name" />
        <label htmlFor="epic-desc">Description</label>
        <textarea id="epic-desc" value={description} onChange={e => setDescription(e.target.value)} disabled={creating} placeholder="Optional description" />
        <label htmlFor="epic-priority">Priority</label>
        <select id="epic-priority" value={priority} onChange={e => setPriority(e.target.value as EpicPriority)} disabled={creating}>
          {EPIC_PRIORITIES.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
        {createError && <div className="error">{createError}</div>}
        <button type="submit" disabled={creating}>{creating ? 'Creating…' : 'Create epic'}</button>
      </form>
    </section>
  )
}

function SubtaskList({
  subtasks,
  onSubtaskUpdate,
}: {
  subtasks: Subtask[]
  onSubtaskUpdate: (updated: Subtask) => void
}) {
  if (subtasks.length === 0) return null
  return (
    <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
      {subtasks.map(st => (
        <SubtaskRow key={st.id} subtask={st} onUpdate={onSubtaskUpdate} />
      ))}
    </ul>
  )
}

function SubtaskRow({ subtask, onUpdate }: { subtask: Subtask; onUpdate: (s: Subtask) => void }) {
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleStatusChange(next: string) {
    setError(null)
    setBusy(true)
    try {
      const updated = await updateSubtask(subtask.id, { status: next as DevTaskStatus })
      onUpdate(updated)
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
      const updated = await updateSubtask(subtask.id, { assignee_type: next })
      onUpdate(updated)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function handleAssigneeNameBlur(name: string) {
    if (name === (subtask.assignee_name ?? '')) return
    setBusy(true)
    try {
      const updated = await updateSubtask(subtask.id, { assignee_name: name || null })
      onUpdate(updated)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <li style={{ marginBottom: 6 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 13 }}>{subtask.title}</span>
        <select
          value={subtask.status}
          onChange={e => handleStatusChange(e.target.value)}
          disabled={busy}
          style={{ fontSize: 11 }}
        >
          {ALL_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        {subtask.qa_required && (
          <span className="status done" style={{ fontSize: 11 }}>QA</span>
        )}
        <select
          value={subtask.assignee_type}
          onChange={e => handleAssigneeTypeChange(e.target.value as AssigneeType)}
          disabled={busy}
          style={{ fontSize: 11 }}
        >
          {ASSIGNEE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        {subtask.assignee_type !== 'unassigned' && (
          <input
            defaultValue={subtask.assignee_name ?? ''}
            onBlur={e => handleAssigneeNameBlur(e.target.value)}
            placeholder="name"
            disabled={busy}
            style={{ fontSize: 11, padding: '1px 4px', background: '#1a1a1a', border: '1px solid #444', color: '#fff', borderRadius: 3, width: 90 }}
          />
        )}
      </div>
      {error && <div className="error" style={{ fontSize: 11, marginTop: 2 }}>{error}</div>}
    </li>
  )
}

function DevTaskCard({
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

  // Check runs disclosure
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

  // Tool runs disclosure
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

  // OpenHands package
  const [ohBusy, setOhBusy] = useState(false)
  const [ohError, setOhError] = useState<string | null>(null)
  const [ohPackage, setOhPackage] = useState<OpenHandsInstructionPackage | null>(null)
  const [ohRun, setOhRun] = useState<ToolRun | null>(null)
  const [ohResultText, setOhResultText] = useState('')
  const [ohResultConclusion, setOhResultConclusion] = useState<ToolRunConclusion>('success')
  const [ohRecording, setOhRecording] = useState(false)

  // PR draft
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
      // Refresh tool runs list if currently open
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

      {/* Epic + assignment */}
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

      {/* Approval controls */}
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
      {/* Check runs disclosure */}
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
      {/* Tool runs disclosure */}
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

      {/* OpenHands package (Task 27 — dry-run only) */}
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
              Dry-run package — ForgeLoop does not execute OpenHands. Copy to OpenHands manually.
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

      {/* PR draft (Task 28 — metadata-only) */}
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

type DecompPhase =
  | { name: 'idle' }
  | { name: 'decomposing' }
  | { name: 'done' }
  | { name: 'error'; message: string }

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
  const [decompPhase, setDecompPhase] = useState<DecompPhase>({ name: 'idle' })
  const [devTasks, setDevTasks] = useState<DevTask[]>([])
  const [subtasks, setSubtasks] = useState<Subtask[]>([])
  const [approvals, setApprovals] = useState<Approval[]>([])
  const busy = phase.name === 'analyzing' || decompPhase.name === 'decomposing'

  async function loadApprovals() {
    try {
      const list = await listProjectApprovals(project.id)
      setApprovals(list)
    } catch {
      // non-critical
    }
  }

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

  async function handleDecompose() {
    setDecompPhase({ name: 'decomposing' })
    try {
      const result = await createTaskDecomposition(requirement.id, selectedProvider || undefined)
      setDevTasks(result.dev_tasks)
      setSubtasks(result.subtasks)
      setDecompPhase({ name: 'done' })
      await loadApprovals()
    } catch (err) {
      setDecompPhase({ name: 'error', message: (err as Error).message })
    }
  }

  function handleTaskUpdate(updated: DevTask) {
    setDevTasks(prev => prev.map(t => t.id === updated.id ? updated : t))
  }

  function handleSubtaskUpdate(updated: Subtask) {
    setSubtasks(prev => prev.map(s => s.id === updated.id ? updated : s))
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

      {providers.length > 0 && (
        <div className="provider-select">
          <label htmlFor="req-provider">LLM provider</label>
          <select
            id="req-provider"
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

      {phase.name === 'error' && <div className="error">{phase.message}</div>}
      {phase.name !== 'done' && (
        <button onClick={handleAnalyze} disabled={busy} style={{ marginRight: 8 }}>
          {phase.name === 'analyzing' ? 'Analyzing…' : 'Analyze requirement'}
        </button>
      )}
      {phase.name === 'done' && (
        <>
          <h3>Requirement Analysis</h3>
          <RequirementAnalysisPanel analysis={phase.analysis} />
        </>
      )}

      <hr style={{ margin: '18px 0', borderColor: '#333' }} />
      <h3>Dev Task Decomposition</h3>
      {decompPhase.name === 'error' && <div className="error">{decompPhase.message}</div>}
      {decompPhase.name !== 'done' && (
        <button onClick={handleDecompose} disabled={busy}>
          {decompPhase.name === 'decomposing' ? 'Decomposing…' : 'Decompose into dev tasks'}
        </button>
      )}
      {decompPhase.name === 'done' && (
        <>
          <p style={{ fontSize: 13, color: '#aaa' }}>
            {devTasks.length} task(s) generated
          </p>
          {devTasks.map(task => (
            <DevTaskCard
              key={task.id}
              task={task}
              allSubtasks={subtasks}
              taskApproval={approvals.find(a => a.target_type === 'dev_task' && a.target_id === task.id)}
              projectId={project.id}
              onTaskUpdate={handleTaskUpdate}
              onSubtaskUpdate={handleSubtaskUpdate}
              onApprovalChange={loadApprovals}
            />
          ))}
          <button onClick={handleDecompose} disabled={busy} style={{ marginTop: 8 }}>
            Re-run decomposition
          </button>
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
