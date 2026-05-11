import { request } from './client'
import type {
  CIAnalysis,
  CIAnalysisCreate,
  CIEvent,
  CIEventCreate,
} from '../types'

export function recordCIEvent(projectId: string, body: CIEventCreate): Promise<CIEvent> {
  return request<CIEvent>('POST', `/projects/${projectId}/ci-events`, body)
}

export function listProjectCIEvents(projectId: string): Promise<CIEvent[]> {
  return request<CIEvent[]>('GET', `/projects/${projectId}/ci-events`)
}

export function getCIEvent(ciEventId: string): Promise<CIEvent> {
  return request<CIEvent>('GET', `/ci-events/${ciEventId}`)
}

export function createCIAnalysis(
  ciEventId: string,
  body: CIAnalysisCreate = {},
): Promise<CIAnalysis> {
  return request<CIAnalysis>('POST', `/ci-events/${ciEventId}/analysis`, body)
}

export function listCIEventAnalyses(ciEventId: string): Promise<CIAnalysis[]> {
  return request<CIAnalysis[]>('GET', `/ci-events/${ciEventId}/analyses`)
}

export function getCIAnalysis(analysisId: string): Promise<CIAnalysis> {
  return request<CIAnalysis>('GET', `/ci-analyses/${analysisId}`)
}
