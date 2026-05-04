import uuid
from datetime import datetime, timezone

from .llm.base import LLMProvider
from .models import AgentRun, Artifact, Ticket
from .repositories import AgentRunRepository, ArtifactRepository


def run_planning_agent(
    ticket: Ticket,
    provider: LLMProvider,
    agent_run_repo: AgentRunRepository,
    artifact_repo: ArtifactRepository,
) -> tuple[AgentRun, Artifact]:
    now = datetime.now(timezone.utc)
    run = AgentRun(
        id=str(uuid.uuid4()),
        ticket_id=ticket.id,
        agent_type="planning",
        provider=provider.provider_name,
        model=provider.model_name,
        status="completed",
        started_at=now,
        completed_at=now,
        error_message=None,
    )
    prompt = f"""\
You are a senior software delivery and QAOps planning agent working inside a human-supervised SDLC platform.
Your job is to produce an implementation-ready planning brief that helps a human or a coding agent understand exactly what to build, how to test it, and what risks to consider.
A human must review and approve this brief before any implementation begins.

Rules:
- Do NOT provide full source-code implementations.
- Do NOT output large code blocks or complete files.
- Do NOT choose a specific framework or library unless the ticket explicitly names one or repository context makes it obvious.
- If a short illustrative snippet (10 lines or fewer) would clarify a concept, you may include it — but keep it minimal.
- Focus on task decomposition, test strategy, acceptance criteria, and human approval points.
- Mark any unknowns or ambiguities clearly.
- Keep the output concise and actionable — avoid padding.
- Assume implementation will be done later by a human or coding agent who will read this brief.

Respond in markdown using exactly these sections in order:

# Implementation Brief

## 1. Requirement Summary
## 2. Clarified Behavior
## 3. Assumptions
## 4. Ambiguities / Questions
## 5. Affected Areas
## 6. Developer Task Breakdown
## 7. Suggested Implementation Approach
## 8. Test Strategy
## 9. Acceptance Criteria
## 10. Edge Cases
## 11. Risks
## 12. Rollback / Safety Notes
## 13. Human Approval Points
## 14. PR Checklist

Ticket title: {ticket.title}

Ticket description: {ticket.description}
"""
    content = provider.generate_text(prompt)
    artifact = Artifact(
        id=str(uuid.uuid4()),
        ticket_id=ticket.id,
        agent_run_id=run.id,
        artifact_type="implementation_brief",
        content=content,
        created_at=now,
    )
    agent_run_repo.save(run)
    artifact_repo.save(artifact)
    return run, artifact
