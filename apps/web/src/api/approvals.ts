import { request } from './client'
import type {
  Approval,
  ApprovalCreate,
  ApprovalDecision,
} from '../types'

export function createApproval(data: ApprovalCreate): Promise<Approval> {
  return request<Approval>('POST', `/approvals`, data)
}

export function listProjectApprovals(projectId: string): Promise<Approval[]> {
  return request<Approval[]>('GET', `/projects/${projectId}/approvals`)
}

export function getApproval(approvalId: string): Promise<Approval> {
  return request<Approval>('GET', `/approvals/${approvalId}`)
}

export function decideApproval(approvalId: string, decision: ApprovalDecision): Promise<Approval> {
  return request<Approval>('PATCH', `/approvals/${approvalId}`, decision)
}
