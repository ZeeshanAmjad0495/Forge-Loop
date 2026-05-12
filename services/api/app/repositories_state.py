"""Module-level repository singletons and shared writers.

Single source of truth for the wired-up repositories. `main.py` re-exports
these names so existing imports (`from app.main import audit_event_repo`,
the 26-name conftest import) continue to work unchanged.

S5 replaced the positional 26-tuple unpack with named-attribute access on
the ``Repositories`` container returned by ``get_repositories()``.
"""

from .repositories import get_repositories
from .services.audit_writer import AuditWriter

repos = get_repositories()

repo = repos.ticket
agent_run_repo = repos.agent_run
artifact_repo = repos.artifact
project_repo = repos.project
project_context_repo = repos.project_context
analysis_repo = repos.requirement_analysis
requirement_repo = repos.requirement
dev_task_repo = repos.dev_task
subtask_repo = repos.subtask
approval_repo = repos.approval
audit_event_repo = repos.audit_event
code_repo_repo = repos.code_repository
repo_safety_profile_repo = repos.repo_safety_profile
epic_repo = repos.epic
check_definition_repo = repos.check_definition
check_run_repo = repos.check_run
tool_runner_definition_repo = repos.tool_runner_definition
tool_run_repo = repos.tool_run
pr_draft_repo = repos.pr_draft
pr_review_repo = repos.pr_review
ci_event_repo = repos.ci_event
ci_analysis_repo = repos.ci_analysis
incident_repo = repos.incident
incident_analysis_repo = repos.incident_analysis
memory_learning_run_repo = repos.memory_learning_run
memory_candidate_repo = repos.memory_candidate
workspace_repo = repos.workspace
command_definition_repo = repos.command_definition
command_run_repo = repos.command_run
workspace_branch_repo = repos.workspace_branch
git_commit_record_repo = repos.git_commit_record
review_feedback_repo = repos.review_feedback
revision_work_item_repo = repos.revision_work_item
cost_record_repo = repos.cost_record
context_pack_repo = repos.context_pack
artifact_summary_repo = repos.artifact_summary
prompt_cache_repo = repos.prompt_cache
budget_policy_repo = repos.budget_policy
swarm_policy_repo = repos.swarm_policy
project_build_trial_repo = repos.project_build_trial
project_build_trial_stage_repo = repos.project_build_trial_stage
quality_metric_snapshot_repo = repos.quality_metric_snapshot
agent_failure_record_repo = repos.agent_failure_record
benchmark_scenario_repo = repos.benchmark_scenario
benchmark_run_repo = repos.benchmark_run
benchmark_run_result_repo = repos.benchmark_run_result
research_brief_repo = repos.research_brief
research_source_repo = repos.research_source
architecture_review_repo = repos.architecture_review
improvement_proposal_repo = repos.improvement_proposal
architecture_decision_repo = repos.architecture_decision
experiment_plan_repo = repos.experiment_plan
experiment_run_repo = repos.experiment_run
project_retrospective_repo = repos.project_retrospective
project_template_repo = repos.project_template
workflow_template_repo = repos.workflow_template
project_pack_repo = repos.project_pack
work_safe_policy_repo = repos.work_safe_policy
audit_export_request_repo = repos.audit_export_request
backup_export_repo = repos.backup_export
backup_import_repo = repos.backup_import

audit_writer = AuditWriter(audit_event_repo)
