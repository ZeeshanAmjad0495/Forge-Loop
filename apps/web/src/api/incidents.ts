import { request } from './client'
import type {
  Incident,
  IncidentAnalysis,
  IncidentAnalysisCreate,
  IncidentCreate,
  IncidentUpdate,
  RemediationWorkItemDraft,
} from '../types'

export function recordIncident(projectId: string, body: IncidentCreate): Promise<Incident> {
  return request<Incident>('POST', `/projects/${projectId}/incidents`, body)
}

export function listProjectIncidents(projectId: string): Promise<Incident[]> {
  return request<Incident[]>('GET', `/projects/${projectId}/incidents`)
}

export function getIncident(incidentId: string): Promise<Incident> {
  return request<Incident>('GET', `/incidents/${incidentId}`)
}

export function updateIncident(incidentId: string, body: IncidentUpdate): Promise<Incident> {
  return request<Incident>('PATCH', `/incidents/${incidentId}`, body)
}

export function createIncidentAnalysis(
  incidentId: string,
  body: IncidentAnalysisCreate = {},
): Promise<IncidentAnalysis> {
  return request<IncidentAnalysis>('POST', `/incidents/${incidentId}/analysis`, body)
}

export function listIncidentAnalyses(incidentId: string): Promise<IncidentAnalysis[]> {
  return request<IncidentAnalysis[]>('GET', `/incidents/${incidentId}/analyses`)
}

export function getIncidentAnalysis(analysisId: string): Promise<IncidentAnalysis> {
  return request<IncidentAnalysis>('GET', `/incident-analyses/${analysisId}`)
}

export function prepareIncidentRemediation(incidentId: string): Promise<RemediationWorkItemDraft> {
  return request<RemediationWorkItemDraft>('POST', `/incidents/${incidentId}/prepare-remediation`)
}
