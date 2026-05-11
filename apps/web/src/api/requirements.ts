import { request } from './client'
import type {
  Requirement,
  RequirementAnalysis,
  RequirementAnalysisRunResponse,
  RequirementCreate,
  RequirementGenerationResponse,
  RequirementUpdate,
} from '../types'

export function listProjectRequirements(projectId: string): Promise<Requirement[]> {
  return request<Requirement[]>('GET', `/projects/${projectId}/requirements`)
}

export function createProjectRequirement(
  projectId: string,
  data: RequirementCreate,
): Promise<Requirement> {
  return request<Requirement>('POST', `/projects/${projectId}/requirements`, data)
}

export function getRequirement(requirementId: string): Promise<Requirement> {
  return request<Requirement>('GET', `/requirements/${requirementId}`)
}

export function updateRequirement(
  requirementId: string,
  data: RequirementUpdate,
): Promise<Requirement> {
  return request<Requirement>('PUT', `/requirements/${requirementId}`, data)
}

export function createProjectRequirementGeneration(
  projectId: string,
  provider?: string,
): Promise<RequirementGenerationResponse> {
  return request<RequirementGenerationResponse>(
    'POST',
    `/projects/${projectId}/requirement-generations`,
    provider ? { provider } : undefined,
  )
}

export function createRequirementAnalysis(
  ticketId: string,
  provider?: string,
): Promise<RequirementAnalysisRunResponse> {
  return request<RequirementAnalysisRunResponse>(
    'POST',
    `/tickets/${ticketId}/requirement-analyses`,
    provider ? { provider } : undefined,
  )
}

export function listRequirementAnalyses(ticketId: string): Promise<RequirementAnalysis[]> {
  return request<RequirementAnalysis[]>('GET', `/tickets/${ticketId}/requirement-analyses`)
}

export function createRequirementAnalysisForRequirement(
  requirementId: string,
  provider?: string,
): Promise<RequirementAnalysisRunResponse> {
  return request<RequirementAnalysisRunResponse>(
    'POST',
    `/requirements/${requirementId}/requirement-analyses`,
    provider ? { provider } : undefined,
  )
}
