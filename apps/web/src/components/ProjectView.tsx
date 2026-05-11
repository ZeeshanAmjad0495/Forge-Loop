import { useEffect, useState } from 'react'
import {
  createProjectTicket,
  listProjectApprovals,
  listProjectAuditEvents,
  listProjectCodeRepositories,
  listProjectTickets,
  listProjectWorkspaces,
} from '../api'
import type {
  Approval,
  AuditEvent,
  CodeRepository,
  Project,
  ProviderInfo,
  Requirement,
  Ticket,
  Workspace,
} from '../types'
import { ProjectContextPanel } from './panels/ProjectContextPanel'
import { RequirementsPanel } from './panels/RequirementsPanel'
import { EpicsPanel } from './panels/TasksPanel'
import { CodeRepositoriesPanel } from './panels/CodeRepositoriesPanel'
import { WorkspacesPanel } from './panels/WorkspacesPanel'
import { CommandRunnerPanel } from './panels/CommandRunnerPanel'
import { ChecksPanel } from './panels/CheckRunsPanel'
import { ToolRunnersPanel } from './panels/ToolRunnersPanel'
import { PullRequestDraftsPanel } from './panels/PrDraftsPanel'
import { CIEventsPanel } from './panels/CiEventsPanel'
import { IncidentsPanel } from './panels/IncidentsPanel'
import { MemoryCandidatesPanel } from './panels/MemoryCandidatesPanel'
import { ApprovalsPanel } from './panels/ApprovalsPanel'
import { AuditEventsPanel } from './panels/AuditEventsPanel'

export function ProjectView({
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
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [ticketError, setTicketError] = useState('')

  const [ticketTitle, setTicketTitle] = useState('')
  const [ticketDesc, setTicketDesc] = useState('')
  const [ticketCreating, setTicketCreating] = useState(false)
  const [ticketCreateError, setTicketCreateError] = useState('')

  const [approvals, setApprovals] = useState<Approval[]>([])
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([])

  async function loadGovernance() {
    try { setApprovals(await listProjectApprovals(project.id)) } catch { /* non-critical */ }
    try { setAuditEvents(await listProjectAuditEvents(project.id)) } catch { /* non-critical */ }
  }

  const [codeRepos, setCodeRepos] = useState<CodeRepository[]>([])
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])

  useEffect(() => {
    listProjectTickets(project.id)
      .then(setTickets)
      .catch(err => setTicketError((err as Error).message))
    listProjectCodeRepositories(project.id)
      .then(setCodeRepos)
      .catch(() => { /* non-critical */ })
    listProjectWorkspaces(project.id)
      .then(setWorkspaces)
      .catch(() => { /* non-critical */ })
    loadGovernance()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id])

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

      <ProjectContextPanel projectId={project.id} />

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

      <RequirementsPanel
        projectId={project.id}
        providers={providers}
        selectedProvider={selectedProvider}
        onProviderChange={onProviderChange}
        onSelectRequirement={onSelectRequirement}
        onAfterGenerate={loadGovernance}
      />

      <hr style={{ margin: '24px 0', borderColor: '#333' }} />
      <EpicsPanel projectId={project.id} />

      <hr style={{ margin: '24px 0', borderColor: '#333' }} />
      <CodeRepositoriesPanel
        projectId={project.id}
        repos={codeRepos}
        onReposChange={setCodeRepos}
      />

      <hr style={{ margin: '24px 0', borderColor: '#333' }} />
      <WorkspacesPanel projectId={project.id} codeRepos={codeRepos} />

      <hr style={{ margin: '24px 0', borderColor: '#333' }} />
      <CommandRunnerPanel projectId={project.id} workspaces={workspaces} />

      <hr style={{ margin: '24px 0', borderColor: '#333' }} />
      <ChecksPanel projectId={project.id} codeRepos={codeRepos} />

      <hr style={{ margin: '24px 0', borderColor: '#333' }} />
      <ToolRunnersPanel projectId={project.id} codeRepos={codeRepos} />

      <hr style={{ margin: '24px 0', borderColor: '#333' }} />
      <PullRequestDraftsPanel projectId={project.id} codeRepos={codeRepos} />

      <hr style={{ margin: '24px 0', borderColor: '#333' }} />
      <CIEventsPanel projectId={project.id} />
      <IncidentsPanel projectId={project.id} />
      <MemoryCandidatesPanel projectId={project.id} />

      <hr style={{ margin: '24px 0', borderColor: '#333' }} />
      <ApprovalsPanel projectId={project.id} approvals={approvals} onApprovalChange={loadGovernance} />
      <AuditEventsPanel events={auditEvents} />
    </div>
  )
}
