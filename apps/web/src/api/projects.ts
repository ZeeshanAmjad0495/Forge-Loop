import { request } from './client'
import type {
  Project,
  ProjectContext,
  ProjectCreate,
  ProvidersResponse,
} from '../types'

export function listProjects(): Promise<Project[]> {
  return request<Project[]>('GET', `/projects`)
}

export function createProject(data: ProjectCreate): Promise<Project> {
  return request<Project>('POST', `/projects`, data)
}

export function getProjectContext(projectId: string): Promise<ProjectContext> {
  return request<ProjectContext>('GET', `/projects/${projectId}/context`)
}

export function updateProjectContext(
  projectId: string,
  ctx: Omit<ProjectContext, 'project_id' | 'updated_at'>,
): Promise<ProjectContext> {
  return request<ProjectContext>('PUT', `/projects/${projectId}/context`, ctx)
}

export function listProviders(): Promise<ProvidersResponse> {
  return request<ProvidersResponse>('GET', `/llm/providers`)
}
