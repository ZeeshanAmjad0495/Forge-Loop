import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { clearToken, getToken, setToken } from './auth'
import {
  createPlanningRun,
  createProject,
  createProjectTicket,
  getProjectContext,
  listProjectTickets,
  listProjects,
  listProviders,
  login,
  updateProjectContext,
} from './api'
import './App.css'
import type { Project, ProjectContext, ProviderInfo, Ticket } from './types'

// ---------------------------------------------------------------------------
// View state — discriminated union, no router
// ---------------------------------------------------------------------------

type View =
  | { view: 'projects' }
  | { view: 'project'; project: Project }
  | { view: 'ticket'; project: Project; ticket: Ticket }

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
  providers,
  selectedProvider,
  onProviderChange,
}: {
  project: Project
  onBack: () => void
  onSelectTicket: (ticket: Ticket) => void
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

  useEffect(() => {
    getProjectContext(project.id)
      .then(setCtx)
      .catch(err => setCtxError((err as Error).message))
    listProjectTickets(project.id)
      .then(setTickets)
      .catch(err => setTicketError((err as Error).message))
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
    </div>
  )
}

// ---------------------------------------------------------------------------
// Ticket view — generate brief + display
// ---------------------------------------------------------------------------

type BriefPhase =
  | { name: 'idle' }
  | { name: 'generating' }
  | { name: 'done'; brief: string }
  | { name: 'error'; message: string }

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
  const [briefPhase, setBriefPhase] = useState<BriefPhase>({ name: 'idle' })

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

  const generating = briefPhase.name === 'generating'

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
            disabled={generating}
          >
            {providers.map(p => (
              <option key={p.name} value={p.name} disabled={!p.configured}>
                {p.name} ({p.default_model}){p.configured ? '' : ' — not configured'}
              </option>
            ))}
          </select>
        </div>
      )}

      {briefPhase.name === 'error' && (
        <div className="error">{briefPhase.message}</div>
      )}

      {briefPhase.name !== 'done' && (
        <button onClick={handleGenerateBrief} disabled={generating}>
          {generating ? 'Generating brief…' : 'Generate planning brief'}
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
    </>
  )
}
