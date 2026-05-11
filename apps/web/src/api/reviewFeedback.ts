import { request } from './client'
import type {
  ReviewFeedback,
  ReviewFeedbackCreate,
  ReviewFeedbackImportResponse,
  ReviewFeedbackResolve,
  ReviewFeedbackUpdate,
  RevisionPlanResponse,
  RevisionWorkItem,
  RevisionWorkItemCreate,
  RevisionWorkItemUpdate,
} from '../types'

export function createReviewFeedback(
  prDraftId: string,
  body: ReviewFeedbackCreate,
): Promise<ReviewFeedback> {
  return request<ReviewFeedback>('POST', `/pr-drafts/${prDraftId}/feedback-items`, body)
}

export function listPrDraftReviewFeedback(prDraftId: string): Promise<ReviewFeedback[]> {
  return request<ReviewFeedback[]>('GET', `/pr-drafts/${prDraftId}/feedback-items`)
}

export function getReviewFeedback(feedbackId: string): Promise<ReviewFeedback> {
  return request<ReviewFeedback>('GET', `/review-feedback/${feedbackId}`)
}

export function patchReviewFeedback(
  feedbackId: string,
  body: ReviewFeedbackUpdate,
): Promise<ReviewFeedback> {
  return request<ReviewFeedback>('PATCH', `/review-feedback/${feedbackId}`, body)
}

export function importReviewFeedbackFromFindings(
  reviewId: string,
): Promise<ReviewFeedbackImportResponse> {
  return request<ReviewFeedbackImportResponse>(
    'POST',
    `/pr-reviews/${reviewId}/feedback-items/from-findings`,
  )
}

export function planReviewFeedbackRevision(
  feedbackId: string,
  body: RevisionWorkItemCreate,
): Promise<RevisionPlanResponse> {
  return request<RevisionPlanResponse>(
    'POST',
    `/review-feedback/${feedbackId}/plan-revision`,
    body,
  )
}

export function resolveReviewFeedback(
  feedbackId: string,
  body: ReviewFeedbackResolve,
): Promise<ReviewFeedback> {
  return request<ReviewFeedback>('POST', `/review-feedback/${feedbackId}/resolve`, body)
}

export function listPrDraftRevisionWorkItems(
  prDraftId: string,
): Promise<RevisionWorkItem[]> {
  return request<RevisionWorkItem[]>('GET', `/pr-drafts/${prDraftId}/revision-work-items`)
}

export function getRevisionWorkItem(revisionId: string): Promise<RevisionWorkItem> {
  return request<RevisionWorkItem>('GET', `/revision-work-items/${revisionId}`)
}

export function patchRevisionWorkItem(
  revisionId: string,
  body: RevisionWorkItemUpdate,
): Promise<RevisionWorkItem> {
  return request<RevisionWorkItem>('PATCH', `/revision-work-items/${revisionId}`, body)
}
