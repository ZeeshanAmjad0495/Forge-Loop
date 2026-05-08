from typing import Protocol

from . import config
from .models import (
    AgentRun,
    Approval,
    AuditEvent,
    Artifact,
    CodeRepository,
    DevTask,
    Project,
    ProjectContext,
    Requirement,
    RequirementAnalysis,
    RepoSafetyProfile,
    Subtask,
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


class DevTaskRepository(Protocol):
    def save(self, dev_task: DevTask) -> None: ...
    def get(self, dev_task_id: str) -> DevTask | None: ...
    def update(self, dev_task: DevTask) -> None: ...
    def list_by_project(self, project_id: str) -> list[DevTask]: ...


class InMemoryDevTaskRepository:
    def __init__(self) -> None:
        self._store: dict[str, DevTask] = {}

    def save(self, dev_task: DevTask) -> None:
        self._store[dev_task.id] = dev_task

    def get(self, dev_task_id: str) -> DevTask | None:
        return self._store.get(dev_task_id)

    def update(self, dev_task: DevTask) -> None:
        self._store[dev_task.id] = dev_task

    def list_by_project(self, project_id: str) -> list[DevTask]:
        return [t for t in self._store.values() if t.project_id == project_id]


class FirestoreDevTaskRepository:
    def __init__(self, client, collection_name: str = "dev_tasks") -> None:
        self._collection = client.collection(collection_name)

    def save(self, dev_task: DevTask) -> None:
        self._collection.document(dev_task.id).set(dev_task.model_dump(mode="python"))

    def get(self, dev_task_id: str) -> DevTask | None:
        snap = self._collection.document(dev_task_id).get()
        if not snap.exists:
            return None
        return DevTask(**snap.to_dict())

    def update(self, dev_task: DevTask) -> None:
        self._collection.document(dev_task.id).set(dev_task.model_dump(mode="python"))

    def list_by_project(self, project_id: str) -> list[DevTask]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        return [DevTask(**d.to_dict()) for d in docs]


class SubtaskRepository(Protocol):
    def save(self, subtask: Subtask) -> None: ...
    def get(self, subtask_id: str) -> Subtask | None: ...
    def update(self, subtask: Subtask) -> None: ...
    def list_by_dev_task(self, dev_task_id: str) -> list[Subtask]: ...


class InMemorySubtaskRepository:
    def __init__(self) -> None:
        self._store: dict[str, Subtask] = {}

    def save(self, subtask: Subtask) -> None:
        self._store[subtask.id] = subtask

    def get(self, subtask_id: str) -> Subtask | None:
        return self._store.get(subtask_id)

    def update(self, subtask: Subtask) -> None:
        self._store[subtask.id] = subtask

    def list_by_dev_task(self, dev_task_id: str) -> list[Subtask]:
        return [s for s in self._store.values() if s.dev_task_id == dev_task_id]


class FirestoreSubtaskRepository:
    def __init__(self, client, collection_name: str = "subtasks") -> None:
        self._collection = client.collection(collection_name)

    def save(self, subtask: Subtask) -> None:
        self._collection.document(subtask.id).set(subtask.model_dump(mode="python"))

    def get(self, subtask_id: str) -> Subtask | None:
        snap = self._collection.document(subtask_id).get()
        if not snap.exists:
            return None
        return Subtask(**snap.to_dict())

    def update(self, subtask: Subtask) -> None:
        self._collection.document(subtask.id).set(subtask.model_dump(mode="python"))

    def list_by_dev_task(self, dev_task_id: str) -> list[Subtask]:
        docs = self._collection.where("dev_task_id", "==", dev_task_id).stream()
        return [Subtask(**d.to_dict()) for d in docs]


class ApprovalRepository(Protocol):
    def save(self, approval: Approval) -> None: ...
    def get(self, approval_id: str) -> Approval | None: ...
    def update(self, approval: Approval) -> None: ...
    def list_by_project(self, project_id: str) -> list[Approval]: ...
    def find_approved_for_target(self, target_type: str, target_id: str) -> Approval | None: ...


class InMemoryApprovalRepository:
    def __init__(self) -> None:
        self._store: dict[str, Approval] = {}

    def save(self, approval: Approval) -> None:
        self._store[approval.id] = approval

    def get(self, approval_id: str) -> Approval | None:
        return self._store.get(approval_id)

    def update(self, approval: Approval) -> None:
        self._store[approval.id] = approval

    def list_by_project(self, project_id: str) -> list[Approval]:
        matches = [a for a in self._store.values() if a.project_id == project_id]
        return sorted(matches, key=lambda a: a.created_at, reverse=True)

    def find_approved_for_target(self, target_type: str, target_id: str) -> Approval | None:
        for a in self._store.values():
            if a.target_type == target_type and a.target_id == target_id and a.status == "approved":
                return a
        return None


class FirestoreApprovalRepository:
    def __init__(self, client, collection_name: str = "approvals") -> None:
        self._collection = client.collection(collection_name)

    def save(self, approval: Approval) -> None:
        self._collection.document(approval.id).set(approval.model_dump(mode="python"))

    def get(self, approval_id: str) -> Approval | None:
        snap = self._collection.document(approval_id).get()
        if not snap.exists:
            return None
        return Approval(**snap.to_dict())

    def update(self, approval: Approval) -> None:
        self._collection.document(approval.id).set(approval.model_dump(mode="python"))

    def list_by_project(self, project_id: str) -> list[Approval]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        matches = [Approval(**d.to_dict()) for d in docs]
        return sorted(matches, key=lambda a: a.created_at, reverse=True)

    def find_approved_for_target(self, target_type: str, target_id: str) -> Approval | None:
        # Three-field equality query; may need a composite index in prod.
        # Fallback: filter status in code if index not available.
        docs = (
            self._collection
            .where("target_type", "==", target_type)
            .where("target_id", "==", target_id)
            .where("status", "==", "approved")
            .stream()
        )
        for d in docs:
            return Approval(**d.to_dict())
        return None


class AuditEventRepository(Protocol):
    def save(self, event: AuditEvent) -> None: ...
    def get(self, event_id: str) -> AuditEvent | None: ...
    def list_by_project(self, project_id: str) -> list[AuditEvent]: ...


class InMemoryAuditEventRepository:
    def __init__(self) -> None:
        self._store: dict[str, AuditEvent] = {}

    def save(self, event: AuditEvent) -> None:
        self._store[event.id] = event

    def get(self, event_id: str) -> AuditEvent | None:
        return self._store.get(event_id)

    def list_by_project(self, project_id: str) -> list[AuditEvent]:
        matches = [e for e in self._store.values() if e.project_id == project_id]
        return sorted(matches, key=lambda e: e.created_at, reverse=True)


class FirestoreAuditEventRepository:
    def __init__(self, client, collection_name: str = "audit_events") -> None:
        self._collection = client.collection(collection_name)

    def save(self, event: AuditEvent) -> None:
        self._collection.document(event.id).set(event.model_dump(mode="python"))

    def get(self, event_id: str) -> AuditEvent | None:
        snap = self._collection.document(event_id).get()
        if not snap.exists:
            return None
        return AuditEvent(**snap.to_dict())

    def list_by_project(self, project_id: str) -> list[AuditEvent]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        matches = [AuditEvent(**d.to_dict()) for d in docs]
        return sorted(matches, key=lambda e: e.created_at, reverse=True)


class CodeRepositoryRepository(Protocol):
    def save(self, repo: CodeRepository) -> None: ...
    def get(self, repo_id: str) -> CodeRepository | None: ...
    def update(self, repo: CodeRepository) -> None: ...
    def list_by_project(self, project_id: str) -> list[CodeRepository]: ...


class InMemoryCodeRepositoryRepository:
    def __init__(self) -> None:
        self._store: dict[str, CodeRepository] = {}

    def save(self, repo: CodeRepository) -> None:
        self._store[repo.id] = repo

    def get(self, repo_id: str) -> CodeRepository | None:
        return self._store.get(repo_id)

    def update(self, repo: CodeRepository) -> None:
        self._store[repo.id] = repo

    def list_by_project(self, project_id: str) -> list[CodeRepository]:
        return [r for r in self._store.values() if r.project_id == project_id]


class FirestoreCodeRepositoryRepository:
    def __init__(self, client, collection_name: str = "code_repositories") -> None:
        self._collection = client.collection(collection_name)

    def save(self, repo: CodeRepository) -> None:
        self._collection.document(repo.id).set(repo.model_dump(mode="python"))

    def get(self, repo_id: str) -> CodeRepository | None:
        snap = self._collection.document(repo_id).get()
        if not snap.exists:
            return None
        return CodeRepository(**snap.to_dict())

    def update(self, repo: CodeRepository) -> None:
        self._collection.document(repo.id).set(repo.model_dump(mode="python"))

    def list_by_project(self, project_id: str) -> list[CodeRepository]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        return [CodeRepository(**d.to_dict()) for d in docs]


class RepoSafetyProfileRepository(Protocol):
    def save(self, profile: RepoSafetyProfile) -> None: ...
    def get_by_repo(self, code_repository_id: str) -> RepoSafetyProfile | None: ...


class InMemoryRepoSafetyProfileRepository:
    def __init__(self) -> None:
        self._store: dict[str, RepoSafetyProfile] = {}

    def save(self, profile: RepoSafetyProfile) -> None:
        self._store[profile.id] = profile

    def get_by_repo(self, code_repository_id: str) -> RepoSafetyProfile | None:
        for p in self._store.values():
            if p.code_repository_id == code_repository_id:
                return p
        return None


class FirestoreRepoSafetyProfileRepository:
    def __init__(self, client, collection_name: str = "repo_safety_profiles") -> None:
        self._collection = client.collection(collection_name)

    def save(self, profile: RepoSafetyProfile) -> None:
        self._collection.document(profile.id).set(profile.model_dump(mode="python"))

    def get_by_repo(self, code_repository_id: str) -> RepoSafetyProfile | None:
        docs = self._collection.where("code_repository_id", "==", code_repository_id).stream()
        for d in docs:
            return RepoSafetyProfile(**d.to_dict())
        return None


def get_repositories() -> tuple[
    TicketRepository,
    AgentRunRepository,
    ArtifactRepository,
    ProjectRepository,
    ProjectContextRepository,
    RequirementAnalysisRepository,
    RequirementRepository,
    DevTaskRepository,
    SubtaskRepository,
    ApprovalRepository,
    AuditEventRepository,
    CodeRepositoryRepository,
    RepoSafetyProfileRepository,
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
            InMemoryDevTaskRepository(),
            InMemorySubtaskRepository(),
            InMemoryApprovalRepository(),
            InMemoryAuditEventRepository(),
            InMemoryCodeRepositoryRepository(),
            InMemoryRepoSafetyProfileRepository(),
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
            FirestoreDevTaskRepository(client),
            FirestoreSubtaskRepository(client),
            FirestoreApprovalRepository(client),
            FirestoreAuditEventRepository(client),
            FirestoreCodeRepositoryRepository(client),
            FirestoreRepoSafetyProfileRepository(client),
        )
    raise ValueError(
        f"Unknown REPOSITORY_PROVIDER: {config.REPOSITORY_PROVIDER!r}. Supported: memory, firestore"
    )
