import { request } from './client'
import type {
  DevTask,
  DevTaskUpdate,
  Epic,
  EpicCreate,
  EpicUpdate,
  Subtask,
  SubtaskUpdate,
  TaskDecompositionResponse,
} from '../types'

export function createTaskDecomposition(
  requirementId: string,
  provider?: string,
): Promise<TaskDecompositionResponse> {
  return request<TaskDecompositionResponse>(
    'POST',
    `/requirements/${requirementId}/task-decompositions`,
    provider ? { provider } : undefined,
  )
}

export function listProjectDevTasks(projectId: string): Promise<DevTask[]> {
  return request<DevTask[]>('GET', `/projects/${projectId}/dev-tasks`)
}

export function getDevTask(devTaskId: string): Promise<{ dev_task: DevTask; subtasks: Subtask[] }> {
  return request<{ dev_task: DevTask; subtasks: Subtask[] }>('GET', `/dev-tasks/${devTaskId}`)
}

export function listDevTaskSubtasks(devTaskId: string): Promise<Subtask[]> {
  return request<Subtask[]>('GET', `/dev-tasks/${devTaskId}/subtasks`)
}

export function updateDevTask(devTaskId: string, patch: DevTaskUpdate): Promise<DevTask> {
  return request<DevTask>('PATCH', `/dev-tasks/${devTaskId}`, patch)
}

export function updateSubtask(subtaskId: string, patch: SubtaskUpdate): Promise<Subtask> {
  return request<Subtask>('PATCH', `/subtasks/${subtaskId}`, patch)
}

export function listProjectEpics(projectId: string): Promise<Epic[]> {
  return request<Epic[]>('GET', `/projects/${projectId}/epics`)
}

export function listRequirementEpics(requirementId: string): Promise<Epic[]> {
  return request<Epic[]>('GET', `/requirements/${requirementId}/epics`)
}

export function getEpic(epicId: string): Promise<Epic> {
  return request<Epic>('GET', `/epics/${epicId}`)
}

export function createProjectEpic(projectId: string, body: EpicCreate): Promise<Epic> {
  return request<Epic>('POST', `/projects/${projectId}/epics`, body)
}

export function updateEpic(epicId: string, patch: EpicUpdate): Promise<Epic> {
  return request<Epic>('PATCH', `/epics/${epicId}`, patch)
}
