import json
import re
import uuid
from datetime import datetime, timezone

from .llm.base import LLMProvider
from .models import (
    AgentRun,
    Artifact,
    DevTask,
    ProjectContext,
    Requirement,
    RequirementAnalysis,
    Subtask,
    Ticket,
)
from .repositories import AgentRunRepository, ArtifactRepository, DevTaskRepository, SubtaskRepository

_TASK_DECOMP_SENTINEL = "TASK_DECOMPOSITION_AGENT"


def _project_context_block(project_context: ProjectContext | None) -> str:
    if project_context is None:
        return ""
    if not any([
        project_context.architecture_notes,
        project_context.coding_standards,
        project_context.test_commands,
        project_context.deployment_commands,
        project_context.domain_rules,
        project_context.safety_rules,
    ]):
        return ""
    return f"""
Project context (provided by ForgeLoop):

Architecture notes: {project_context.architecture_notes or "none"}
Coding standards: {project_context.coding_standards or "none"}
Test commands: {project_context.test_commands or "none"}
Deployment commands: {project_context.deployment_commands or "none"}
Domain rules: {project_context.domain_rules or "none"}
Safety rules: {project_context.safety_rules or "none"}
"""


def _analysis_block(analysis: RequirementAnalysis | None) -> str:
    if analysis is None:
        return ""

    def _bullets(items: list[str]) -> str:
        return "\n".join(f"- {x}" for x in items) if items else "none"

    return f"""
Latest requirement analysis:

Clarified requirement: {analysis.clarified_requirement or "none"}

Assumptions:
{_bullets(analysis.assumptions)}

Risks:
{_bullets(analysis.risks)}

Affected areas:
{_bullets(analysis.affected_areas)}
"""


_PROMPT_INSTRUCTIONS = f"""\
{_TASK_DECOMP_SENTINEL}

You are a senior software delivery agent working inside a human-supervised SDLC platform called ForgeLoop.
Your job is to decompose a requirement into small, reviewable dev tasks and subtasks for a future coding agent or human to implement.

Rules:
- Do NOT implement code.
- Do NOT create branches or pull requests.
- Do NOT assume system details not provided.
- Decompose into tasks small enough for one agent or developer to complete in isolation.
- Set qa_required=true for tasks involving business logic, API behavior, data validation, auth/security, or user-facing behavior.
- Include acceptance_criteria and definition_of_done for every task.
- Use depends_on with the zero-based index of other tasks in this same response when a task depends on another.
- Keep subtasks to the most important steps within a task.
- Honor explicit scope boundaries in the requirement. If the requirement's first listed acceptance criterion or functional requirement is a project skeleton / health endpoint / test setup / README, the FIRST dev task must contain ONLY that scope. Storage/database/ORM, domain models, CRUD endpoints, business logic, validation, and incident logic belong in separate later tasks. Do not bundle them into the skeleton task even if they appear later in the requirement.
- Map each distinct functional requirement to its own dev task (or a small group of closely related ones). Do not collapse unrelated functional requirements into one task to make the decomposition shorter.
- A task titled or described as "skeleton", "scaffold", "bootstrap", or "project init" must not include database, ORM, model, schema, or CRUD subtasks. Its acceptance criteria and subtasks must be limited to: project file layout, framework entry point, a single health/status endpoint, test runner setup, README run/test commands, and .gitignore.
- Subtasks must stay inside the parent task's scope. If a subtask requires capability that belongs to a later task, drop the subtask — do not silently expand the parent task to absorb it.

task_type must be one of: backend, frontend, full_stack, testing, documentation, infrastructure, refactor, unknown.
priority must be one of: low, medium, high.

Anti-pattern (do NOT do this) — bundling storage into a skeleton task:
- "Project skeleton with health endpoint, pytest setup, and README" with subtasks
  that include "Initialize SQLAlchemy and SQLite", "Define Endpoint model",
  or "Create database tables on startup". Those belong in a separate
  storage/models task that depends_on the skeleton task.

Acceptable pattern — skeleton task stays minimal:
- "Project skeleton with health endpoint" — subtasks: create FastAPI app,
  add GET /health returning healthy status, set up pytest with a health
  test, write README run/test commands, add .gitignore.
- A separate "Storage and models" task — subtasks: pick storage, define
  models for the domain, wire startup, add storage tests.

Respond with a single JSON object (no markdown fences, no extra text) using exactly this shape:

{{
  "dev_tasks": [
    {{
      "title": "...",
      "description": "...",
      "task_type": "backend",
      "priority": "medium",
      "acceptance_criteria": ["..."],
      "definition_of_done": ["..."],
      "qa_required": true,
      "suggested_agent_type": "backend_coder",
      "depends_on": [],
      "subtasks": [
        {{
          "title": "...",
          "description": "...",
          "acceptance_criteria": ["..."],
          "qa_required": false
        }}
      ]
    }}
  ]
}}
"""


