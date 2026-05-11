import { request } from './client'
import type {
  Workspace,
  WorkspaceCreate,
  WorkspaceInspection,
  WorkspaceUpdate,
} from '../types'

export function listProjectWorkspaces(projectId: string): Promise<Workspace[]> {
  return request<Workspace[]>('GET', `/projects/${projectId}/workspaces`)
}

export function createWorkspace(projectId: string, body: WorkspaceCreate): Promise<Workspace> {
  return request<Workspace>('POST', `/projects/${projectId}/workspaces`, body)
}

export function getWorkspace(workspaceId: string): Promise<Workspace> {
  return request<Workspace>('GET', `/workspaces/${workspaceId}`)
}

export function updateWorkspace(workspaceId: string, body: WorkspaceUpdate): Promise<Workspace> {
  return request<Workspace>('PATCH', `/workspaces/${workspaceId}`, body)
}

export function inspectWorkspace(workspaceId: string): Promise<WorkspaceInspection> {
  return request<WorkspaceInspection>('POST', `/workspaces/${workspaceId}/inspect`)
}

export function archiveWorkspace(workspaceId: string): Promise<Workspace> {
  return request<Workspace>('POST', `/workspaces/${workspaceId}/archive`)
}
