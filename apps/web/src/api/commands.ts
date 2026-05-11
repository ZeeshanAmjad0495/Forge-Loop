import { request } from './client'
import type {
  CommandDefinition,
  CommandDefinitionCreate,
  CommandDefinitionUpdate,
  CommandRun,
  CommandRunCreate,
} from '../types'

export function listProjectCommandDefinitions(projectId: string): Promise<CommandDefinition[]> {
  return request<CommandDefinition[]>('GET', `/projects/${projectId}/command-definitions`)
}

export function createCommandDefinition(
  projectId: string,
  body: CommandDefinitionCreate,
): Promise<CommandDefinition> {
  return request<CommandDefinition>('POST', `/projects/${projectId}/command-definitions`, body)
}

export function getCommandDefinition(definitionId: string): Promise<CommandDefinition> {
  return request<CommandDefinition>('GET', `/command-definitions/${definitionId}`)
}

export function patchCommandDefinition(
  definitionId: string,
  body: CommandDefinitionUpdate,
): Promise<CommandDefinition> {
  return request<CommandDefinition>('PATCH', `/command-definitions/${definitionId}`, body)
}

export function runCommandInWorkspace(
  workspaceId: string,
  body: CommandRunCreate,
): Promise<CommandRun> {
  return request<CommandRun>('POST', `/workspaces/${workspaceId}/command-runs`, body)
}

export function listWorkspaceCommandRuns(workspaceId: string): Promise<CommandRun[]> {
  return request<CommandRun[]>('GET', `/workspaces/${workspaceId}/command-runs`)
}

export function listProjectCommandRuns(projectId: string): Promise<CommandRun[]> {
  return request<CommandRun[]>('GET', `/projects/${projectId}/command-runs`)
}

export function getCommandRun(commandRunId: string): Promise<CommandRun> {
  return request<CommandRun>('GET', `/command-runs/${commandRunId}`)
}
