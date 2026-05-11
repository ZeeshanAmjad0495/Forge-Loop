import type {
  AssigneeType,
  CheckRunConclusion,
  CheckRunStatus,
  CheckRunTargetType,
  CheckSeverity,
  CheckType,
  DevTaskStatus,
  EpicPriority,
  EpicStatus,
  IncidentStatus,
  MemoryCandidateMemoryType,
  MemoryCandidateSourceType,
  RunnerType,
  ToolRunConclusion,
  ToolRunStatus,
  ToolRunTargetType,
  ToolRunnerMode,
} from '../types'

export const ALL_STATUSES: DevTaskStatus[] = ['proposed', 'ready', 'in_progress', 'blocked', 'completed']

export const EPIC_STATUSES: EpicStatus[] = ['proposed', 'ready', 'in_progress', 'blocked', 'completed']
export const EPIC_PRIORITIES: EpicPriority[] = ['low', 'medium', 'high']
export const ASSIGNEE_TYPES: AssigneeType[] = ['unassigned', 'human', 'agent']

export const CHECK_TYPES: CheckType[] = [
  'tests', 'build', 'lint', 'typecheck', 'coverage',
  'security_sast', 'dependency_scan', 'secret_scan', 'container_scan',
  'accessibility', 'e2e', 'custom',
]
export const CHECK_SEVERITIES: CheckSeverity[] = ['info', 'warning', 'blocking']
export const CHECK_RUN_TARGET_TYPES: CheckRunTargetType[] = [
  'project', 'requirement', 'epic', 'dev_task', 'subtask', 'pull_request', 'manual',
]
export const CHECK_RUN_STATUSES: CheckRunStatus[] = ['pending', 'running', 'completed', 'failed']
export const CHECK_RUN_CONCLUSIONS: CheckRunConclusion[] = ['success', 'failure', 'neutral', 'skipped', 'cancelled']

export const RUNNER_TYPES: RunnerType[] = [
  'openhands', 'aider', 'cline', 'opencode', 'hermes', 'openclaw', 'manual', 'custom',
]
export const RUNNER_MODES: ToolRunnerMode[] = ['local', 'api', 'manual', 'dry_run']
export const TOOL_RUN_TARGET_TYPES: ToolRunTargetType[] = [
  'requirement', 'epic', 'dev_task', 'subtask', 'check_run', 'manual',
]
export const TOOL_RUN_STATUSES: ToolRunStatus[] = ['pending', 'running', 'completed', 'failed', 'cancelled']
export const TOOL_RUN_CONCLUSIONS: ToolRunConclusion[] = [
  'success', 'failure', 'neutral', 'skipped', 'requires_human_action',
]

export const INCIDENT_STATUSES: IncidentStatus[] = [
  'reported',
  'triaging',
  'remediation_planned',
  'remediation_approved',
  'resolved',
  'closed',
  'cancelled',
]

export const MEMORY_TYPES: MemoryCandidateMemoryType[] = [
  'architecture_decision',
  'project_rule',
  'coding_standard',
  'testing_rule',
  'deployment_rule',
  'approved_approach',
  'rejected_approach',
  'known_risk',
  'known_failure_pattern',
  'human_feedback',
  'important_file',
  'prompt_note',
  'qa_learning',
  'incident_learning',
  'cost_note',
  'custom',
]

export const LEARNING_SOURCE_TYPES: MemoryCandidateSourceType[] = [
  'ci_analysis',
  'incident_analysis',
  'pr_review',
  'check_run',
  'tool_run',
  'approval',
  'dev_task',
  'subtask',
]
