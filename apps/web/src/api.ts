import { clearToken, getToken } from './auth'
import type {
  Approval,
  ApprovalCreate,
  ApprovalDecision,
  AuditEvent,
  CheckDefinition,
  CheckDefinitionCreate,
  CheckDefinitionUpdate,
  CheckDefinitionsFromSafetyProfileResponse,
  CheckRun,
  CheckRunCreate,
  CodeRepository,
  CodeRepositoryCreate,
  CodeRepositoryUpdate,
  DevTask,
  DevTaskUpdate,
  Epic,
  EpicCreate,
  EpicUpdate,
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
  RequirementGenerationResponse,
  RequirementUpdate,
  RepoSafetyProfile,
  RepoSafetyProfileUpsert,
  Subtask,
  SubtaskUpdate,
  TaskDecompositionResponse,
  Ticket,
  ToolRun,
  ToolRunCreate,
  ToolRunnerDefinition,
  ToolRunnerDefinitionCreate,
  ToolRunnerDefinitionUpdate,
  ToolRunnerDefinitionsDefaultsResponse,
  OpenHandsPreparePackageRequest,
  OpenHandsPrepareResponse,
  OpenHandsRecordResultRequest,
  PullRequestDraft,
  PullRequestDraftCreate,
  PullRequestDraftUpdate,
  PullRequestReview,
  PullRequestReviewComplete,
  PullRequestReviewCreate,
  PullRequestReviewUpdate,
  CIAnalysis,
  CIAnalysisCreate,
  CIEvent,
  CIEventCreate,
  Incident,
  IncidentAnalysis,
  IncidentAnalysisCreate,
  IncidentCreate,
  IncidentUpdate,
  MemoryCandidateRejectRequest,
  MemoryLearningRun,
  MemoryLearningRunCreate,
  ProjectMemoryCandidate,
  ProjectMemoryCandidateCreate,
  ProjectMemoryCandidateUpdate,
  RemediationWorkItemDraft,
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

export async function createProjectRequirementGeneration(
  projectId: string,
  provider?: string,
): Promise<RequirementGenerationResponse> {
  const init: RequestInit = {
    method: 'POST',
    headers: { ...authHeaders() },
  }
  if (provider) {
    init.headers = { 'Content-Type': 'application/json', ...authHeaders() }
    init.body = JSON.stringify({ provider })
  }
  const res = await fetch(`${BASE}/projects/${projectId}/requirement-generations`, init)
  return handleResponse<RequirementGenerationResponse>(res)
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

// ---------------------------------------------------------------------------
// Code repositories
// ---------------------------------------------------------------------------

export async function listProjectCodeRepositories(projectId: string): Promise<CodeRepository[]> {
  const res = await fetch(`${BASE}/projects/${projectId}/code-repositories`, { headers: authHeaders() })
  return handleResponse<CodeRepository[]>(res)
}

export async function createCodeRepository(projectId: string, body: CodeRepositoryCreate): Promise<CodeRepository> {
  const res = await fetch(`${BASE}/projects/${projectId}/code-repositories`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<CodeRepository>(res)
}

export async function getCodeRepository(repoId: string): Promise<CodeRepository> {
  const res = await fetch(`${BASE}/code-repositories/${repoId}`, { headers: authHeaders() })
  return handleResponse<CodeRepository>(res)
}

export async function updateCodeRepository(repoId: string, body: CodeRepositoryUpdate): Promise<CodeRepository> {
  const res = await fetch(`${BASE}/code-repositories/${repoId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<CodeRepository>(res)
}

// ---------------------------------------------------------------------------
// Repo safety profiles
// ---------------------------------------------------------------------------

export async function getRepoSafetyProfile(repoId: string): Promise<RepoSafetyProfile> {
  const res = await fetch(`${BASE}/code-repositories/${repoId}/safety-profile`, { headers: authHeaders() })
  return handleResponse<RepoSafetyProfile>(res)
}

export async function upsertRepoSafetyProfile(repoId: string, body: RepoSafetyProfileUpsert): Promise<RepoSafetyProfile> {
  const res = await fetch(`${BASE}/code-repositories/${repoId}/safety-profile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<RepoSafetyProfile>(res)
}

export async function updateRepoSafetyProfile(repoId: string, body: RepoSafetyProfileUpsert): Promise<RepoSafetyProfile> {
  const res = await fetch(`${BASE}/code-repositories/${repoId}/safety-profile`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<RepoSafetyProfile>(res)
}

// ---------------------------------------------------------------------------
// Epics
// ---------------------------------------------------------------------------

export async function listProjectEpics(projectId: string): Promise<Epic[]> {
  const res = await fetch(`${BASE}/projects/${projectId}/epics`, { headers: authHeaders() })
  return handleResponse<Epic[]>(res)
}

export async function listRequirementEpics(requirementId: string): Promise<Epic[]> {
  const res = await fetch(`${BASE}/requirements/${requirementId}/epics`, { headers: authHeaders() })
  return handleResponse<Epic[]>(res)
}

export async function getEpic(epicId: string): Promise<Epic> {
  const res = await fetch(`${BASE}/epics/${epicId}`, { headers: authHeaders() })
  return handleResponse<Epic>(res)
}

export async function createProjectEpic(projectId: string, body: EpicCreate): Promise<Epic> {
  const res = await fetch(`${BASE}/projects/${projectId}/epics`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<Epic>(res)
}

export async function updateEpic(epicId: string, patch: EpicUpdate): Promise<Epic> {
  const res = await fetch(`${BASE}/epics/${epicId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(patch),
  })
  return handleResponse<Epic>(res)
}

// ---------------------------------------------------------------------------
// Check definitions
// ---------------------------------------------------------------------------

export async function listProjectCheckDefinitions(projectId: string): Promise<CheckDefinition[]> {
  const res = await fetch(`${BASE}/projects/${projectId}/check-definitions`, { headers: authHeaders() })
  return handleResponse<CheckDefinition[]>(res)
}

export async function createCheckDefinition(
  projectId: string,
  body: CheckDefinitionCreate,
): Promise<CheckDefinition> {
  const res = await fetch(`${BASE}/projects/${projectId}/check-definitions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<CheckDefinition>(res)
}

export async function getCheckDefinition(definitionId: string): Promise<CheckDefinition> {
  const res = await fetch(`${BASE}/check-definitions/${definitionId}`, { headers: authHeaders() })
  return handleResponse<CheckDefinition>(res)
}

export async function updateCheckDefinition(
  definitionId: string,
  patch: CheckDefinitionUpdate,
): Promise<CheckDefinition> {
  const res = await fetch(`${BASE}/check-definitions/${definitionId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(patch),
  })
  return handleResponse<CheckDefinition>(res)
}

export async function generateCheckDefinitionsFromSafetyProfile(
  projectId: string,
  codeRepositoryId?: string | null,
): Promise<CheckDefinitionsFromSafetyProfileResponse> {
  const res = await fetch(`${BASE}/projects/${projectId}/check-definitions/from-safety-profile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ code_repository_id: codeRepositoryId ?? null }),
  })
  return handleResponse<CheckDefinitionsFromSafetyProfileResponse>(res)
}

// ---------------------------------------------------------------------------
// Check runs
// ---------------------------------------------------------------------------

export async function listProjectCheckRuns(projectId: string): Promise<CheckRun[]> {
  const res = await fetch(`${BASE}/projects/${projectId}/check-runs`, { headers: authHeaders() })
  return handleResponse<CheckRun[]>(res)
}

export async function getCheckRun(checkRunId: string): Promise<CheckRun> {
  const res = await fetch(`${BASE}/check-runs/${checkRunId}`, { headers: authHeaders() })
  return handleResponse<CheckRun>(res)
}

export async function listDevTaskCheckRuns(devTaskId: string): Promise<CheckRun[]> {
  const res = await fetch(`${BASE}/dev-tasks/${devTaskId}/check-runs`, { headers: authHeaders() })
  return handleResponse<CheckRun[]>(res)
}

export async function recordCheckRun(body: CheckRunCreate): Promise<CheckRun> {
  const res = await fetch(`${BASE}/check-runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<CheckRun>(res)
}

// ---------------------------------------------------------------------------
// Tool runner definitions
// ---------------------------------------------------------------------------

export async function listProjectToolRunnerDefinitions(projectId: string): Promise<ToolRunnerDefinition[]> {
  const res = await fetch(`${BASE}/projects/${projectId}/tool-runner-definitions`, { headers: authHeaders() })
  return handleResponse<ToolRunnerDefinition[]>(res)
}

export async function createToolRunnerDefinition(
  projectId: string,
  body: ToolRunnerDefinitionCreate,
): Promise<ToolRunnerDefinition> {
  const res = await fetch(`${BASE}/projects/${projectId}/tool-runner-definitions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<ToolRunnerDefinition>(res)
}

export async function updateToolRunnerDefinition(
  definitionId: string,
  patch: ToolRunnerDefinitionUpdate,
): Promise<ToolRunnerDefinition> {
  const res = await fetch(`${BASE}/tool-runner-definitions/${definitionId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(patch),
  })
  return handleResponse<ToolRunnerDefinition>(res)
}

export async function generateDefaultToolRunnerDefinitions(
  projectId: string,
  codeRepositoryId?: string | null,
): Promise<ToolRunnerDefinitionsDefaultsResponse> {
  const res = await fetch(`${BASE}/projects/${projectId}/tool-runner-definitions/defaults`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ code_repository_id: codeRepositoryId ?? null }),
  })
  return handleResponse<ToolRunnerDefinitionsDefaultsResponse>(res)
}

// ---------------------------------------------------------------------------
// Tool runs
// ---------------------------------------------------------------------------

export async function listProjectToolRuns(projectId: string): Promise<ToolRun[]> {
  const res = await fetch(`${BASE}/projects/${projectId}/tool-runs`, { headers: authHeaders() })
  return handleResponse<ToolRun[]>(res)
}

export async function listDevTaskToolRuns(devTaskId: string): Promise<ToolRun[]> {
  const res = await fetch(`${BASE}/dev-tasks/${devTaskId}/tool-runs`, { headers: authHeaders() })
  return handleResponse<ToolRun[]>(res)
}

export async function recordToolRun(body: ToolRunCreate): Promise<ToolRun> {
  const res = await fetch(`${BASE}/tool-runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<ToolRun>(res)
}

// ---------------------------------------------------------------------------
// OpenHandsRunner (Task 27)
// ---------------------------------------------------------------------------

export async function prepareOpenHandsPackage(
  devTaskId: string,
  body: OpenHandsPreparePackageRequest = {},
): Promise<OpenHandsPrepareResponse> {
  const res = await fetch(`${BASE}/dev-tasks/${devTaskId}/openhands/prepare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<OpenHandsPrepareResponse>(res)
}

export async function recordOpenHandsResult(
  toolRunId: string,
  body: OpenHandsRecordResultRequest,
): Promise<ToolRun> {
  const res = await fetch(`${BASE}/tool-runs/${toolRunId}/openhands/record-result`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<ToolRun>(res)
}

// ---------------------------------------------------------------------------
// PR draft workflow (Task 28)
// ---------------------------------------------------------------------------

export async function preparePullRequestDraft(
  projectId: string,
  body: PullRequestDraftCreate,
): Promise<PullRequestDraft> {
  const res = await fetch(`${BASE}/projects/${projectId}/pr-drafts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<PullRequestDraft>(res)
}

export async function listProjectPullRequestDrafts(
  projectId: string,
): Promise<PullRequestDraft[]> {
  const res = await fetch(`${BASE}/projects/${projectId}/pr-drafts`, {
    headers: authHeaders(),
  })
  return handleResponse<PullRequestDraft[]>(res)
}

export async function getPullRequestDraft(
  prDraftId: string,
): Promise<PullRequestDraft> {
  const res = await fetch(`${BASE}/pr-drafts/${prDraftId}`, {
    headers: authHeaders(),
  })
  return handleResponse<PullRequestDraft>(res)
}

export async function updatePullRequestDraft(
  prDraftId: string,
  body: PullRequestDraftUpdate,
): Promise<PullRequestDraft> {
  const res = await fetch(`${BASE}/pr-drafts/${prDraftId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<PullRequestDraft>(res)
}

export async function approvePullRequestDraft(
  prDraftId: string,
): Promise<PullRequestDraft> {
  const res = await fetch(`${BASE}/pr-drafts/${prDraftId}/approve`, {
    method: 'POST',
    headers: authHeaders(),
  })
  return handleResponse<PullRequestDraft>(res)
}

// ---------------------------------------------------------------------------
// PR review integration foundation (Task 29)
// ---------------------------------------------------------------------------

export async function createPullRequestReview(
  prDraftId: string,
  body: PullRequestReviewCreate,
): Promise<PullRequestReview> {
  const res = await fetch(`${BASE}/pr-drafts/${prDraftId}/reviews`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<PullRequestReview>(res)
}

export async function listPullRequestReviews(
  prDraftId: string,
): Promise<PullRequestReview[]> {
  const res = await fetch(`${BASE}/pr-drafts/${prDraftId}/reviews`, {
    headers: authHeaders(),
  })
  return handleResponse<PullRequestReview[]>(res)
}

export async function getPullRequestReview(
  reviewId: string,
): Promise<PullRequestReview> {
  const res = await fetch(`${BASE}/pr-reviews/${reviewId}`, {
    headers: authHeaders(),
  })
  return handleResponse<PullRequestReview>(res)
}

export async function updatePullRequestReview(
  reviewId: string,
  body: PullRequestReviewUpdate,
): Promise<PullRequestReview> {
  const res = await fetch(`${BASE}/pr-reviews/${reviewId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<PullRequestReview>(res)
}

export async function completePullRequestReview(
  reviewId: string,
  body: PullRequestReviewComplete,
): Promise<PullRequestReview> {
  const res = await fetch(`${BASE}/pr-reviews/${reviewId}/complete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<PullRequestReview>(res)
}

// CI failure ingestion and analysis (Task 30)

export async function recordCIEvent(
  projectId: string,
  body: CIEventCreate,
): Promise<CIEvent> {
  const res = await fetch(`${BASE}/projects/${projectId}/ci-events`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<CIEvent>(res)
}

export async function listProjectCIEvents(projectId: string): Promise<CIEvent[]> {
  const res = await fetch(`${BASE}/projects/${projectId}/ci-events`, {
    headers: authHeaders(),
  })
  return handleResponse<CIEvent[]>(res)
}

export async function getCIEvent(ciEventId: string): Promise<CIEvent> {
  const res = await fetch(`${BASE}/ci-events/${ciEventId}`, {
    headers: authHeaders(),
  })
  return handleResponse<CIEvent>(res)
}

export async function createCIAnalysis(
  ciEventId: string,
  body: CIAnalysisCreate = {},
): Promise<CIAnalysis> {
  const res = await fetch(`${BASE}/ci-events/${ciEventId}/analysis`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<CIAnalysis>(res)
}

export async function listCIEventAnalyses(ciEventId: string): Promise<CIAnalysis[]> {
  const res = await fetch(`${BASE}/ci-events/${ciEventId}/analyses`, {
    headers: authHeaders(),
  })
  return handleResponse<CIAnalysis[]>(res)
}

export async function getCIAnalysis(analysisId: string): Promise<CIAnalysis> {
  const res = await fetch(`${BASE}/ci-analyses/${analysisId}`, {
    headers: authHeaders(),
  })
  return handleResponse<CIAnalysis>(res)
}

// Production / incident workflow (Task 31)

export async function recordIncident(
  projectId: string,
  body: IncidentCreate,
): Promise<Incident> {
  const res = await fetch(`${BASE}/projects/${projectId}/incidents`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<Incident>(res)
}

export async function listProjectIncidents(projectId: string): Promise<Incident[]> {
  const res = await fetch(`${BASE}/projects/${projectId}/incidents`, {
    headers: authHeaders(),
  })
  return handleResponse<Incident[]>(res)
}

export async function getIncident(incidentId: string): Promise<Incident> {
  const res = await fetch(`${BASE}/incidents/${incidentId}`, {
    headers: authHeaders(),
  })
  return handleResponse<Incident>(res)
}

export async function updateIncident(
  incidentId: string,
  body: IncidentUpdate,
): Promise<Incident> {
  const res = await fetch(`${BASE}/incidents/${incidentId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<Incident>(res)
}

export async function createIncidentAnalysis(
  incidentId: string,
  body: IncidentAnalysisCreate = {},
): Promise<IncidentAnalysis> {
  const res = await fetch(`${BASE}/incidents/${incidentId}/analysis`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<IncidentAnalysis>(res)
}

export async function listIncidentAnalyses(
  incidentId: string,
): Promise<IncidentAnalysis[]> {
  const res = await fetch(`${BASE}/incidents/${incidentId}/analyses`, {
    headers: authHeaders(),
  })
  return handleResponse<IncidentAnalysis[]>(res)
}

export async function getIncidentAnalysis(
  analysisId: string,
): Promise<IncidentAnalysis> {
  const res = await fetch(`${BASE}/incident-analyses/${analysisId}`, {
    headers: authHeaders(),
  })
  return handleResponse<IncidentAnalysis>(res)
}

export async function prepareIncidentRemediation(
  incidentId: string,
): Promise<RemediationWorkItemDraft> {
  const res = await fetch(`${BASE}/incidents/${incidentId}/prepare-remediation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
  })
  return handleResponse<RemediationWorkItemDraft>(res)
}

// Project memory learning loop (Task 32)

export async function createMemoryLearningRun(
  projectId: string,
  body: MemoryLearningRunCreate,
): Promise<MemoryLearningRun> {
  const res = await fetch(`${BASE}/projects/${projectId}/memory-learning-runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<MemoryLearningRun>(res)
}

export async function listProjectMemoryLearningRuns(
  projectId: string,
): Promise<MemoryLearningRun[]> {
  const res = await fetch(`${BASE}/projects/${projectId}/memory-learning-runs`, {
    headers: authHeaders(),
  })
  return handleResponse<MemoryLearningRun[]>(res)
}

export async function getMemoryLearningRun(
  runId: string,
): Promise<MemoryLearningRun> {
  const res = await fetch(`${BASE}/memory-learning-runs/${runId}`, {
    headers: authHeaders(),
  })
  return handleResponse<MemoryLearningRun>(res)
}

export async function createMemoryCandidate(
  projectId: string,
  body: ProjectMemoryCandidateCreate,
): Promise<ProjectMemoryCandidate> {
  const res = await fetch(`${BASE}/projects/${projectId}/memory-candidates`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<ProjectMemoryCandidate>(res)
}

export async function listProjectMemoryCandidates(
  projectId: string,
): Promise<ProjectMemoryCandidate[]> {
  const res = await fetch(`${BASE}/projects/${projectId}/memory-candidates`, {
    headers: authHeaders(),
  })
  return handleResponse<ProjectMemoryCandidate[]>(res)
}

export async function getMemoryCandidate(
  candidateId: string,
): Promise<ProjectMemoryCandidate> {
  const res = await fetch(`${BASE}/memory-candidates/${candidateId}`, {
    headers: authHeaders(),
  })
  return handleResponse<ProjectMemoryCandidate>(res)
}

export async function updateMemoryCandidate(
  candidateId: string,
  body: ProjectMemoryCandidateUpdate,
): Promise<ProjectMemoryCandidate> {
  const res = await fetch(`${BASE}/memory-candidates/${candidateId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<ProjectMemoryCandidate>(res)
}

export async function approveMemoryCandidate(
  candidateId: string,
): Promise<ProjectMemoryCandidate> {
  const res = await fetch(`${BASE}/memory-candidates/${candidateId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
  })
  return handleResponse<ProjectMemoryCandidate>(res)
}

export async function rejectMemoryCandidate(
  candidateId: string,
  body: MemoryCandidateRejectRequest = {},
): Promise<ProjectMemoryCandidate> {
  const res = await fetch(`${BASE}/memory-candidates/${candidateId}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return handleResponse<ProjectMemoryCandidate>(res)
}
