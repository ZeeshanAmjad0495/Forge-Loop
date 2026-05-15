"""FastAPI app composition root.

Routes live in `services/api/app/routes/`. Shared repository singletons
live in `services/api/app/repositories_state.py` and are re-exported here
so existing imports (`from app.main import audit_event_repo`, the
26-name conftest import) continue to work unchanged.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .repositories_state import (
    agent_run_repo,
    analysis_repo,
    approval_repo,
    artifact_repo,
    audit_event_repo,
    audit_writer,
    check_definition_repo,
    check_run_repo,
    ci_analysis_repo,
    ci_event_repo,
    code_repo_repo,
    dev_task_repo,
    epic_repo,
    incident_analysis_repo,
    incident_repo,
    memory_candidate_repo,
    memory_learning_run_repo,
    pr_draft_repo,
    pr_review_repo,
    project_context_repo,
    project_repo,
    repo,
    repo_safety_profile_repo,
    requirement_repo,
    subtask_repo,
    tool_run_repo,
    tool_runner_definition_repo,
    workspace_repo,
)
from .routes import (
    agent_failures,
    approvals,
    aider,
    architecture_decisions,
    architecture_reviews,
    improvement_proposals,
    artifact_summaries,
    audit,
    auth,
    backups,
    benchmarks,
    budgets,
    checks,
    ci,
    code_repositories,
    commands,
    context_packs,
    cost_records,
    cost_reporting,
    dev_tasks,
    epics,
    evaluation_trials,
    experiments,
    feedback_analytics,
    git_workflow,
    health,
    incidents,
    integration_runs,
    llm,
    memory,
    memory_retrieval,
    model_routing,
    openhands,
    planning,
    pr_drafts,
    pr_reviews,
    project_packs,
    project_templates,
    projects,
    quality_metrics,
    prompt_cache,
    requirements,
    research_briefs,
    research_sources,
    retrospectives,
    review_feedback,
    runtime,
    subtasks,
    swarm_policies,
    task_decomposition,
    tickets,
    tool_runners,
    work_safe_policies,
    workflow_templates,
    workspaces,
)
from .services.runtime_profile import startup_log_line

@asynccontextmanager
async def lifespan(_app: FastAPI):
    config.validate_startup_config()
    import logging

    logging.getLogger(__name__).info(startup_log_line())
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(tickets.router)
app.include_router(planning.router)
app.include_router(requirements.router)
app.include_router(llm.router)
app.include_router(task_decomposition.router)
app.include_router(dev_tasks.router)
app.include_router(subtasks.router)
app.include_router(approvals.router)
app.include_router(audit.router)
app.include_router(code_repositories.router)
app.include_router(epics.router)
app.include_router(checks.router)
app.include_router(tool_runners.router)
app.include_router(openhands.router)
app.include_router(aider.router)
app.include_router(pr_drafts.router)
app.include_router(pr_reviews.router)
app.include_router(ci.router)
app.include_router(incidents.router)
app.include_router(memory.router)
app.include_router(memory_retrieval.router)
app.include_router(model_routing.router)
app.include_router(prompt_cache.router)
app.include_router(budgets.router)
app.include_router(swarm_policies.router)
app.include_router(evaluation_trials.router)
app.include_router(quality_metrics.router)
app.include_router(feedback_analytics.router)
app.include_router(agent_failures.router)
app.include_router(cost_reporting.router)
app.include_router(benchmarks.router)
app.include_router(workspaces.router)
app.include_router(commands.router)
app.include_router(git_workflow.router)
app.include_router(integration_runs.router)
app.include_router(review_feedback.router)
app.include_router(runtime.router)
app.include_router(cost_records.router)
app.include_router(context_packs.router)
app.include_router(artifact_summaries.router)
app.include_router(research_briefs.router)
app.include_router(research_sources.router)
app.include_router(architecture_reviews.router)
app.include_router(improvement_proposals.router)
app.include_router(architecture_decisions.router)
app.include_router(experiments.router)
app.include_router(retrospectives.router)
app.include_router(project_templates.router)
app.include_router(workflow_templates.router)
app.include_router(project_packs.router)
app.include_router(work_safe_policies.router)
app.include_router(backups.router)


__all__ = [
    "app",
    "audit_writer",
    "repo",
    "agent_run_repo",
    "artifact_repo",
    "project_repo",
    "project_context_repo",
    "analysis_repo",
    "requirement_repo",
    "dev_task_repo",
    "subtask_repo",
    "approval_repo",
    "audit_event_repo",
    "code_repo_repo",
    "repo_safety_profile_repo",
    "epic_repo",
    "check_definition_repo",
    "check_run_repo",
    "tool_runner_definition_repo",
    "tool_run_repo",
    "pr_draft_repo",
    "pr_review_repo",
    "ci_event_repo",
    "ci_analysis_repo",
    "incident_repo",
    "incident_analysis_repo",
    "memory_learning_run_repo",
    "memory_candidate_repo",
    "workspace_repo",
]
