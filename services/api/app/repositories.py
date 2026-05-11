import dataclasses
from dataclasses import dataclass
from typing import Protocol

from . import config
from .models import (
    AgentRun,
    Approval,
    AuditEvent,
    Artifact,
    CheckDefinition,
    CheckRun,
    CIAnalysis,
    CIEvent,
    CodeRepository,
    CommandDefinition,
    CommandRun,
    DevTask,
    Epic,
    GitCommitRecord,
    Incident,
    IncidentAnalysis,
    MemoryLearningRun,
    Project,
    ProjectMemoryCandidate,
    ProjectContext,
    PullRequestDraft,
    PullRequestReview,
    Requirement,
    RequirementAnalysis,
    RepoSafetyProfile,
    ReviewFeedback,
    RevisionWorkItem,
    Subtask,
    Ticket,
    ToolRun,
    ToolRunnerDefinition,
    Workspace,
    WorkspaceBranch,
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

    def clear(self) -> None:
        self._store.clear()


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

    def clear(self) -> None:
        self._store.clear()


class ArtifactRepository(Protocol):
    def save(self, artifact: Artifact) -> None: ...
    def get(self, artifact_id: str) -> Artifact | None: ...
    def list_by_ticket(self, ticket_id: str) -> list[Artifact]: ...


class InMemoryArtifactRepository:
    def __init__(self) -> None:
        self._store: dict[str, Artifact] = {}

    def save(self, artifact: Artifact) -> None:
        self._store[artifact.id] = artifact

    def get(self, artifact_id: str) -> Artifact | None:
        return self._store.get(artifact_id)

    def list_by_ticket(self, ticket_id: str) -> list[Artifact]:
        return [a for a in self._store.values() if a.ticket_id == ticket_id]

    def clear(self) -> None:
        self._store.clear()


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

    def clear(self) -> None:
        self._store.clear()


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

    def clear(self) -> None:
        self._store.clear()


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

    def get(self, artifact_id: str) -> Artifact | None:
        snap = self._collection.document(artifact_id).get()
        if not snap.exists:
            return None
        return Artifact(**snap.to_dict())

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

    def clear(self) -> None:
        self._store.clear()


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

    def clear(self) -> None:
        self._store.clear()


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

    def clear(self) -> None:
        self._store.clear()


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

    def clear(self) -> None:
        self._store.clear()


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

    def clear(self) -> None:
        self._store.clear()


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

    def clear(self) -> None:
        self._store.clear()


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

    def clear(self) -> None:
        self._store.clear()


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

    def clear(self) -> None:
        self._store.clear()


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


class EpicRepository(Protocol):
    def save(self, epic: Epic) -> None: ...
    def get(self, epic_id: str) -> Epic | None: ...
    def update(self, epic: Epic) -> None: ...
    def list_by_project(self, project_id: str) -> list[Epic]: ...
    def list_by_requirement(self, requirement_id: str) -> list[Epic]: ...


class InMemoryEpicRepository:
    def __init__(self) -> None:
        self._store: dict[str, Epic] = {}

    def save(self, epic: Epic) -> None:
        self._store[epic.id] = epic

    def get(self, epic_id: str) -> Epic | None:
        return self._store.get(epic_id)

    def update(self, epic: Epic) -> None:
        self._store[epic.id] = epic

    def list_by_project(self, project_id: str) -> list[Epic]:
        return [e for e in self._store.values() if e.project_id == project_id]

    def list_by_requirement(self, requirement_id: str) -> list[Epic]:
        return [e for e in self._store.values() if e.requirement_id == requirement_id]

    def clear(self) -> None:
        self._store.clear()


class FirestoreEpicRepository:
    def __init__(self, client, collection_name: str = "epics") -> None:
        self._collection = client.collection(collection_name)

    def save(self, epic: Epic) -> None:
        self._collection.document(epic.id).set(epic.model_dump(mode="python"))

    def get(self, epic_id: str) -> Epic | None:
        snap = self._collection.document(epic_id).get()
        if not snap.exists:
            return None
        return Epic(**snap.to_dict())

    def update(self, epic: Epic) -> None:
        self._collection.document(epic.id).set(epic.model_dump(mode="python"))

    def list_by_project(self, project_id: str) -> list[Epic]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        return [Epic(**d.to_dict()) for d in docs]

    def list_by_requirement(self, requirement_id: str) -> list[Epic]:
        docs = self._collection.where("requirement_id", "==", requirement_id).stream()
        return [Epic(**d.to_dict()) for d in docs]


class CheckDefinitionRepository(Protocol):
    def save(self, definition: CheckDefinition) -> None: ...
    def get(self, definition_id: str) -> CheckDefinition | None: ...
    def update(self, definition: CheckDefinition) -> None: ...
    def list_by_project(self, project_id: str) -> list[CheckDefinition]: ...


class InMemoryCheckDefinitionRepository:
    def __init__(self) -> None:
        self._store: dict[str, CheckDefinition] = {}

    def save(self, definition: CheckDefinition) -> None:
        self._store[definition.id] = definition

    def get(self, definition_id: str) -> CheckDefinition | None:
        return self._store.get(definition_id)

    def update(self, definition: CheckDefinition) -> None:
        self._store[definition.id] = definition

    def list_by_project(self, project_id: str) -> list[CheckDefinition]:
        return [d for d in self._store.values() if d.project_id == project_id]

    def clear(self) -> None:
        self._store.clear()


class FirestoreCheckDefinitionRepository:
    def __init__(self, client, collection_name: str = "check_definitions") -> None:
        self._collection = client.collection(collection_name)

    def save(self, definition: CheckDefinition) -> None:
        self._collection.document(definition.id).set(definition.model_dump(mode="python"))

    def get(self, definition_id: str) -> CheckDefinition | None:
        snap = self._collection.document(definition_id).get()
        if not snap.exists:
            return None
        return CheckDefinition(**snap.to_dict())

    def update(self, definition: CheckDefinition) -> None:
        self._collection.document(definition.id).set(definition.model_dump(mode="python"))

    def list_by_project(self, project_id: str) -> list[CheckDefinition]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        return [CheckDefinition(**d.to_dict()) for d in docs]


class CheckRunRepository(Protocol):
    def save(self, run: CheckRun) -> None: ...
    def get(self, run_id: str) -> CheckRun | None: ...
    def list_by_project(self, project_id: str) -> list[CheckRun]: ...
    def list_by_target(self, target_type: str, target_id: str) -> list[CheckRun]: ...


class InMemoryCheckRunRepository:
    def __init__(self) -> None:
        self._store: dict[str, CheckRun] = {}

    def save(self, run: CheckRun) -> None:
        self._store[run.id] = run

    def get(self, run_id: str) -> CheckRun | None:
        return self._store.get(run_id)

    def list_by_project(self, project_id: str) -> list[CheckRun]:
        return [r for r in self._store.values() if r.project_id == project_id]

    def list_by_target(self, target_type: str, target_id: str) -> list[CheckRun]:
        return [
            r for r in self._store.values()
            if r.target_type == target_type and r.target_id == target_id
        ]

    def clear(self) -> None:
        self._store.clear()


class FirestoreCheckRunRepository:
    def __init__(self, client, collection_name: str = "check_runs") -> None:
        self._collection = client.collection(collection_name)

    def save(self, run: CheckRun) -> None:
        self._collection.document(run.id).set(run.model_dump(mode="python"))

    def get(self, run_id: str) -> CheckRun | None:
        snap = self._collection.document(run_id).get()
        if not snap.exists:
            return None
        return CheckRun(**snap.to_dict())

    def list_by_project(self, project_id: str) -> list[CheckRun]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        return [CheckRun(**d.to_dict()) for d in docs]

    def list_by_target(self, target_type: str, target_id: str) -> list[CheckRun]:
        # Compound equality query; may need a composite index in Firestore prod.
        docs = (
            self._collection
            .where("target_type", "==", target_type)
            .where("target_id", "==", target_id)
            .stream()
        )
        return [CheckRun(**d.to_dict()) for d in docs]


class ToolRunnerDefinitionRepository(Protocol):
    def save(self, definition: ToolRunnerDefinition) -> None: ...
    def get(self, definition_id: str) -> ToolRunnerDefinition | None: ...
    def update(self, definition: ToolRunnerDefinition) -> None: ...
    def list_by_project(self, project_id: str) -> list[ToolRunnerDefinition]: ...


class InMemoryToolRunnerDefinitionRepository:
    def __init__(self) -> None:
        self._store: dict[str, ToolRunnerDefinition] = {}

    def save(self, definition: ToolRunnerDefinition) -> None:
        self._store[definition.id] = definition

    def get(self, definition_id: str) -> ToolRunnerDefinition | None:
        return self._store.get(definition_id)

    def update(self, definition: ToolRunnerDefinition) -> None:
        self._store[definition.id] = definition

    def list_by_project(self, project_id: str) -> list[ToolRunnerDefinition]:
        return [d for d in self._store.values() if d.project_id == project_id]

    def clear(self) -> None:
        self._store.clear()


class FirestoreToolRunnerDefinitionRepository:
    def __init__(self, client, collection_name: str = "tool_runner_definitions") -> None:
        self._collection = client.collection(collection_name)

    def save(self, definition: ToolRunnerDefinition) -> None:
        self._collection.document(definition.id).set(definition.model_dump(mode="python"))

    def get(self, definition_id: str) -> ToolRunnerDefinition | None:
        snap = self._collection.document(definition_id).get()
        if not snap.exists:
            return None
        return ToolRunnerDefinition(**snap.to_dict())

    def update(self, definition: ToolRunnerDefinition) -> None:
        self._collection.document(definition.id).set(definition.model_dump(mode="python"))

    def list_by_project(self, project_id: str) -> list[ToolRunnerDefinition]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        return [ToolRunnerDefinition(**d.to_dict()) for d in docs]


class ToolRunRepository(Protocol):
    def save(self, run: ToolRun) -> None: ...
    def get(self, run_id: str) -> ToolRun | None: ...
    def list_by_project(self, project_id: str) -> list[ToolRun]: ...
    def list_by_target(self, target_type: str, target_id: str) -> list[ToolRun]: ...


class InMemoryToolRunRepository:
    def __init__(self) -> None:
        self._store: dict[str, ToolRun] = {}

    def save(self, run: ToolRun) -> None:
        self._store[run.id] = run

    def get(self, run_id: str) -> ToolRun | None:
        return self._store.get(run_id)

    def list_by_project(self, project_id: str) -> list[ToolRun]:
        return [r for r in self._store.values() if r.project_id == project_id]

    def list_by_target(self, target_type: str, target_id: str) -> list[ToolRun]:
        return [
            r for r in self._store.values()
            if r.target_type == target_type and r.target_id == target_id
        ]

    def clear(self) -> None:
        self._store.clear()


class FirestoreToolRunRepository:
    def __init__(self, client, collection_name: str = "tool_runs") -> None:
        self._collection = client.collection(collection_name)

    def save(self, run: ToolRun) -> None:
        self._collection.document(run.id).set(run.model_dump(mode="python"))

    def get(self, run_id: str) -> ToolRun | None:
        snap = self._collection.document(run_id).get()
        if not snap.exists:
            return None
        return ToolRun(**snap.to_dict())

    def list_by_project(self, project_id: str) -> list[ToolRun]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        return [ToolRun(**d.to_dict()) for d in docs]

    def list_by_target(self, target_type: str, target_id: str) -> list[ToolRun]:
        # Compound equality query; may need a composite index in Firestore prod.
        docs = (
            self._collection
            .where("target_type", "==", target_type)
            .where("target_id", "==", target_id)
            .stream()
        )
        return [ToolRun(**d.to_dict()) for d in docs]


class PullRequestDraftRepository(Protocol):
    def save(self, draft: PullRequestDraft) -> None: ...
    def get(self, draft_id: str) -> PullRequestDraft | None: ...
    def update(self, draft: PullRequestDraft) -> None: ...
    def list_by_project(self, project_id: str) -> list[PullRequestDraft]: ...
    def list_by_dev_task(self, dev_task_id: str) -> list[PullRequestDraft]: ...


class InMemoryPullRequestDraftRepository:
    def __init__(self) -> None:
        self._store: dict[str, PullRequestDraft] = {}

    def save(self, draft: PullRequestDraft) -> None:
        self._store[draft.id] = draft

    def get(self, draft_id: str) -> PullRequestDraft | None:
        return self._store.get(draft_id)

    def update(self, draft: PullRequestDraft) -> None:
        self._store[draft.id] = draft

    def list_by_project(self, project_id: str) -> list[PullRequestDraft]:
        matches = [d for d in self._store.values() if d.project_id == project_id]
        return sorted(matches, key=lambda d: d.created_at, reverse=True)

    def list_by_dev_task(self, dev_task_id: str) -> list[PullRequestDraft]:
        return [d for d in self._store.values() if d.dev_task_id == dev_task_id]

    def clear(self) -> None:
        self._store.clear()


class FirestorePullRequestDraftRepository:
    def __init__(self, client, collection_name: str = "pull_request_drafts") -> None:
        self._collection = client.collection(collection_name)

    def save(self, draft: PullRequestDraft) -> None:
        self._collection.document(draft.id).set(draft.model_dump(mode="python"))

    def get(self, draft_id: str) -> PullRequestDraft | None:
        snap = self._collection.document(draft_id).get()
        if not snap.exists:
            return None
        return PullRequestDraft(**snap.to_dict())

    def update(self, draft: PullRequestDraft) -> None:
        self._collection.document(draft.id).set(draft.model_dump(mode="python"))

    def list_by_project(self, project_id: str) -> list[PullRequestDraft]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        matches = [PullRequestDraft(**d.to_dict()) for d in docs]
        return sorted(matches, key=lambda d: d.created_at, reverse=True)

    def list_by_dev_task(self, dev_task_id: str) -> list[PullRequestDraft]:
        docs = self._collection.where("dev_task_id", "==", dev_task_id).stream()
        return [PullRequestDraft(**d.to_dict()) for d in docs]


class PullRequestReviewRepository(Protocol):
    def save(self, review: PullRequestReview) -> None: ...
    def get(self, review_id: str) -> PullRequestReview | None: ...
    def update(self, review: PullRequestReview) -> None: ...
    def list_by_pr_draft(self, pr_draft_id: str) -> list[PullRequestReview]: ...


class InMemoryPullRequestReviewRepository:
    def __init__(self) -> None:
        self._store: dict[str, PullRequestReview] = {}

    def save(self, review: PullRequestReview) -> None:
        self._store[review.id] = review

    def get(self, review_id: str) -> PullRequestReview | None:
        return self._store.get(review_id)

    def update(self, review: PullRequestReview) -> None:
        self._store[review.id] = review

    def list_by_pr_draft(self, pr_draft_id: str) -> list[PullRequestReview]:
        matches = [r for r in self._store.values() if r.pr_draft_id == pr_draft_id]
        return sorted(matches, key=lambda r: r.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestorePullRequestReviewRepository:
    def __init__(self, client, collection_name: str = "pull_request_reviews") -> None:
        self._collection = client.collection(collection_name)

    def save(self, review: PullRequestReview) -> None:
        self._collection.document(review.id).set(review.model_dump(mode="python"))

    def get(self, review_id: str) -> PullRequestReview | None:
        snap = self._collection.document(review_id).get()
        if not snap.exists:
            return None
        return PullRequestReview(**snap.to_dict())

    def update(self, review: PullRequestReview) -> None:
        self._collection.document(review.id).set(review.model_dump(mode="python"))

    def list_by_pr_draft(self, pr_draft_id: str) -> list[PullRequestReview]:
        docs = self._collection.where("pr_draft_id", "==", pr_draft_id).stream()
        matches = [PullRequestReview(**d.to_dict()) for d in docs]
        return sorted(matches, key=lambda r: r.created_at, reverse=True)


class CIEventRepository(Protocol):
    def save(self, event: CIEvent) -> None: ...
    def get(self, event_id: str) -> CIEvent | None: ...
    def list_by_project(self, project_id: str) -> list[CIEvent]: ...
    def list_by_pr_draft(self, pr_draft_id: str) -> list[CIEvent]: ...
    def list_by_dev_task(self, dev_task_id: str) -> list[CIEvent]: ...


class InMemoryCIEventRepository:
    def __init__(self) -> None:
        self._store: dict[str, CIEvent] = {}

    def save(self, event: CIEvent) -> None:
        self._store[event.id] = event

    def get(self, event_id: str) -> CIEvent | None:
        return self._store.get(event_id)

    def list_by_project(self, project_id: str) -> list[CIEvent]:
        matches = [e for e in self._store.values() if e.project_id == project_id]
        return sorted(matches, key=lambda e: e.created_at, reverse=True)

    def list_by_pr_draft(self, pr_draft_id: str) -> list[CIEvent]:
        matches = [e for e in self._store.values() if e.pr_draft_id == pr_draft_id]
        return sorted(matches, key=lambda e: e.created_at, reverse=True)

    def list_by_dev_task(self, dev_task_id: str) -> list[CIEvent]:
        matches = [e for e in self._store.values() if e.dev_task_id == dev_task_id]
        return sorted(matches, key=lambda e: e.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreCIEventRepository:
    def __init__(self, client, collection_name: str = "ci_events") -> None:
        self._collection = client.collection(collection_name)

    def save(self, event: CIEvent) -> None:
        self._collection.document(event.id).set(event.model_dump(mode="python"))

    def get(self, event_id: str) -> CIEvent | None:
        snap = self._collection.document(event_id).get()
        if not snap.exists:
            return None
        return CIEvent(**snap.to_dict())

    def list_by_project(self, project_id: str) -> list[CIEvent]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        matches = [CIEvent(**d.to_dict()) for d in docs]
        return sorted(matches, key=lambda e: e.created_at, reverse=True)

    def list_by_pr_draft(self, pr_draft_id: str) -> list[CIEvent]:
        docs = self._collection.where("pr_draft_id", "==", pr_draft_id).stream()
        matches = [CIEvent(**d.to_dict()) for d in docs]
        return sorted(matches, key=lambda e: e.created_at, reverse=True)

    def list_by_dev_task(self, dev_task_id: str) -> list[CIEvent]:
        docs = self._collection.where("dev_task_id", "==", dev_task_id).stream()
        matches = [CIEvent(**d.to_dict()) for d in docs]
        return sorted(matches, key=lambda e: e.created_at, reverse=True)


class CIAnalysisRepository(Protocol):
    def save(self, analysis: CIAnalysis) -> None: ...
    def get(self, analysis_id: str) -> CIAnalysis | None: ...
    def list_by_ci_event(self, ci_event_id: str) -> list[CIAnalysis]: ...


class InMemoryCIAnalysisRepository:
    def __init__(self) -> None:
        self._store: dict[str, CIAnalysis] = {}

    def save(self, analysis: CIAnalysis) -> None:
        self._store[analysis.id] = analysis

    def get(self, analysis_id: str) -> CIAnalysis | None:
        return self._store.get(analysis_id)

    def list_by_ci_event(self, ci_event_id: str) -> list[CIAnalysis]:
        matches = [a for a in self._store.values() if a.ci_event_id == ci_event_id]
        return sorted(matches, key=lambda a: a.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreCIAnalysisRepository:
    def __init__(self, client, collection_name: str = "ci_analyses") -> None:
        self._collection = client.collection(collection_name)

    def save(self, analysis: CIAnalysis) -> None:
        self._collection.document(analysis.id).set(analysis.model_dump(mode="python"))

    def get(self, analysis_id: str) -> CIAnalysis | None:
        snap = self._collection.document(analysis_id).get()
        if not snap.exists:
            return None
        return CIAnalysis(**snap.to_dict())

    def list_by_ci_event(self, ci_event_id: str) -> list[CIAnalysis]:
        docs = self._collection.where("ci_event_id", "==", ci_event_id).stream()
        matches = [CIAnalysis(**d.to_dict()) for d in docs]
        return sorted(matches, key=lambda a: a.created_at, reverse=True)


class IncidentRepository(Protocol):
    def save(self, incident: Incident) -> None: ...
    def get(self, incident_id: str) -> Incident | None: ...
    def list_by_project(self, project_id: str) -> list[Incident]: ...


class InMemoryIncidentRepository:
    def __init__(self) -> None:
        self._store: dict[str, Incident] = {}

    def save(self, incident: Incident) -> None:
        self._store[incident.id] = incident

    def get(self, incident_id: str) -> Incident | None:
        return self._store.get(incident_id)

    def list_by_project(self, project_id: str) -> list[Incident]:
        matches = [i for i in self._store.values() if i.project_id == project_id]
        return sorted(matches, key=lambda i: i.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreIncidentRepository:
    def __init__(self, client, collection_name: str = "incidents") -> None:
        self._collection = client.collection(collection_name)

    def save(self, incident: Incident) -> None:
        self._collection.document(incident.id).set(incident.model_dump(mode="python"))

    def get(self, incident_id: str) -> Incident | None:
        snap = self._collection.document(incident_id).get()
        if not snap.exists:
            return None
        return Incident(**snap.to_dict())

    def list_by_project(self, project_id: str) -> list[Incident]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        matches = [Incident(**d.to_dict()) for d in docs]
        return sorted(matches, key=lambda i: i.created_at, reverse=True)


class IncidentAnalysisRepository(Protocol):
    def save(self, analysis: IncidentAnalysis) -> None: ...
    def get(self, analysis_id: str) -> IncidentAnalysis | None: ...
    def list_by_incident(self, incident_id: str) -> list[IncidentAnalysis]: ...


class InMemoryIncidentAnalysisRepository:
    def __init__(self) -> None:
        self._store: dict[str, IncidentAnalysis] = {}

    def save(self, analysis: IncidentAnalysis) -> None:
        self._store[analysis.id] = analysis

    def get(self, analysis_id: str) -> IncidentAnalysis | None:
        return self._store.get(analysis_id)

    def list_by_incident(self, incident_id: str) -> list[IncidentAnalysis]:
        matches = [a for a in self._store.values() if a.incident_id == incident_id]
        return sorted(matches, key=lambda a: a.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreIncidentAnalysisRepository:
    def __init__(self, client, collection_name: str = "incident_analyses") -> None:
        self._collection = client.collection(collection_name)

    def save(self, analysis: IncidentAnalysis) -> None:
        self._collection.document(analysis.id).set(analysis.model_dump(mode="python"))

    def get(self, analysis_id: str) -> IncidentAnalysis | None:
        snap = self._collection.document(analysis_id).get()
        if not snap.exists:
            return None
        return IncidentAnalysis(**snap.to_dict())

    def list_by_incident(self, incident_id: str) -> list[IncidentAnalysis]:
        docs = self._collection.where("incident_id", "==", incident_id).stream()
        matches = [IncidentAnalysis(**d.to_dict()) for d in docs]
        return sorted(matches, key=lambda a: a.created_at, reverse=True)


class MemoryLearningRunRepository(Protocol):
    def save(self, run: MemoryLearningRun) -> None: ...
    def get(self, run_id: str) -> MemoryLearningRun | None: ...
    def list_by_project(self, project_id: str) -> list[MemoryLearningRun]: ...


class InMemoryMemoryLearningRunRepository:
    def __init__(self) -> None:
        self._store: dict[str, MemoryLearningRun] = {}

    def save(self, run: MemoryLearningRun) -> None:
        self._store[run.id] = run

    def get(self, run_id: str) -> MemoryLearningRun | None:
        return self._store.get(run_id)

    def list_by_project(self, project_id: str) -> list[MemoryLearningRun]:
        matches = [r for r in self._store.values() if r.project_id == project_id]
        return sorted(matches, key=lambda r: r.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreMemoryLearningRunRepository:
    def __init__(self, client, collection_name: str = "memory_learning_runs") -> None:
        self._collection = client.collection(collection_name)

    def save(self, run: MemoryLearningRun) -> None:
        self._collection.document(run.id).set(run.model_dump(mode="python"))

    def get(self, run_id: str) -> MemoryLearningRun | None:
        snap = self._collection.document(run_id).get()
        if not snap.exists:
            return None
        return MemoryLearningRun(**snap.to_dict())

    def list_by_project(self, project_id: str) -> list[MemoryLearningRun]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        matches = [MemoryLearningRun(**d.to_dict()) for d in docs]
        return sorted(matches, key=lambda r: r.created_at, reverse=True)


class ProjectMemoryCandidateRepository(Protocol):
    def save(self, candidate: ProjectMemoryCandidate) -> None: ...
    def get(self, candidate_id: str) -> ProjectMemoryCandidate | None: ...
    def list_by_project(self, project_id: str) -> list[ProjectMemoryCandidate]: ...
    def list_by_learning_run(self, learning_run_id: str) -> list[ProjectMemoryCandidate]: ...


class InMemoryProjectMemoryCandidateRepository:
    def __init__(self) -> None:
        self._store: dict[str, ProjectMemoryCandidate] = {}

    def save(self, candidate: ProjectMemoryCandidate) -> None:
        self._store[candidate.id] = candidate

    def get(self, candidate_id: str) -> ProjectMemoryCandidate | None:
        return self._store.get(candidate_id)

    def list_by_project(self, project_id: str) -> list[ProjectMemoryCandidate]:
        matches = [c for c in self._store.values() if c.project_id == project_id]
        return sorted(matches, key=lambda c: c.created_at, reverse=True)

    def list_by_learning_run(self, learning_run_id: str) -> list[ProjectMemoryCandidate]:
        matches = [c for c in self._store.values() if c.learning_run_id == learning_run_id]
        return sorted(matches, key=lambda c: c.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreProjectMemoryCandidateRepository:
    def __init__(self, client, collection_name: str = "project_memory_candidates") -> None:
        self._collection = client.collection(collection_name)

    def save(self, candidate: ProjectMemoryCandidate) -> None:
        self._collection.document(candidate.id).set(candidate.model_dump(mode="python"))

    def get(self, candidate_id: str) -> ProjectMemoryCandidate | None:
        snap = self._collection.document(candidate_id).get()
        if not snap.exists:
            return None
        return ProjectMemoryCandidate(**snap.to_dict())

    def list_by_project(self, project_id: str) -> list[ProjectMemoryCandidate]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        matches = [ProjectMemoryCandidate(**d.to_dict()) for d in docs]
        return sorted(matches, key=lambda c: c.created_at, reverse=True)

    def list_by_learning_run(self, learning_run_id: str) -> list[ProjectMemoryCandidate]:
        docs = self._collection.where("learning_run_id", "==", learning_run_id).stream()
        matches = [ProjectMemoryCandidate(**d.to_dict()) for d in docs]
        return sorted(matches, key=lambda c: c.created_at, reverse=True)


class WorkspaceRepository(Protocol):
    def save(self, workspace: Workspace) -> None: ...
    def get(self, workspace_id: str) -> Workspace | None: ...
    def update(self, workspace: Workspace) -> None: ...
    def list_by_project(self, project_id: str) -> list[Workspace]: ...
    def list_by_code_repository(self, code_repository_id: str) -> list[Workspace]: ...


class InMemoryWorkspaceRepository:
    def __init__(self) -> None:
        self._store: dict[str, Workspace] = {}

    def save(self, workspace: Workspace) -> None:
        self._store[workspace.id] = workspace

    def get(self, workspace_id: str) -> Workspace | None:
        return self._store.get(workspace_id)

    def update(self, workspace: Workspace) -> None:
        self._store[workspace.id] = workspace

    def list_by_project(self, project_id: str) -> list[Workspace]:
        return [w for w in self._store.values() if w.project_id == project_id]

    def list_by_code_repository(self, code_repository_id: str) -> list[Workspace]:
        return [w for w in self._store.values() if w.code_repository_id == code_repository_id]

    def clear(self) -> None:
        self._store.clear()


class FirestoreWorkspaceRepository:
    def __init__(self, client, collection_name: str = "workspaces") -> None:
        self._collection = client.collection(collection_name)

    def save(self, workspace: Workspace) -> None:
        self._collection.document(workspace.id).set(workspace.model_dump(mode="python"))

    def get(self, workspace_id: str) -> Workspace | None:
        snap = self._collection.document(workspace_id).get()
        if not snap.exists:
            return None
        return Workspace(**snap.to_dict())

    def update(self, workspace: Workspace) -> None:
        self._collection.document(workspace.id).set(workspace.model_dump(mode="python"))

    def list_by_project(self, project_id: str) -> list[Workspace]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        return [Workspace(**d.to_dict()) for d in docs]

    def list_by_code_repository(self, code_repository_id: str) -> list[Workspace]:
        docs = self._collection.where("code_repository_id", "==", code_repository_id).stream()
        return [Workspace(**d.to_dict()) for d in docs]


class CommandDefinitionRepository(Protocol):
    def save(self, definition: CommandDefinition) -> None: ...
    def get(self, definition_id: str) -> CommandDefinition | None: ...
    def update(self, definition: CommandDefinition) -> None: ...
    def list_by_project(self, project_id: str) -> list[CommandDefinition]: ...
    def list_by_workspace(self, workspace_id: str) -> list[CommandDefinition]: ...


class InMemoryCommandDefinitionRepository:
    def __init__(self) -> None:
        self._store: dict[str, CommandDefinition] = {}

    def save(self, definition: CommandDefinition) -> None:
        self._store[definition.id] = definition

    def get(self, definition_id: str) -> CommandDefinition | None:
        return self._store.get(definition_id)

    def update(self, definition: CommandDefinition) -> None:
        self._store[definition.id] = definition

    def list_by_project(self, project_id: str) -> list[CommandDefinition]:
        return [d for d in self._store.values() if d.project_id == project_id]

    def list_by_workspace(self, workspace_id: str) -> list[CommandDefinition]:
        return [d for d in self._store.values() if d.workspace_id == workspace_id]

    def clear(self) -> None:
        self._store.clear()


class FirestoreCommandDefinitionRepository:
    def __init__(self, client, collection_name: str = "command_definitions") -> None:
        self._collection = client.collection(collection_name)

    def save(self, definition: CommandDefinition) -> None:
        self._collection.document(definition.id).set(definition.model_dump(mode="python"))

    def get(self, definition_id: str) -> CommandDefinition | None:
        snap = self._collection.document(definition_id).get()
        if not snap.exists:
            return None
        return CommandDefinition(**snap.to_dict())

    def update(self, definition: CommandDefinition) -> None:
        self._collection.document(definition.id).set(definition.model_dump(mode="python"))

    def list_by_project(self, project_id: str) -> list[CommandDefinition]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        return [CommandDefinition(**d.to_dict()) for d in docs]

    def list_by_workspace(self, workspace_id: str) -> list[CommandDefinition]:
        docs = self._collection.where("workspace_id", "==", workspace_id).stream()
        return [CommandDefinition(**d.to_dict()) for d in docs]


class CommandRunRepository(Protocol):
    def save(self, run: CommandRun) -> None: ...
    def get(self, run_id: str) -> CommandRun | None: ...
    def update(self, run: CommandRun) -> None: ...
    def list_by_project(self, project_id: str) -> list[CommandRun]: ...
    def list_by_workspace(self, workspace_id: str) -> list[CommandRun]: ...
    def list_by_target(self, target_type: str, target_id: str) -> list[CommandRun]: ...


class InMemoryCommandRunRepository:
    def __init__(self) -> None:
        self._store: dict[str, CommandRun] = {}

    def save(self, run: CommandRun) -> None:
        self._store[run.id] = run

    def get(self, run_id: str) -> CommandRun | None:
        return self._store.get(run_id)

    def update(self, run: CommandRun) -> None:
        self._store[run.id] = run

    def list_by_project(self, project_id: str) -> list[CommandRun]:
        return [r for r in self._store.values() if r.project_id == project_id]

    def list_by_workspace(self, workspace_id: str) -> list[CommandRun]:
        return [r for r in self._store.values() if r.workspace_id == workspace_id]

    def list_by_target(self, target_type: str, target_id: str) -> list[CommandRun]:
        return [
            r
            for r in self._store.values()
            if r.target_type == target_type and r.target_id == target_id
        ]

    def clear(self) -> None:
        self._store.clear()


class FirestoreCommandRunRepository:
    def __init__(self, client, collection_name: str = "command_runs") -> None:
        self._collection = client.collection(collection_name)

    def save(self, run: CommandRun) -> None:
        self._collection.document(run.id).set(run.model_dump(mode="python"))

    def get(self, run_id: str) -> CommandRun | None:
        snap = self._collection.document(run_id).get()
        if not snap.exists:
            return None
        return CommandRun(**snap.to_dict())

    def update(self, run: CommandRun) -> None:
        self._collection.document(run.id).set(run.model_dump(mode="python"))

    def list_by_project(self, project_id: str) -> list[CommandRun]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        return [CommandRun(**d.to_dict()) for d in docs]

    def list_by_workspace(self, workspace_id: str) -> list[CommandRun]:
        docs = self._collection.where("workspace_id", "==", workspace_id).stream()
        return [CommandRun(**d.to_dict()) for d in docs]

    def list_by_target(self, target_type: str, target_id: str) -> list[CommandRun]:
        docs = (
            self._collection.where("target_type", "==", target_type)
            .where("target_id", "==", target_id)
            .stream()
        )
        return [CommandRun(**d.to_dict()) for d in docs]


class WorkspaceBranchRepository(Protocol):
    def save(self, branch: WorkspaceBranch) -> None: ...
    def get(self, branch_id: str) -> WorkspaceBranch | None: ...
    def update(self, branch: WorkspaceBranch) -> None: ...
    def list_by_workspace(self, workspace_id: str) -> list[WorkspaceBranch]: ...
    def list_by_project(self, project_id: str) -> list[WorkspaceBranch]: ...


class InMemoryWorkspaceBranchRepository:
    def __init__(self) -> None:
        self._store: dict[str, WorkspaceBranch] = {}

    def save(self, branch: WorkspaceBranch) -> None:
        self._store[branch.id] = branch

    def get(self, branch_id: str) -> WorkspaceBranch | None:
        return self._store.get(branch_id)

    def update(self, branch: WorkspaceBranch) -> None:
        self._store[branch.id] = branch

    def list_by_workspace(self, workspace_id: str) -> list[WorkspaceBranch]:
        return [b for b in self._store.values() if b.workspace_id == workspace_id]

    def list_by_project(self, project_id: str) -> list[WorkspaceBranch]:
        return [b for b in self._store.values() if b.project_id == project_id]

    def clear(self) -> None:
        self._store.clear()


class FirestoreWorkspaceBranchRepository:
    def __init__(self, client, collection_name: str = "workspace_branches") -> None:
        self._collection = client.collection(collection_name)

    def save(self, branch: WorkspaceBranch) -> None:
        self._collection.document(branch.id).set(branch.model_dump(mode="python"))

    def get(self, branch_id: str) -> WorkspaceBranch | None:
        snap = self._collection.document(branch_id).get()
        if not snap.exists:
            return None
        return WorkspaceBranch(**snap.to_dict())

    def update(self, branch: WorkspaceBranch) -> None:
        self._collection.document(branch.id).set(branch.model_dump(mode="python"))

    def list_by_workspace(self, workspace_id: str) -> list[WorkspaceBranch]:
        docs = self._collection.where("workspace_id", "==", workspace_id).stream()
        return [WorkspaceBranch(**d.to_dict()) for d in docs]

    def list_by_project(self, project_id: str) -> list[WorkspaceBranch]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        return [WorkspaceBranch(**d.to_dict()) for d in docs]


class GitCommitRecordRepository(Protocol):
    def save(self, record: GitCommitRecord) -> None: ...
    def get(self, record_id: str) -> GitCommitRecord | None: ...
    def update(self, record: GitCommitRecord) -> None: ...
    def list_by_branch(self, branch_id: str) -> list[GitCommitRecord]: ...
    def list_by_workspace(self, workspace_id: str) -> list[GitCommitRecord]: ...


class InMemoryGitCommitRecordRepository:
    def __init__(self) -> None:
        self._store: dict[str, GitCommitRecord] = {}

    def save(self, record: GitCommitRecord) -> None:
        self._store[record.id] = record

    def get(self, record_id: str) -> GitCommitRecord | None:
        return self._store.get(record_id)

    def update(self, record: GitCommitRecord) -> None:
        self._store[record.id] = record

    def list_by_branch(self, branch_id: str) -> list[GitCommitRecord]:
        return [r for r in self._store.values() if r.workspace_branch_id == branch_id]

    def list_by_workspace(self, workspace_id: str) -> list[GitCommitRecord]:
        return [r for r in self._store.values() if r.workspace_id == workspace_id]

    def clear(self) -> None:
        self._store.clear()


class FirestoreGitCommitRecordRepository:
    def __init__(self, client, collection_name: str = "git_commit_records") -> None:
        self._collection = client.collection(collection_name)

    def save(self, record: GitCommitRecord) -> None:
        self._collection.document(record.id).set(record.model_dump(mode="python"))

    def get(self, record_id: str) -> GitCommitRecord | None:
        snap = self._collection.document(record_id).get()
        if not snap.exists:
            return None
        return GitCommitRecord(**snap.to_dict())

    def update(self, record: GitCommitRecord) -> None:
        self._collection.document(record.id).set(record.model_dump(mode="python"))

    def list_by_branch(self, branch_id: str) -> list[GitCommitRecord]:
        docs = self._collection.where("workspace_branch_id", "==", branch_id).stream()
        return [GitCommitRecord(**d.to_dict()) for d in docs]

    def list_by_workspace(self, workspace_id: str) -> list[GitCommitRecord]:
        docs = self._collection.where("workspace_id", "==", workspace_id).stream()
        return [GitCommitRecord(**d.to_dict()) for d in docs]


class ReviewFeedbackRepository(Protocol):
    def save(self, feedback: ReviewFeedback) -> None: ...
    def get(self, feedback_id: str) -> ReviewFeedback | None: ...
    def update(self, feedback: ReviewFeedback) -> None: ...
    def list_by_pr_draft(self, pr_draft_id: str) -> list[ReviewFeedback]: ...
    def list_by_pr_review(self, pr_review_id: str) -> list[ReviewFeedback]: ...
    def list_by_project(self, project_id: str) -> list[ReviewFeedback]: ...


class InMemoryReviewFeedbackRepository:
    def __init__(self) -> None:
        self._store: dict[str, ReviewFeedback] = {}

    def save(self, feedback: ReviewFeedback) -> None:
        self._store[feedback.id] = feedback

    def get(self, feedback_id: str) -> ReviewFeedback | None:
        return self._store.get(feedback_id)

    def update(self, feedback: ReviewFeedback) -> None:
        self._store[feedback.id] = feedback

    def list_by_pr_draft(self, pr_draft_id: str) -> list[ReviewFeedback]:
        items = [f for f in self._store.values() if f.pr_draft_id == pr_draft_id]
        return sorted(items, key=lambda f: f.created_at, reverse=True)

    def list_by_pr_review(self, pr_review_id: str) -> list[ReviewFeedback]:
        items = [f for f in self._store.values() if f.pr_review_id == pr_review_id]
        return sorted(items, key=lambda f: f.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[ReviewFeedback]:
        items = [f for f in self._store.values() if f.project_id == project_id]
        return sorted(items, key=lambda f: f.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreReviewFeedbackRepository:
    def __init__(self, client, collection_name: str = "review_feedback") -> None:
        self._collection = client.collection(collection_name)

    def save(self, feedback: ReviewFeedback) -> None:
        self._collection.document(feedback.id).set(feedback.model_dump(mode="python"))

    def get(self, feedback_id: str) -> ReviewFeedback | None:
        snap = self._collection.document(feedback_id).get()
        if not snap.exists:
            return None
        return ReviewFeedback(**snap.to_dict())

    def update(self, feedback: ReviewFeedback) -> None:
        self._collection.document(feedback.id).set(feedback.model_dump(mode="python"))

    def list_by_pr_draft(self, pr_draft_id: str) -> list[ReviewFeedback]:
        docs = self._collection.where("pr_draft_id", "==", pr_draft_id).stream()
        items = [ReviewFeedback(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda f: f.created_at, reverse=True)

    def list_by_pr_review(self, pr_review_id: str) -> list[ReviewFeedback]:
        docs = self._collection.where("pr_review_id", "==", pr_review_id).stream()
        items = [ReviewFeedback(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda f: f.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[ReviewFeedback]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        items = [ReviewFeedback(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda f: f.created_at, reverse=True)


class RevisionWorkItemRepository(Protocol):
    def save(self, item: RevisionWorkItem) -> None: ...
    def get(self, item_id: str) -> RevisionWorkItem | None: ...
    def update(self, item: RevisionWorkItem) -> None: ...
    def list_by_pr_draft(self, pr_draft_id: str) -> list[RevisionWorkItem]: ...
    def list_by_feedback(self, feedback_id: str) -> list[RevisionWorkItem]: ...
    def list_by_project(self, project_id: str) -> list[RevisionWorkItem]: ...


class InMemoryRevisionWorkItemRepository:
    def __init__(self) -> None:
        self._store: dict[str, RevisionWorkItem] = {}

    def save(self, item: RevisionWorkItem) -> None:
        self._store[item.id] = item

    def get(self, item_id: str) -> RevisionWorkItem | None:
        return self._store.get(item_id)

    def update(self, item: RevisionWorkItem) -> None:
        self._store[item.id] = item

    def list_by_pr_draft(self, pr_draft_id: str) -> list[RevisionWorkItem]:
        items = [r for r in self._store.values() if r.pr_draft_id == pr_draft_id]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def list_by_feedback(self, feedback_id: str) -> list[RevisionWorkItem]:
        items = [r for r in self._store.values() if r.review_feedback_id == feedback_id]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[RevisionWorkItem]:
        items = [r for r in self._store.values() if r.project_id == project_id]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreRevisionWorkItemRepository:
    def __init__(self, client, collection_name: str = "revision_work_items") -> None:
        self._collection = client.collection(collection_name)

    def save(self, item: RevisionWorkItem) -> None:
        self._collection.document(item.id).set(item.model_dump(mode="python"))

    def get(self, item_id: str) -> RevisionWorkItem | None:
        snap = self._collection.document(item_id).get()
        if not snap.exists:
            return None
        return RevisionWorkItem(**snap.to_dict())

    def update(self, item: RevisionWorkItem) -> None:
        self._collection.document(item.id).set(item.model_dump(mode="python"))

    def list_by_pr_draft(self, pr_draft_id: str) -> list[RevisionWorkItem]:
        docs = self._collection.where("pr_draft_id", "==", pr_draft_id).stream()
        items = [RevisionWorkItem(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def list_by_feedback(self, feedback_id: str) -> list[RevisionWorkItem]:
        docs = self._collection.where("review_feedback_id", "==", feedback_id).stream()
        items = [RevisionWorkItem(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[RevisionWorkItem]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        items = [RevisionWorkItem(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda r: r.created_at, reverse=True)


@dataclass(frozen=True)
class Repositories:
    """Named container for the wired-up repository singletons.

    Replaces the previous 26-element positional tuple returned by
    ``get_repositories()``. Field names mirror the singleton names used in
    ``repositories_state.py`` with the ``_repo`` suffix stripped.
    """

    def reset_all(self) -> None:
        """Clear every in-memory repository. Only intended for test isolation."""
        for f in dataclasses.fields(self):
            r = getattr(self, f.name)
            if callable(getattr(r, "clear", None)):
                r.clear()

    ticket: TicketRepository
    agent_run: AgentRunRepository
    artifact: ArtifactRepository
    project: ProjectRepository
    project_context: ProjectContextRepository
    requirement_analysis: RequirementAnalysisRepository
    requirement: RequirementRepository
    dev_task: DevTaskRepository
    subtask: SubtaskRepository
    approval: ApprovalRepository
    audit_event: AuditEventRepository
    code_repository: CodeRepositoryRepository
    repo_safety_profile: RepoSafetyProfileRepository
    epic: EpicRepository
    check_definition: CheckDefinitionRepository
    check_run: CheckRunRepository
    tool_runner_definition: ToolRunnerDefinitionRepository
    tool_run: ToolRunRepository
    pr_draft: PullRequestDraftRepository
    pr_review: PullRequestReviewRepository
    ci_event: CIEventRepository
    ci_analysis: CIAnalysisRepository
    incident: IncidentRepository
    incident_analysis: IncidentAnalysisRepository
    memory_learning_run: MemoryLearningRunRepository
    memory_candidate: ProjectMemoryCandidateRepository
    workspace: WorkspaceRepository
    command_definition: CommandDefinitionRepository
    command_run: CommandRunRepository
    workspace_branch: WorkspaceBranchRepository
    git_commit_record: GitCommitRecordRepository
    review_feedback: ReviewFeedbackRepository
    revision_work_item: RevisionWorkItemRepository


def get_repositories() -> Repositories:
    if config.REPOSITORY_PROVIDER == "memory":
        return Repositories(
            ticket=InMemoryTicketRepository(),
            agent_run=InMemoryAgentRunRepository(),
            artifact=InMemoryArtifactRepository(),
            project=InMemoryProjectRepository(),
            project_context=InMemoryProjectContextRepository(),
            requirement_analysis=InMemoryRequirementAnalysisRepository(),
            requirement=InMemoryRequirementRepository(),
            dev_task=InMemoryDevTaskRepository(),
            subtask=InMemorySubtaskRepository(),
            approval=InMemoryApprovalRepository(),
            audit_event=InMemoryAuditEventRepository(),
            code_repository=InMemoryCodeRepositoryRepository(),
            repo_safety_profile=InMemoryRepoSafetyProfileRepository(),
            epic=InMemoryEpicRepository(),
            check_definition=InMemoryCheckDefinitionRepository(),
            check_run=InMemoryCheckRunRepository(),
            tool_runner_definition=InMemoryToolRunnerDefinitionRepository(),
            tool_run=InMemoryToolRunRepository(),
            pr_draft=InMemoryPullRequestDraftRepository(),
            pr_review=InMemoryPullRequestReviewRepository(),
            ci_event=InMemoryCIEventRepository(),
            ci_analysis=InMemoryCIAnalysisRepository(),
            incident=InMemoryIncidentRepository(),
            incident_analysis=InMemoryIncidentAnalysisRepository(),
            memory_learning_run=InMemoryMemoryLearningRunRepository(),
            memory_candidate=InMemoryProjectMemoryCandidateRepository(),
            workspace=InMemoryWorkspaceRepository(),
            command_definition=InMemoryCommandDefinitionRepository(),
            command_run=InMemoryCommandRunRepository(),
            workspace_branch=InMemoryWorkspaceBranchRepository(),
            git_commit_record=InMemoryGitCommitRecordRepository(),
            review_feedback=InMemoryReviewFeedbackRepository(),
            revision_work_item=InMemoryRevisionWorkItemRepository(),
        )
    if config.REPOSITORY_PROVIDER == "firestore":
        from google.cloud import firestore

        client = firestore.Client(
            project=config.GCP_PROJECT_ID or None,
            database=config.FIRESTORE_DATABASE,
        )
        return Repositories(
            ticket=FirestoreTicketRepository(client),
            agent_run=FirestoreAgentRunRepository(client),
            artifact=FirestoreArtifactRepository(client),
            project=FirestoreProjectRepository(client),
            project_context=FirestoreProjectContextRepository(client),
            requirement_analysis=FirestoreRequirementAnalysisRepository(client),
            requirement=FirestoreRequirementRepository(client),
            dev_task=FirestoreDevTaskRepository(client),
            subtask=FirestoreSubtaskRepository(client),
            approval=FirestoreApprovalRepository(client),
            audit_event=FirestoreAuditEventRepository(client),
            code_repository=FirestoreCodeRepositoryRepository(client),
            repo_safety_profile=FirestoreRepoSafetyProfileRepository(client),
            epic=FirestoreEpicRepository(client),
            check_definition=FirestoreCheckDefinitionRepository(client),
            check_run=FirestoreCheckRunRepository(client),
            tool_runner_definition=FirestoreToolRunnerDefinitionRepository(client),
            tool_run=FirestoreToolRunRepository(client),
            pr_draft=FirestorePullRequestDraftRepository(client),
            pr_review=FirestorePullRequestReviewRepository(client),
            ci_event=FirestoreCIEventRepository(client),
            ci_analysis=FirestoreCIAnalysisRepository(client),
            incident=FirestoreIncidentRepository(client),
            incident_analysis=FirestoreIncidentAnalysisRepository(client),
            memory_learning_run=FirestoreMemoryLearningRunRepository(client),
            memory_candidate=FirestoreProjectMemoryCandidateRepository(client),
            workspace=FirestoreWorkspaceRepository(client),
            command_definition=FirestoreCommandDefinitionRepository(client),
            command_run=FirestoreCommandRunRepository(client),
            workspace_branch=FirestoreWorkspaceBranchRepository(client),
            git_commit_record=FirestoreGitCommitRecordRepository(client),
            review_feedback=FirestoreReviewFeedbackRepository(client),
            revision_work_item=FirestoreRevisionWorkItemRepository(client),
        )
    raise ValueError(
        f"Unknown REPOSITORY_PROVIDER: {config.REPOSITORY_PROVIDER!r}. Supported: memory, firestore"
    )
