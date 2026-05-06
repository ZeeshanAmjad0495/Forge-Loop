from typing import Protocol

from . import config
from .models import (
    AgentRun,
    Artifact,
    Project,
    ProjectContext,
    Requirement,
    RequirementAnalysis,
    Ticket,
)


class TicketRepository(Protocol):
    def save(self, ticket: Ticket) -> None: ...
    def get(self, ticket_id: str) -> Ticket | None: ...
    def list_by_project(self, project_id: str) -> list[Ticket]: ...


class InMemoryTicketRepository:
    def __init__(self) -> None:
        self._store: dict[str, Ticket] = {}

    def save(self, ticket: Ticket) -> None:
        self._store[ticket.id] = ticket

    def get(self, ticket_id: str) -> Ticket | None:
        return self._store.get(ticket_id)

    def list_by_project(self, project_id: str) -> list[Ticket]:
        return [t for t in self._store.values() if t.project_id == project_id]


class AgentRunRepository(Protocol):
    def save(self, run: AgentRun) -> None: ...
    def get(self, run_id: str) -> AgentRun | None: ...


class InMemoryAgentRunRepository:
    def __init__(self) -> None:
        self._store: dict[str, AgentRun] = {}

    def save(self, run: AgentRun) -> None:
        self._store[run.id] = run

    def get(self, run_id: str) -> AgentRun | None:
        return self._store.get(run_id)


class ArtifactRepository(Protocol):
    def save(self, artifact: Artifact) -> None: ...
    def list_by_ticket(self, ticket_id: str) -> list[Artifact]: ...


class InMemoryArtifactRepository:
    def __init__(self) -> None:
        self._store: dict[str, Artifact] = {}

    def save(self, artifact: Artifact) -> None:
        self._store[artifact.id] = artifact

    def list_by_ticket(self, ticket_id: str) -> list[Artifact]:
        return [a for a in self._store.values() if a.ticket_id == ticket_id]


class ProjectRepository(Protocol):
    def save(self, project: Project) -> None: ...
    def get(self, project_id: str) -> Project | None: ...
    def list_all(self) -> list[Project]: ...


class InMemoryProjectRepository:
    def __init__(self) -> None:
        self._store: dict[str, Project] = {}

    def save(self, project: Project) -> None:
        self._store[project.id] = project

    def get(self, project_id: str) -> Project | None:
        return self._store.get(project_id)

    def list_all(self) -> list[Project]:
        return list(self._store.values())


class ProjectContextRepository(Protocol):
    def save(self, ctx: ProjectContext) -> None: ...
    def get(self, project_id: str) -> ProjectContext | None: ...


class InMemoryProjectContextRepository:
    def __init__(self) -> None:
        self._store: dict[str, ProjectContext] = {}

    def save(self, ctx: ProjectContext) -> None:
        self._store[ctx.project_id] = ctx

    def get(self, project_id: str) -> ProjectContext | None:
        return self._store.get(project_id)


class FirestoreTicketRepository:
    def __init__(self, client, collection_name: str = "tickets") -> None:
        self._collection = client.collection(collection_name)

    def save(self, ticket: Ticket) -> None:
        self._collection.document(ticket.id).set(ticket.model_dump(mode="python"))

    def get(self, ticket_id: str) -> Ticket | None:
        snap = self._collection.document(ticket_id).get()
        if not snap.exists:
            return None
        return Ticket(**snap.to_dict())

    def list_by_project(self, project_id: str) -> list[Ticket]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        return [Ticket(**d.to_dict()) for d in docs]


class FirestoreAgentRunRepository:
    def __init__(self, client, collection_name: str = "agent_runs") -> None:
        self._collection = client.collection(collection_name)

    def save(self, run: AgentRun) -> None:
        self._collection.document(run.id).set(run.model_dump(mode="python"))

    def get(self, run_id: str) -> AgentRun | None:
        snap = self._collection.document(run_id).get()
        if not snap.exists:
            return None
        return AgentRun(**snap.to_dict())


class FirestoreArtifactRepository:
    def __init__(self, client, collection_name: str = "artifacts") -> None:
        self._collection = client.collection(collection_name)

    def save(self, artifact: Artifact) -> None:
        self._collection.document(artifact.id).set(artifact.model_dump(mode="python"))

    def list_by_ticket(self, ticket_id: str) -> list[Artifact]:
        docs = self._collection.where("ticket_id", "==", ticket_id).stream()
        return [Artifact(**d.to_dict()) for d in docs]


class FirestoreProjectRepository:
    def __init__(self, client, collection_name: str = "projects") -> None:
        self._collection = client.collection(collection_name)

    def save(self, project: Project) -> None:
        self._collection.document(project.id).set(project.model_dump(mode="python"))

    def get(self, project_id: str) -> Project | None:
        snap = self._collection.document(project_id).get()
        if not snap.exists:
            return None
        return Project(**snap.to_dict())

    def list_all(self) -> list[Project]:
        return [Project(**d.to_dict()) for d in self._collection.stream()]


class FirestoreProjectContextRepository:
    def __init__(self, client, collection_name: str = "project_contexts") -> None:
        self._collection = client.collection(collection_name)

    def save(self, ctx: ProjectContext) -> None:
        self._collection.document(ctx.project_id).set(ctx.model_dump(mode="python"))

    def get(self, project_id: str) -> ProjectContext | None:
        snap = self._collection.document(project_id).get()
        if not snap.exists:
            return None
        return ProjectContext(**snap.to_dict())


