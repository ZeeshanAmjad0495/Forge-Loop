import { clearToken, getToken } from './auth'
import type {
  Approval,
  ApprovalCreate,
  ApprovalDecision,
  AuditEvent,
  DevTask,
  DevTaskUpdate,
  LoginResponse,
  PlanningRunResponse,
  Project,
  ProjectContext,
  ProjectCreate,
  ProvidersResponse,
  Requirement,
  RequirementAnalysis,
  RequirementAnalysisRunResponse,
  RequirementCreate,
  RequirementUpdate,
  Subtask,
  SubtaskUpdate,
  TaskDecompositionResponse,
  Ticket,
} from './types'

const BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8080'

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.status === 401) {
    clearToken()
    throw new Error('401: Unauthorized')
  }
  if (res.ok) return res.json() as Promise<T>
  let message = res.statusText
  try {
    const body = await res.json()
    if (typeof body.detail === 'string') message = body.detail
  } catch {
    // keep statusText
  }
  throw new Error(`${res.status}: ${message}`)
}

function authHeaders(): Record<string, string> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const res = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  return handleResponse<LoginResponse>(res)
}

// ---------------------------------------------------------------------------
// Projects
// ---------------------------------------------------------------------------

export async function listProjects(): Promise<Project[]> {
  const res = await fetch(`${BASE}/projects`, { headers: authHeaders() })
  return handleResponse<Project[]>(res)
}

export async function createProject(data: ProjectCreate): Promise<Project> {
  const res = await fetch(`${BASE}/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(data),
  })
  return handleResponse<Project>(res)
}

export async function getProjectContext(projectId: string): Promise<ProjectContext> {
  const res = await fetch(`${BASE}/projects/${projectId}/context`, { headers: authHeaders() })
  return handleResponse<ProjectContext>(res)
}

export async function updateProjectContext(
  projectId: string,
  ctx: Omit<ProjectContext, 'project_id' | 'updated_at'>,
): Promise<ProjectContext> {
  const res = await fetch(`${BASE}/projects/${projectId}/context`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(ctx),
  })
  return handleResponse<ProjectContext>(res)
}

export async function createProjectTicket(
  projectId: string,
  title: string,
  description: string,
): Promise<Ticket> {
  const res = await fetch(`${BASE}/projects/${projectId}/tickets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ title, description }),
  })
  return handleResponse<Ticket>(res)
}

export async function listProjectTickets(projectId: string): Promise<Ticket[]> {
  const res = await fetch(`${BASE}/projects/${projectId}/tickets`, { headers: authHeaders() })
  return handleResponse<Ticket[]>(res)
}

// ---------------------------------------------------------------------------
// Tickets (legacy standalone flow)
// ---------------------------------------------------------------------------

export async function createTicket(title: string, description: string): Promise<Ticket> {
  const res = await fetch(`${BASE}/tickets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ title, description }),
  })
  return handleResponse<Ticket>(res)
}

export async function createPlanningRun(
  ticketId: string,
  provider?: string,
): Promise<PlanningRunResponse> {
  const init: RequestInit = {
    method: 'POST',
    headers: { ...authHeaders() },
  }
  if (provider) {
    init.headers = { 'Content-Type': 'application/json', ...authHeaders() }
    init.body = JSON.stringify({ provider })
  }
  const res = await fetch(`${BASE}/tickets/${ticketId}/planning-runs`, init)
  return handleResponse<PlanningRunResponse>(res)
}

export async function createRequirementAnalysis(
  ticketId: string,
  provider?: string,
): Promise<RequirementAnalysisRunResponse> {
  const init: RequestInit = {
    method: 'POST',
    headers: { ...authHeaders() },
  }
  if (provider) {
    init.headers = { 'Content-Type': 'application/json', ...authHeaders() }
    init.body = JSON.stringify({ provider })
  }
  const res = await fetch(`${BASE}/tickets/${ticketId}/requirement-analyses`, init)
  return handleResponse<RequirementAnalysisRunResponse>(res)
}

export async function listRequirementAnalyses(ticketId: string): Promise<RequirementAnalysis[]> {
  const res = await fetch(`${BASE}/tickets/${ticketId}/requirement-analyses`, {
    headers: authHeaders(),
  })
  return handleResponse<RequirementAnalysis[]>(res)
}

export async function listProviders(): Promise<ProvidersResponse> {
  const res = await fetch(`${BASE}/llm/providers`, { headers: authHeaders() })
  return handleResponse<ProvidersResponse>(res)
}

// ---------------------------------------------------------------------------
// Structured requirements
// ---------------------------------------------------------------------------

export async function listProjectRequirements(projectId: string): Promise<Requirement[]> {
  const res = await fetch(`${BASE}/projects/${projectId}/requirements`, {
    headers: authHeaders(),
  })
  return handleResponse<Requirement[]>(res)
}

export async function createProjectRequirement(
  projectId: string,
  data: RequirementCreate,
): Promise<Requirement> {
  const res = await fetch(`${BASE}/projects/${projectId}/requirements`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(data),
  })
  return handleResponse<Requirement>(res)
}

export async function getRequirement(requirementId: string): Promise<Requirement> {
  const res = await fetch(`${BASE}/requirements/${requirementId}`, { headers: authHeaders() })
  return handleResponse<Requirement>(res)
}

export async function updateRequirement(
  requirementId: string,
  data: RequirementUpdate,
): Promise<Requirement> {
  const res = await fetch(`${BASE}/requirements/${requirementId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(data),
  })
  return handleResponse<Requirement>(res)
}

