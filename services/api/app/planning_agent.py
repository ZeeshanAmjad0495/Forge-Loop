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
    prompt = f"Ticket title: {ticket.title}\n\nDescription: {ticket.description}"
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
