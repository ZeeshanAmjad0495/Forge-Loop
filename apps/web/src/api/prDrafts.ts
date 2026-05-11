import { request } from './client'
import type {
  PullRequestDraft,
  PullRequestDraftCreate,
  PullRequestDraftUpdate,
} from '../types'

export function preparePullRequestDraft(
  projectId: string,
  body: PullRequestDraftCreate,
): Promise<PullRequestDraft> {
  return request<PullRequestDraft>('POST', `/projects/${projectId}/pr-drafts`, body)
}

export function listProjectPullRequestDrafts(projectId: string): Promise<PullRequestDraft[]> {
  return request<PullRequestDraft[]>('GET', `/projects/${projectId}/pr-drafts`)
}

export function getPullRequestDraft(prDraftId: string): Promise<PullRequestDraft> {
  return request<PullRequestDraft>('GET', `/pr-drafts/${prDraftId}`)
}

export function updatePullRequestDraft(
  prDraftId: string,
  body: PullRequestDraftUpdate,
): Promise<PullRequestDraft> {
  return request<PullRequestDraft>('PATCH', `/pr-drafts/${prDraftId}`, body)
}

export function approvePullRequestDraft(prDraftId: string): Promise<PullRequestDraft> {
  return request<PullRequestDraft>('POST', `/pr-drafts/${prDraftId}/approve`)
}
