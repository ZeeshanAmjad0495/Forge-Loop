import { request } from './client'
import type {
  PullRequestReview,
  PullRequestReviewComplete,
  PullRequestReviewCreate,
  PullRequestReviewUpdate,
} from '../types'

export function createPullRequestReview(
  prDraftId: string,
  body: PullRequestReviewCreate,
): Promise<PullRequestReview> {
  return request<PullRequestReview>('POST', `/pr-drafts/${prDraftId}/reviews`, body)
}

export function listPullRequestReviews(prDraftId: string): Promise<PullRequestReview[]> {
  return request<PullRequestReview[]>('GET', `/pr-drafts/${prDraftId}/reviews`)
}

export function getPullRequestReview(reviewId: string): Promise<PullRequestReview> {
  return request<PullRequestReview>('GET', `/pr-reviews/${reviewId}`)
}

export function updatePullRequestReview(
  reviewId: string,
  body: PullRequestReviewUpdate,
): Promise<PullRequestReview> {
  return request<PullRequestReview>('PATCH', `/pr-reviews/${reviewId}`, body)
}

export function completePullRequestReview(
  reviewId: string,
  body: PullRequestReviewComplete,
): Promise<PullRequestReview> {
  return request<PullRequestReview>('POST', `/pr-reviews/${reviewId}/complete`, body)
}