def _build_prompt_for_requirement(
    requirement: Requirement,
    project_context: ProjectContext | None,
    latest_analysis: RequirementAnalysis | None,
) -> str:
    def _bullets(items: list[str]) -> str:
        return "\n".join(f"- {x}" for x in items) if items else "none"

    body = f"""\
Requirement title: {requirement.title}

Problem statement: {requirement.problem_statement or "none"}

Business goal: {requirement.business_goal or "none"}

Functional requirements:
{_bullets(requirement.functional_requirements)}

Non-functional requirements:
{_bullets(requirement.non_functional_requirements)}

Acceptance criteria:
{_bullets(requirement.acceptance_criteria)}

Constraints:
{_bullets(requirement.constraints)}

Non-goals:
{_bullets(requirement.non_goals)}
"""
    return _PROMPT_INSTRUCTIONS + "\n" + body + _analysis_block(latest_analysis) + _project_context_block(project_context)


def _build_prompt_for_ticket(
    ticket: Ticket,
    project_context: ProjectContext | None,
    latest_analysis: RequirementAnalysis | None,
) -> str:
    body = f"""\
Ticket title: {ticket.title}

Ticket description: {ticket.description}
"""
    return _PROMPT_INSTRUCTIONS + "\n" + body + _analysis_block(latest_analysis) + _project_context_block(project_context)


def _parse_decomposition(raw: str) -> dict:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


def _fallback_decomposition() -> dict:
    return {
        "dev_tasks": [
            {
                "title": "Review and decompose requirement manually",
                "description": "Task decomposition output could not be parsed. A human should review the requirement and decompose it manually.",
                "task_type": "unknown",
                "priority": "high",
                "acceptance_criteria": ["Requirement is broken into implementable tasks"],
                "definition_of_done": ["Tasks are created and ready for assignment"],
                "qa_required": True,
                "suggested_agent_type": None,
                "depends_on": [],
                "subtasks": [],
            }
        ]
    }


def _build_records(
    parsed: dict,
    project_id: str,
    requirement_id: str | None,
    ticket_id: str | None,
    source_analysis_id: str | None,
    agent_run_id: str,
    now: datetime,
) -> tuple[list[DevTask], list[Subtask]]:
    raw_tasks = parsed.get("dev_tasks", [])
    task_ids: list[str] = [str(uuid.uuid4()) for _ in raw_tasks]

    dev_tasks: list[DevTask] = []
    subtasks: list[Subtask] = []

    for seq, (raw_task, task_id) in enumerate(zip(raw_tasks, task_ids)):
        raw_depends = raw_task.get("depends_on", [])
        resolved_depends: list[str] = []
        for idx in raw_depends:
            if isinstance(idx, int) and 0 <= idx < len(task_ids) and idx != seq:
                resolved_depends.append(task_ids[idx])

        task_type = raw_task.get("task_type", "unknown")
        if task_type not in ("backend", "frontend", "full_stack", "testing", "documentation", "infrastructure", "refactor", "unknown"):
            task_type = "unknown"

        priority = raw_task.get("priority", "medium")
        if priority not in ("low", "medium", "high"):
            priority = "medium"

        dev_task = DevTask(
            id=task_id,
            project_id=project_id,
            requirement_id=requirement_id,
            ticket_id=ticket_id,
            source_analysis_id=source_analysis_id,
            agent_run_id=agent_run_id,
            title=raw_task.get("title", "Untitled task"),
            description=raw_task.get("description", ""),
            task_type=task_type,
            status="proposed",
            priority=priority,
            sequence_order=seq,
            depends_on=resolved_depends,
            acceptance_criteria=raw_task.get("acceptance_criteria", []),
            definition_of_done=raw_task.get("definition_of_done", []),
            qa_required=bool(raw_task.get("qa_required", False)),
            suggested_agent_type=raw_task.get("suggested_agent_type") or None,
            created_at=now,
            updated_at=now,
        )
        dev_tasks.append(dev_task)

        for sub_seq, raw_sub in enumerate(raw_task.get("subtasks", [])):
            subtask = Subtask(
                id=str(uuid.uuid4()),
                dev_task_id=task_id,
                project_id=project_id,
                title=raw_sub.get("title", "Untitled subtask"),
                description=raw_sub.get("description", ""),
                status="proposed",
                sequence_order=sub_seq,
                acceptance_criteria=raw_sub.get("acceptance_criteria", []),
                qa_required=bool(raw_sub.get("qa_required", False)),
                created_at=now,
                updated_at=now,
            )
            subtasks.append(subtask)

    return dev_tasks, subtasks


