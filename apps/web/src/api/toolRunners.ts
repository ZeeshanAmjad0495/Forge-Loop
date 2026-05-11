import { request } from './client'
import type {
  OpenHandsPreparePackageRequest,
  OpenHandsPrepareResponse,
  OpenHandsRecordResultRequest,
  ToolRun,
  ToolRunCreate,
  ToolRunnerDefinition,
  ToolRunnerDefinitionCreate,
  ToolRunnerDefinitionUpdate,
  ToolRunnerDefinitionsDefaultsResponse,
} from '../types'

export function listProjectToolRunnerDefinitions(projectId: string): Promise<ToolRunnerDefinition[]> {
  return request<ToolRunnerDefinition[]>('GET', `/projects/${projectId}/tool-runner-definitions`)
}

export function createToolRunnerDefinition(
  projectId: string,
  body: ToolRunnerDefinitionCreate,
): Promise<ToolRunnerDefinition> {
  return request<ToolRunnerDefinition>('POST', `/projects/${projectId}/tool-runner-definitions`, body)
}

export function updateToolRunnerDefinition(
  definitionId: string,
  patch: ToolRunnerDefinitionUpdate,
): Promise<ToolRunnerDefinition> {
  return request<ToolRunnerDefinition>('PATCH', `/tool-runner-definitions/${definitionId}`, patch)
}

export function generateDefaultToolRunnerDefinitions(
  projectId: string,
  codeRepositoryId?: string | null,
): Promise<ToolRunnerDefinitionsDefaultsResponse> {
  return request<ToolRunnerDefinitionsDefaultsResponse>(
    'POST',
    `/projects/${projectId}/tool-runner-definitions/defaults`,
    { code_repository_id: codeRepositoryId ?? null },
  )
}

export function listProjectToolRuns(projectId: string): Promise<ToolRun[]> {
  return request<ToolRun[]>('GET', `/projects/${projectId}/tool-runs`)
}

export function listDevTaskToolRuns(devTaskId: string): Promise<ToolRun[]> {
  return request<ToolRun[]>('GET', `/dev-tasks/${devTaskId}/tool-runs`)
}

export function recordToolRun(body: ToolRunCreate): Promise<ToolRun> {
  return request<ToolRun>('POST', `/tool-runs`, body)
}

export function prepareOpenHandsPackage(
  devTaskId: string,
  body: OpenHandsPreparePackageRequest = {},
): Promise<OpenHandsPrepareResponse> {
  return request<OpenHandsPrepareResponse>('POST', `/dev-tasks/${devTaskId}/openhands/prepare`, body)
}

export function recordOpenHandsResult(
  toolRunId: string,
  body: OpenHandsRecordResultRequest,
): Promise<ToolRun> {
  return request<ToolRun>('POST', `/tool-runs/${toolRunId}/openhands/record-result`, body)
}
