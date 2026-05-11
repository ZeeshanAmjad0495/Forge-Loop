import { request } from './client'
import type {
  CheckDefinition,
  CheckDefinitionCreate,
  CheckDefinitionUpdate,
  CheckDefinitionsFromSafetyProfileResponse,
  CheckExecutionRequest,
  CheckExecutionResponse,
  CheckRun,
  CheckRunCreate,
} from '../types'

export function listProjectCheckDefinitions(projectId: string): Promise<CheckDefinition[]> {
  return request<CheckDefinition[]>('GET', `/projects/${projectId}/check-definitions`)
}

export function createCheckDefinition(
  projectId: string,
  body: CheckDefinitionCreate,
): Promise<CheckDefinition> {
  return request<CheckDefinition>('POST', `/projects/${projectId}/check-definitions`, body)
}

export function getCheckDefinition(definitionId: string): Promise<CheckDefinition> {
  return request<CheckDefinition>('GET', `/check-definitions/${definitionId}`)
}

export function updateCheckDefinition(
  definitionId: string,
  patch: CheckDefinitionUpdate,
): Promise<CheckDefinition> {
  return request<CheckDefinition>('PATCH', `/check-definitions/${definitionId}`, patch)
}

export function generateCheckDefinitionsFromSafetyProfile(
  projectId: string,
  codeRepositoryId?: string | null,
): Promise<CheckDefinitionsFromSafetyProfileResponse> {
  return request<CheckDefinitionsFromSafetyProfileResponse>(
    'POST',
    `/projects/${projectId}/check-definitions/from-safety-profile`,
    { code_repository_id: codeRepositoryId ?? null },
  )
}

export function listProjectCheckRuns(projectId: string): Promise<CheckRun[]> {
  return request<CheckRun[]>('GET', `/projects/${projectId}/check-runs`)
}

export function getCheckRun(checkRunId: string): Promise<CheckRun> {
  return request<CheckRun>('GET', `/check-runs/${checkRunId}`)
}

export function listDevTaskCheckRuns(devTaskId: string): Promise<CheckRun[]> {
  return request<CheckRun[]>('GET', `/dev-tasks/${devTaskId}/check-runs`)
}

export function recordCheckRun(body: CheckRunCreate): Promise<CheckRun> {
  return request<CheckRun>('POST', `/check-runs`, body)
}

export function executeCheckDefinition(
  checkDefinitionId: string,
  body: CheckExecutionRequest,
): Promise<CheckExecutionResponse> {
  return request<CheckExecutionResponse>(
    'POST',
    `/check-definitions/${checkDefinitionId}/execute`,
    body,
  )
}
