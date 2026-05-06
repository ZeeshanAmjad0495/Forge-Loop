import json
import re
import uuid
from datetime import datetime, timezone

from .llm.base import LLMProvider
from .models import AgentRun, Artifact, ProjectContext, Requirement, RequirementAnalysis, Ticket
from .repositories import AgentRunRepository, ArtifactRepository, RequirementAnalysisRepository

# Sentinel injected into the prompt so MockLLMProvider can detect it.
_AGENT_SENTINEL = "REQUIREMENT_ANALYSIS_AGENT"


def _build_prompt(ticket: Ticket, project_context: ProjectContext | None) -> str:
    prompt = f"""\
{_AGENT_SENTINEL}

You are a senior requirements analyst working inside a human-supervised SDLC platform called ForgeLoop.
Your job is to analyze a ticket and determine whether it is ready for implementation planning.

Rules:
- Do NOT generate implementation code.
- Do NOT create developer tasks or subtasks.
- Do NOT propose branch names or pull requests.
- Do NOT assume missing information — flag it explicitly.
- If any ambiguity remains, set readiness to "needs_clarification" and list specific clarification questions.
- If the requirement is clear and self-contained, set readiness to "ready_for_planning".
- Be concise. Avoid padding.

Respond with a single JSON object (no markdown fences, no extra text) using exactly this shape:

{{
  "summary": "one-sentence summary of what the ticket is asking for",
  "clarified_requirement": "restatement of the requirement in unambiguous terms, or best attempt given available info",
  "assumptions": ["assumption 1", "assumption 2"],
  "ambiguities": ["ambiguity 1", "ambiguity 2"],
  "clarification_questions": ["question 1", "question 2"],
  "risks": ["risk 1", "risk 2"],
  "affected_areas": ["area 1", "area 2"],
  "readiness": "ready_for_planning"
}}

Set readiness to "needs_clarification" if clarification_questions is non-empty.
Set readiness to "ready_for_planning" only if the requirement can be acted on without further input.

Ticket title: {ticket.title}

Ticket description: {ticket.description}
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
    return prompt


def _parse_analysis(raw: str) -> dict:
    # Try to extract the first JSON object from the response.
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


def _fallback_analysis() -> dict:
    return {
        "summary": "Analysis output could not be parsed.",
        "clarified_requirement": "",
        "assumptions": [],
        "ambiguities": ["Model returned unparseable output."],
        "clarification_questions": ["Model output could not be parsed; please retry."],
        "risks": [],
        "affected_areas": [],
        "readiness": "needs_clarification",
    }


def _build_prompt_for_requirement(
    requirement: Requirement, project_context: ProjectContext | None
) -> str:
    def _bullets(items: list[str]) -> str:
        return "\n".join(f"- {x}" for x in items) if items else "none"

    prompt = f"""\
{_AGENT_SENTINEL}

You are a senior requirements analyst working inside a human-supervised SDLC platform called ForgeLoop.
Your job is to analyze a structured requirement and determine whether it is ready for implementation planning.

Rules:
- Do NOT generate implementation code.
- Do NOT create developer tasks or subtasks.
- Do NOT propose branch names or pull requests.
- Do NOT assume missing information — flag it explicitly.
- If any ambiguity remains, set readiness to "needs_clarification" and list specific clarification questions.
- If the requirement is clear and self-contained, set readiness to "ready_for_planning".
- Be concise. Avoid padding.

Respond with a single JSON object (no markdown fences, no extra text) using exactly this shape:

{{
  "summary": "one-sentence summary of what is being asked",
  "clarified_requirement": "restatement of the requirement in unambiguous terms, or best attempt given available info",
  "assumptions": ["assumption 1", "assumption 2"],
  "ambiguities": ["ambiguity 1", "ambiguity 2"],
  "clarification_questions": ["question 1", "question 2"],
  "risks": ["risk 1", "risk 2"],
  "affected_areas": ["area 1", "area 2"],
  "readiness": "ready_for_planning"
}}

Set readiness to "needs_clarification" if clarification_questions is non-empty.
Set readiness to "ready_for_planning" only if the requirement can be acted on without further input.

Requirement title: {requirement.title}

Problem statement: {requirement.problem_statement or "none"}

Business goal: {requirement.business_goal or "none"}

Target users:
{_bullets(requirement.target_users)}

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

