import json
import re
import uuid
from datetime import datetime, timezone

from .llm.base import LLMProvider
from .models import (
    AgentRun,
    Artifact,
    CodeRepository,
    Project,
    ProjectContext,
    RepoSafetyProfile,
    Requirement,
)
from .repositories import (
    AgentRunRepository,
    ArtifactRepository,
    RequirementRepository,
)

_AGENT_SENTINEL = "REQUIREMENT_GENERATION_AGENT"

_REQUIREMENT_FIELDS_STR = (
    "title",
    "problem_statement",
    "business_goal",
)
_REQUIREMENT_FIELDS_LIST = (
    "target_users",
    "functional_requirements",
    "non_functional_requirements",
    "acceptance_criteria",
    "constraints",
    "non_goals",
    "assumptions",
)


def _build_prompt(
    project: Project,
    project_context: ProjectContext | None,
    code_repository: CodeRepository | None,
    safety_profile: RepoSafetyProfile | None,
) -> str:
    prompt = f"""\
{_AGENT_SENTINEL}

You are a senior product/requirements analyst working inside a human-supervised SDLC platform called ForgeLoop.
Your job is to generate an initial set of structured product/software requirements from a project's details and context.

Rules:
- Generate product/software requirements, NOT developer tasks, NOT code, NOT branches/PRs.
- Do NOT generate epics, tasks, or subtasks.
- Requirements must be clear, testable, and reviewable.
- Mark uncertainty explicitly in `assumptions`.
- If project details are insufficient, still generate a small (2-3) set of draft requirements and call out missing information in `assumptions`.
- Be concise. Avoid padding.

Respond with a single JSON object (no markdown fences, no extra text) using exactly this shape:

{{
  "requirements": [
    {{
      "title": "short requirement title",
      "problem_statement": "the problem this requirement solves",
      "business_goal": "the business outcome this requirement supports",
      "target_users": ["user type 1", "user type 2"],
      "functional_requirements": ["functional requirement 1", "functional requirement 2"],
      "non_functional_requirements": ["non-functional requirement 1"],
      "acceptance_criteria": ["acceptance criterion 1", "acceptance criterion 2"],
      "constraints": ["constraint 1"],
      "non_goals": ["non-goal 1"],
      "assumptions": ["assumption 1"]
    }}
  ]
}}

Project name: {project.name}

Project description: {project.description}

Tech stack: {", ".join(project.tech_stack) if project.tech_stack else "none"}
"""
    if project_context and any(
        [
            project_context.architecture_notes,
            project_context.coding_standards,
            project_context.test_commands,
            project_context.deployment_commands,
            project_context.domain_rules,
            project_context.safety_rules,
        ]
    ):
        prompt += f"""
Project context (provided by ForgeLoop for this project):

Architecture notes: {project_context.architecture_notes or "none"}
Coding standards: {project_context.coding_standards or "none"}
Test commands: {project_context.test_commands or "none"}
Deployment commands: {project_context.deployment_commands or "none"}
Domain rules: {project_context.domain_rules or "none"}
Safety rules: {project_context.safety_rules or "none"}
"""
    if code_repository is not None:
        prompt += f"""
Connected code repository:
- provider: {code_repository.provider}
- repo_url: {code_repository.repo_url}
- default_branch: {code_repository.default_branch}
"""
    if safety_profile is not None:
        prompt += f"""
Repo safety profile:
- work_safe_mode: {safety_profile.work_safe_mode}
- protected_branches: {", ".join(safety_profile.protected_branches) or "none"}
- requires_approval_for: {", ".join(safety_profile.requires_approval_for) or "none"}
"""
    return prompt


def _parse_generation(raw: str) -> dict:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


def _fallback_generation(project: Project) -> dict:
    return {
        "requirements": [
            {
                "title": f"Draft requirement for {project.name}",
                "problem_statement": "Model output could not be parsed.",
                "business_goal": "",
                "target_users": [],
                "functional_requirements": [],
                "non_functional_requirements": [],
                "acceptance_criteria": [],
                "constraints": [],
                "non_goals": [],
                "assumptions": [
                    "Generated as a fallback because the model output could not be parsed.",
                ],
            }
        ]
    }


def _coerce_str(value) -> str:
    return value if isinstance(value, str) else ""


def _coerce_str_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, str)]


def _normalize_item(item: dict) -> dict:
    if not isinstance(item, dict):
        item = {}
    normalized = {f: _coerce_str(item.get(f, "")) for f in _REQUIREMENT_FIELDS_STR}
    for f in _REQUIREMENT_FIELDS_LIST:
        normalized[f] = _coerce_str_list(item.get(f, []))
    return normalized


def run_requirement_generation_agent(
    project: Project,
    provider: LLMProvider,
    agent_run_repo: AgentRunRepository,
    artifact_repo: ArtifactRepository,
    requirement_repo: RequirementRepository,
    project_context: ProjectContext | None = None,
    code_repository: CodeRepository | None = None,
    safety_profile: RepoSafetyProfile | None = None,
) -> tuple[AgentRun, list[Requirement], Artifact]:
    now = datetime.now(timezone.utc)
    run = AgentRun(
        id=str(uuid.uuid4()),
        ticket_id=None,
        requirement_id=None,
        agent_type="requirement_generation",
        provider=provider.provider_name,
        model=provider.model_name,
        status="completed",
        started_at=now,
        completed_at=now,
        error_message=None,
    )

    prompt = _build_prompt(project, project_context, code_repository, safety_profile)
    raw = provider.generate_text(prompt)

    parsed = _parse_generation(raw)
    items = parsed.get("requirements") if isinstance(parsed, dict) else None
    if not isinstance(items, list) or not items:
        items = _fallback_generation(project)["requirements"]

    requirements: list[Requirement] = []
    for raw_item in items:
        normalized = _normalize_item(raw_item)
        title = normalized["title"].strip()
        if not title:
            title = f"Draft requirement for {project.name}"
        requirement = Requirement(
            id=str(uuid.uuid4()),
            project_id=project.id,
            title=title,
            problem_statement=normalized["problem_statement"],
            business_goal=normalized["business_goal"],
            target_users=normalized["target_users"],
            functional_requirements=normalized["functional_requirements"],
            non_functional_requirements=normalized["non_functional_requirements"],
            acceptance_criteria=normalized["acceptance_criteria"],
            constraints=normalized["constraints"],
            non_goals=normalized["non_goals"],
            assumptions=normalized["assumptions"],
            source="agent_generated",
            status="draft",
            created_at=now,
            updated_at=now,
        )
        requirements.append(requirement)

    artifact = Artifact(
        id=str(uuid.uuid4()),
        ticket_id=None,
        requirement_id=None,
        agent_run_id=run.id,
        artifact_type="requirement_generation",
        content=raw,
        created_at=now,
    )

    agent_run_repo.save(run)
    for requirement in requirements:
        requirement_repo.save(requirement)
    artifact_repo.save(artifact)

    return run, requirements, artifact