class RequirementAnalysisRepository(Protocol):
    def save(self, analysis: RequirementAnalysis) -> None: ...
    def list_by_ticket(self, ticket_id: str) -> list[RequirementAnalysis]: ...
    def get_latest_by_ticket(self, ticket_id: str) -> RequirementAnalysis | None: ...
    def list_by_requirement(self, requirement_id: str) -> list[RequirementAnalysis]: ...
    def get_latest_by_requirement(self, requirement_id: str) -> RequirementAnalysis | None: ...


class InMemoryRequirementAnalysisRepository:
    def __init__(self) -> None:
        self._store: dict[str, RequirementAnalysis] = {}

    def save(self, analysis: RequirementAnalysis) -> None:
        self._store[analysis.id] = analysis

    def list_by_ticket(self, ticket_id: str) -> list[RequirementAnalysis]:
        return [a for a in self._store.values() if a.ticket_id == ticket_id]

    def get_latest_by_ticket(self, ticket_id: str) -> RequirementAnalysis | None:
        matches = self.list_by_ticket(ticket_id)
        if not matches:
            return None
        return max(matches, key=lambda a: a.created_at)

    def list_by_requirement(self, requirement_id: str) -> list[RequirementAnalysis]:
        return [a for a in self._store.values() if a.requirement_id == requirement_id]

    def get_latest_by_requirement(self, requirement_id: str) -> RequirementAnalysis | None:
        matches = self.list_by_requirement(requirement_id)
        if not matches:
            return None
        return max(matches, key=lambda a: a.created_at)


class FirestoreRequirementAnalysisRepository:
    def __init__(self, client, collection_name: str = "requirement_analyses") -> None:
        self._collection = client.collection(collection_name)

    def save(self, analysis: RequirementAnalysis) -> None:
        self._collection.document(analysis.id).set(analysis.model_dump(mode="python"))

    def list_by_ticket(self, ticket_id: str) -> list[RequirementAnalysis]:
        docs = self._collection.where("ticket_id", "==", ticket_id).stream()
        return [RequirementAnalysis(**d.to_dict()) for d in docs]

    def get_latest_by_ticket(self, ticket_id: str) -> RequirementAnalysis | None:
        matches = self.list_by_ticket(ticket_id)
        if not matches:
            return None
        return max(matches, key=lambda a: a.created_at)

    def list_by_requirement(self, requirement_id: str) -> list[RequirementAnalysis]:
        docs = self._collection.where("requirement_id", "==", requirement_id).stream()
        return [RequirementAnalysis(**d.to_dict()) for d in docs]

    def get_latest_by_requirement(self, requirement_id: str) -> RequirementAnalysis | None:
        matches = self.list_by_requirement(requirement_id)
        if not matches:
            return None
        return max(matches, key=lambda a: a.created_at)


class RequirementRepository(Protocol):
    def save(self, requirement: Requirement) -> None: ...
    def get(self, requirement_id: str) -> Requirement | None: ...
    def update(self, requirement: Requirement) -> None: ...
    def list_by_project(self, project_id: str) -> list[Requirement]: ...


class InMemoryRequirementRepository:
    def __init__(self) -> None:
        self._store: dict[str, Requirement] = {}

    def save(self, requirement: Requirement) -> None:
        self._store[requirement.id] = requirement

    def get(self, requirement_id: str) -> Requirement | None:
        return self._store.get(requirement_id)

    def update(self, requirement: Requirement) -> None:
        self._store[requirement.id] = requirement

    def list_by_project(self, project_id: str) -> list[Requirement]:
        return [r for r in self._store.values() if r.project_id == project_id]


class FirestoreRequirementRepository:
    def __init__(self, client, collection_name: str = "requirements") -> None:
        self._collection = client.collection(collection_name)

    def save(self, requirement: Requirement) -> None:
        self._collection.document(requirement.id).set(requirement.model_dump(mode="python"))

    def get(self, requirement_id: str) -> Requirement | None:
        snap = self._collection.document(requirement_id).get()
        if not snap.exists:
            return None
        return Requirement(**snap.to_dict())

    def update(self, requirement: Requirement) -> None:
        self._collection.document(requirement.id).set(requirement.model_dump(mode="python"))

    def list_by_project(self, project_id: str) -> list[Requirement]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        return [Requirement(**d.to_dict()) for d in docs]


def get_repositories() -> tuple[
    TicketRepository,
    AgentRunRepository,
    ArtifactRepository,
    ProjectRepository,
    ProjectContextRepository,
    RequirementAnalysisRepository,
    RequirementRepository,
]:
    if config.REPOSITORY_PROVIDER == "memory":
        return (
            InMemoryTicketRepository(),
            InMemoryAgentRunRepository(),
            InMemoryArtifactRepository(),
            InMemoryProjectRepository(),
            InMemoryProjectContextRepository(),
            InMemoryRequirementAnalysisRepository(),
            InMemoryRequirementRepository(),
        )
    if config.REPOSITORY_PROVIDER == "firestore":
        from google.cloud import firestore

        client = firestore.Client(
            project=config.GCP_PROJECT_ID or None,
            database=config.FIRESTORE_DATABASE,
        )
        return (
            FirestoreTicketRepository(client),
            FirestoreAgentRunRepository(client),
            FirestoreArtifactRepository(client),
            FirestoreProjectRepository(client),
            FirestoreProjectContextRepository(client),
            FirestoreRequirementAnalysisRepository(client),
            FirestoreRequirementRepository(client),
        )
    raise ValueError(
        f"Unknown REPOSITORY_PROVIDER: {config.REPOSITORY_PROVIDER!r}. Supported: memory, firestore"
    )