export async function createRequirementAnalysisForRequirement(
  requirementId: string,
  provider?: string,
): Promise<RequirementAnalysisRunResponse> {
  const init: RequestInit = {
    method: 'POST',
    headers: { ...authHeaders() },
  }
  if (provider) {
    init.headers = { 'Content-Type': 'application/json', ...authHeaders() }
    init.body = JSON.stringify({ provider })
  }
  const res = await fetch(`${BASE}/requirements/${requirementId}/requirement-analyses`, init)
  return handleResponse<RequirementAnalysisRunResponse>(res)
}

// ---------------------------------------------------------------------------
// Task decomposition
// ---------------------------------------------------------------------------

export async function createTaskDecomposition(
  requirementId: string,
  provider?: string,
): Promise<TaskDecompositionResponse> {
  const init: RequestInit = {
    method: 'POST',
    headers: { ...authHeaders() },
  }
  if (provider) {
    init.headers = { 'Content-Type': 'application/json', ...authHeaders() }
    init.body = JSON.stringify({ provider })
  }
  const res = await fetch(`${BASE}/requirements/${requirementId}/task-decompositions`, init)
  return handleResponse<TaskDecompositionResponse>(res)
}

export async function listProjectDevTasks(projectId: string): Promise<DevTask[]> {
  const res = await fetch(`${BASE}/projects/${projectId}/dev-tasks`, { headers: authHeaders() })
  return handleResponse<DevTask[]>(res)
}

export async function getDevTask(devTaskId: string): Promise<{ dev_task: DevTask; subtasks: Subtask[] }> {
  const res = await fetch(`${BASE}/dev-tasks/${devTaskId}`, { headers: authHeaders() })
  return handleResponse<{ dev_task: DevTask; subtasks: Subtask[] }>(res)
}

export async function listDevTaskSubtasks(devTaskId: string): Promise<Subtask[]> {
  const res = await fetch(`${BASE}/dev-tasks/${devTaskId}/subtasks`, { headers: authHeaders() })
  return handleResponse<Subtask[]>(res)
}

export async function updateDevTask(devTaskId: string, patch: DevTaskUpdate): Promise<DevTask> {
  const res = await fetch(`${BASE}/dev-tasks/${devTaskId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(patch),
  })
  return handleResponse<DevTask>(res)
}

export async function updateSubtask(subtaskId: string, patch: SubtaskUpdate): Promise<Subtask> {
  const res = await fetch(`${BASE}/subtasks/${subtaskId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(patch),
  })
  return handleResponse<Subtask>(res)
}

// ---------------------------------------------------------------------------
// Approvals
// ---------------------------------------------------------------------------

export async function createApproval(data: ApprovalCreate): Promise<Approval> {
  const res = await fetch(`${BASE}/approvals`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(data),
  })
  return handleResponse<Approval>(res)
}

export async function listProjectApprovals(projectId: string): Promise<Approval[]> {
  const res = await fetch(`${BASE}/projects/${projectId}/approvals`, { headers: authHeaders() })
  return handleResponse<Approval[]>(res)
}

export async function getApproval(approvalId: string): Promise<Approval> {
  const res = await fetch(`${BASE}/approvals/${approvalId}`, { headers: authHeaders() })
  return handleResponse<Approval>(res)
}

export async function decideApproval(approvalId: string, decision: ApprovalDecision): Promise<Approval> {
  const res = await fetch(`${BASE}/approvals/${approvalId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(decision),
  })
  return handleResponse<Approval>(res)
}

// ---------------------------------------------------------------------------
// Audit events
// ---------------------------------------------------------------------------

export async function listProjectAuditEvents(projectId: string): Promise<AuditEvent[]> {
  const res = await fetch(`${BASE}/projects/${projectId}/audit-events`, { headers: authHeaders() })
  return handleResponse<AuditEvent[]>(res)
}

export async function getAuditEvent(auditEventId: string): Promise<AuditEvent> {
  const res = await fetch(`${BASE}/audit-events/${auditEventId}`, { headers: authHeaders() })
  return handleResponse<AuditEvent>(res)
}
