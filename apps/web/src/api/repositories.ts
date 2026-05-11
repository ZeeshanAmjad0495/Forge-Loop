import { request } from './client'
import type {
  CodeRepository,
  CodeRepositoryCreate,
  CodeRepositoryUpdate,
  RepoSafetyProfile,
  RepoSafetyProfileUpsert,
} from '../types'

export function listProjectCodeRepositories(projectId: string): Promise<CodeRepository[]> {
  return request<CodeRepository[]>('GET', `/projects/${projectId}/code-repositories`)
}

export function createCodeRepository(projectId: string, body: CodeRepositoryCreate): Promise<CodeRepository> {
  return request<CodeRepository>('POST', `/projects/${projectId}/code-repositories`, body)
}

export function getCodeRepository(repoId: string): Promise<CodeRepository> {
  return request<CodeRepository>('GET', `/code-repositories/${repoId}`)
}

export function updateCodeRepository(repoId: string, body: CodeRepositoryUpdate): Promise<CodeRepository> {
  return request<CodeRepository>('PATCH', `/code-repositories/${repoId}`, body)
}

export function getRepoSafetyProfile(repoId: string): Promise<RepoSafetyProfile> {
  return request<RepoSafetyProfile>('GET', `/code-repositories/${repoId}/safety-profile`)
}

export function upsertRepoSafetyProfile(repoId: string, body: RepoSafetyProfileUpsert): Promise<RepoSafetyProfile> {
  return request<RepoSafetyProfile>('POST', `/code-repositories/${repoId}/safety-profile`, body)
}

export function updateRepoSafetyProfile(repoId: string, body: RepoSafetyProfileUpsert): Promise<RepoSafetyProfile> {
  return request<RepoSafetyProfile>('PATCH', `/code-repositories/${repoId}/safety-profile`, body)
}