Stated assumptions:
{_bullets(requirement.assumptions)}
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
    return prompt


def run_requirement_analysis_agent(
    ticket: Ticket,
    provider: LLMProvider,
    agent_run_repo: AgentRunRepository,
    artifact_repo: ArtifactRepository,
    analysis_repo: RequirementAnalysisRepository,
    project_context: ProjectContext | None = None,
) -> tuple[AgentRun, RequirementAnalysis, Artifact]:
    now = datetime.now(timezone.utc)
    run = AgentRun(
        id=str(uuid.uuid4()),
        ticket_id=ticket.id,
        requirement_id=None,
        agent_type="requirement_analysis",
        provider=provider.provider_name,
        model=provider.model_name,
        status="completed",
        started_at=now,
        completed_at=now,
        error_message=None,
    )

    prompt = _build_prompt(ticket, project_context)
    raw = provider.generate_text(prompt)

    parsed = _parse_analysis(raw)
    if not parsed:
        parsed = _fallback_analysis()

    readiness = parsed.get("readiness", "needs_clarification")
    if readiness not in ("ready_for_planning", "needs_clarification"):
        readiness = "needs_clarification"

    analysis = RequirementAnalysis(
        id=str(uuid.uuid4()),
        project_id=ticket.project_id,
        ticket_id=ticket.id,
        requirement_id=None,
        agent_run_id=run.id,
        status="completed",
        summary=parsed.get("summary", ""),
        clarified_requirement=parsed.get("clarified_requirement", ""),
        assumptions=parsed.get("assumptions", []),
        ambiguities=parsed.get("ambiguities", []),
        clarification_questions=parsed.get("clarification_questions", []),
        risks=parsed.get("risks", []),
        affected_areas=parsed.get("affected_areas", []),
        readiness=readiness,
        created_at=now,
        updated_at=now,
    )

    artifact = Artifact(
        id=str(uuid.uuid4()),
        ticket_id=ticket.id,
        requirement_id=None,
        agent_run_id=run.id,
        artifact_type="requirement_analysis",
        content=raw,
        created_at=now,
    )

    agent_run_repo.save(run)
    analysis_repo.save(analysis)
    artifact_repo.save(artifact)

    return run, analysis, artifact


def run_requirement_analysis_for_requirement(
    requirement: Requirement,
    provider: LLMProvider,
    agent_run_repo: AgentRunRepository,
    artifact_repo: ArtifactRepository,
    analysis_repo: RequirementAnalysisRepository,
    project_context: ProjectContext | None = None,
) -> tuple[AgentRun, RequirementAnalysis, Artifact]:
    now = datetime.now(timezone.utc)
    run = AgentRun(
        id=str(uuid.uuid4()),
        ticket_id=None,
        requirement_id=requirement.id,
        agent_type="requirement_analysis",
        provider=provider.provider_name,
        model=provider.model_name,
        status="completed",
        started_at=now,
        completed_at=now,
        error_message=None,
    )

    prompt = _build_prompt_for_requirement(requirement, project_context)
    raw = provider.generate_text(prompt)

    parsed = _parse_analysis(raw)
    if not parsed:
        parsed = _fallback_analysis()

    readiness = parsed.get("readiness", "needs_clarification")
    if readiness not in ("ready_for_planning", "needs_clarification"):
        readiness = "needs_clarification"

    analysis = RequirementAnalysis(
        id=str(uuid.uuid4()),
        project_id=requirement.project_id,
        ticket_id=None,
        requirement_id=requirement.id,
        agent_run_id=run.id,
        status="completed",
        summary=parsed.get("summary", ""),
        clarified_requirement=parsed.get("clarified_requirement", ""),
        assumptions=parsed.get("assumptions", []),
        ambiguities=parsed.get("ambiguities", []),
        clarification_questions=parsed.get("clarification_questions", []),
        risks=parsed.get("risks", []),
        affected_areas=parsed.get("affected_areas", []),
        readiness=readiness,
        created_at=now,
        updated_at=now,
    )

    artifact = Artifact(
        id=str(uuid.uuid4()),
        ticket_id=None,
        requirement_id=requirement.id,
        agent_run_id=run.id,
        artifact_type="requirement_analysis",
        content=raw,
        created_at=now,
    )

    agent_run_repo.save(run)
    analysis_repo.save(analysis)
    artifact_repo.save(artifact)

    return run, analysis, artifact
