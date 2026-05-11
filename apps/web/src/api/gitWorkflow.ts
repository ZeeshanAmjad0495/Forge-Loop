import { request } from './client'
import type {
  GitCommitCreate,
  GitCommitRecord,
  GitInspectionResponse,
  WorkspaceBranch,
  WorkspaceBranchCreate,
  WorkspaceBranchResponse,
} from '../types'

export function inspectWorkspaceGit(workspaceId: string): Promise<GitInspectionResponse> {
  return request<GitInspectionResponse>('POST', `/workspaces/${workspaceId}/git/inspect`)
}

export function createWorkspaceBranch(
  workspaceId: string,
  body: WorkspaceBranchCreate,
): Promise<WorkspaceBranchResponse> {
  return request<WorkspaceBranchResponse>('POST', `/workspaces/${workspaceId}/branches`, body)
}

export function listWorkspaceBranches(workspaceId: string): Promise<WorkspaceBranch[]> {
  return request<WorkspaceBranch[]>('GET', `/workspaces/${workspaceId}/branches`)
}

export function getWorkspaceBranch(branchId: string): Promise<WorkspaceBranchResponse> {
  return request<WorkspaceBranchResponse>('GET', `/workspace-branches/${branchId}`)
}

export function inspectWorkspaceBranch(branchId: string): Promise<WorkspaceBranchResponse> {
  return request<WorkspaceBranchResponse>('POST', `/workspace-branches/${branchId}/inspect`)
}

export function commitWorkspaceBranch(
  branchId: string,
  body: GitCommitCreate,
): Promise<GitCommitRecord> {
  return request<GitCommitRecord>('POST', `/workspace-branches/${branchId}/commit`, body)
}

export function listWorkspaceBranchCommits(branchId: string): Promise<GitCommitRecord[]> {
  return request<GitCommitRecord[]>('GET', `/workspace-branches/${branchId}/commits`)
}