def _run_decomposition(
    prompt: str,
    project_id: str,
    requirement_id: str | None,
    ticket_id: str | None,
    source_analysis_id: str | None,
    provider: LLMProvider,
    agent_run_repo: AgentRunRepository,
    artifact_repo: ArtifactRepository,
    dev_task_repo: DevTaskRepository,
    subtask_repo: SubtaskRepository,
) -> tuple[AgentRun, Artifact, list[DevTask], list[Subtask]]:
    now = datetime.now(timezone.utc)
    run = AgentRun(
        id=str(uuid.uuid4()),
        ticket_id=ticket_id,
        requirement_id=requirement_id,
        agent_type="task_decomposition",
        provider=provider.provider_name,
        model=provider.model_name,
        status="completed",
        started_at=now,
        completed_at=now,
        error_message=None,
    )

    raw = provider.generate_text(prompt)

    parsed = _parse_decomposition(raw)
    if not parsed:
        parsed = _fallback_decomposition()

    dev_tasks, subtasks = _build_records(
        parsed, project_id, requirement_id, ticket_id, source_analysis_id, run.id, now
    )

    artifact = Artifact(
        id=str(uuid.uuid4()),
        ticket_id=ticket_id,
        requirement_id=requirement_id,
        agent_run_id=run.id,
        artifact_type="task_decomposition",
        content=raw,
        created_at=now,
    )

    agent_run_repo.save(run)
    artifact_repo.save(artifact)
    for dt in dev_tasks:
        dev_task_repo.save(dt)
    for st in subtasks:
        subtask_repo.save(st)

    return run, artifact, dev_tasks, subtasks


def run_task_decomposition_for_requirement(
    requirement: Requirement,
    provider: LLMProvider,
    agent_run_repo: AgentRunRepository,
    artifact_repo: ArtifactRepository,
    dev_task_repo: DevTaskRepository,
    subtask_repo: SubtaskRepository,
    project_context: ProjectContext | None = None,
    latest_analysis: RequirementAnalysis | None = None,
) -> tuple[AgentRun, Artifact, list[DevTask], list[Subtask]]:
    prompt = _build_prompt_for_requirement(requirement, project_context, latest_analysis)
    source_analysis_id = latest_analysis.id if latest_analysis else None
    return _run_decomposition(
        prompt,
        project_id=requirement.project_id,
        requirement_id=requirement.id,
        ticket_id=None,
        source_analysis_id=source_analysis_id,
        provider=provider,
        agent_run_repo=agent_run_repo,
        artifact_repo=artifact_repo,
        dev_task_repo=dev_task_repo,
        subtask_repo=subtask_repo,
    )


def run_task_decomposition_for_ticket(
    ticket: Ticket,
    provider: LLMProvider,
    agent_run_repo: AgentRunRepository,
    artifact_repo: ArtifactRepository,
    dev_task_repo: DevTaskRepository,
    subtask_repo: SubtaskRepository,
    project_context: ProjectContext | None = None,
    latest_analysis: RequirementAnalysis | None = None,
) -> tuple[AgentRun, Artifact, list[DevTask], list[Subtask]]:
    prompt = _build_prompt_for_ticket(ticket, project_context, latest_analysis)
    source_analysis_id = latest_analysis.id if latest_analysis else None
    project_id = ticket.project_id or "unassigned"
    return _run_decomposition(
        prompt,
        project_id=project_id,
        requirement_id=None,
        ticket_id=ticket.id,
        source_analysis_id=source_analysis_id,
        provider=provider,
        agent_run_repo=agent_run_repo,
        artifact_repo=artifact_repo,
        dev_task_repo=dev_task_repo,
        subtask_repo=subtask_repo,
    )
