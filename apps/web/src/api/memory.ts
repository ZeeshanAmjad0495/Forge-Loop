import { request } from './client'
import type {
  MemoryCandidateRejectRequest,
  MemoryLearningRun,
  MemoryLearningRunCreate,
  ProjectMemoryCandidate,
  ProjectMemoryCandidateCreate,
  ProjectMemoryCandidateUpdate,
} from '../types'

export function createMemoryLearningRun(
  projectId: string,
  body: MemoryLearningRunCreate,
): Promise<MemoryLearningRun> {
  return request<MemoryLearningRun>('POST', `/projects/${projectId}/memory-learning-runs`, body)
}

export function listProjectMemoryLearningRuns(projectId: string): Promise<MemoryLearningRun[]> {
  return request<MemoryLearningRun[]>('GET', `/projects/${projectId}/memory-learning-runs`)
}

export function getMemoryLearningRun(runId: string): Promise<MemoryLearningRun> {
  return request<MemoryLearningRun>('GET', `/memory-learning-runs/${runId}`)
}

export function createMemoryCandidate(
  projectId: string,
  body: ProjectMemoryCandidateCreate,
): Promise<ProjectMemoryCandidate> {
  return request<ProjectMemoryCandidate>('POST', `/projects/${projectId}/memory-candidates`, body)
}

export function listProjectMemoryCandidates(projectId: string): Promise<ProjectMemoryCandidate[]> {
  return request<ProjectMemoryCandidate[]>('GET', `/projects/${projectId}/memory-candidates`)
}

export function getMemoryCandidate(candidateId: string): Promise<ProjectMemoryCandidate> {
  return request<ProjectMemoryCandidate>('GET', `/memory-candidates/${candidateId}`)
}

export function updateMemoryCandidate(
  candidateId: string,
  body: ProjectMemoryCandidateUpdate,
): Promise<ProjectMemoryCandidate> {
  return request<ProjectMemoryCandidate>('PATCH', `/memory-candidates/${candidateId}`, body)
}

export function approveMemoryCandidate(candidateId: string): Promise<ProjectMemoryCandidate> {
  return request<ProjectMemoryCandidate>('POST', `/memory-candidates/${candidateId}/approve`)
}

export function rejectMemoryCandidate(
  candidateId: string,
  body: MemoryCandidateRejectRequest = {},
): Promise<ProjectMemoryCandidate> {
  return request<ProjectMemoryCandidate>('POST', `/memory-candidates/${candidateId}/reject`, body)
}
