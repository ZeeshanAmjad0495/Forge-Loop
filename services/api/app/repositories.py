import dataclasses
from dataclasses import dataclass
from typing import Protocol

from . import config
from .models import (
    AgentFailureRecord,
    AgentRun,
    BenchmarkRun,
    BenchmarkRunResult,
    BenchmarkScenario,
    Approval,
    ArchitectureDecisionRecord,
    ArchitectureReview,
    AuditEvent,
    Artifact,
    ArtifactSummary,
    BudgetPolicy,
    CheckDefinition,
    CheckRun,
    CIAnalysis,
    CIEvent,
    CodeRepository,
    CommandDefinition,
    CommandRun,
    ContextPack,
    CostRecord,
    DevTask,
    Epic,
    ExperimentPlan,
    ExperimentRun,
    ImprovementProposal,
    GitCommitRecord,
    Incident,
    IncidentAnalysis,
    MemoryLearningRun,
    Project,
    ProjectBuildTrial,
    ProjectPack,
    ProjectRetrospective,
    ProjectTemplate,
    ProjectBuildTrialStage,
    PromptContextCacheEntry,
    QualityMetricSnapshot,
    ProjectMemoryCandidate,
    ProjectContext,
    PullRequestDraft,
    PullRequestReview,
    Requirement,
    RequirementAnalysis,
    RepoSafetyProfile,
    ResearchBrief,
    ResearchSource,
    ReviewFeedback,
    RevisionWorkItem,
    Subtask,
    SwarmPolicy,
    Ticket,
    ToolRun,
    ToolRunnerDefinition,
    AuditExportRequest,
    BackupExport,
    BackupImport,
    WorkflowTemplate,
    WorkSafePolicy,
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
    def find_approved_for_target(
        self, target_type: str, target_id: str,
        project_id: str | None = None,
    ) -> Approval | None: ...


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

    def find_approved_for_target(
        self, target_type: str, target_id: str,
        project_id: str | None = None,
    ) -> Approval | None:
        for a in self._store.values():
            if (
                a.target_type == target_type
                and a.target_id == target_id
                and a.status == "approved"
                and (project_id is None or a.project_id == project_id)
            ):
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

    def find_approved_for_target(
        self, target_type: str, target_id: str,
        project_id: str | None = None,
    ) -> Approval | None:
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
            appr = Approval(**d.to_dict())
            if project_id is None or appr.project_id == project_id:
                return appr
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


class BenchmarkScenarioRepository(Protocol):
    def save(self, scenario: BenchmarkScenario) -> None: ...
    def get(self, scenario_id: str) -> BenchmarkScenario | None: ...
    def update(self, scenario: BenchmarkScenario) -> None: ...
    def list_all(self) -> list[BenchmarkScenario]: ...
    def list_by_project(self, project_id: str) -> list[BenchmarkScenario]: ...


class InMemoryBenchmarkScenarioRepository:
    def __init__(self) -> None:
        self._store: dict[str, BenchmarkScenario] = {}

    def save(self, scenario: BenchmarkScenario) -> None:
        self._store[scenario.id] = scenario

    def get(self, scenario_id: str) -> BenchmarkScenario | None:
        return self._store.get(scenario_id)

    def update(self, scenario: BenchmarkScenario) -> None:
        self._store[scenario.id] = scenario

    def list_all(self) -> list[BenchmarkScenario]:
        return sorted(self._store.values(), key=lambda s: s.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[BenchmarkScenario]:
        items = [s for s in self._store.values() if s.project_id == project_id]
        return sorted(items, key=lambda s: s.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreBenchmarkScenarioRepository:
    def __init__(self, client, collection_name: str = "benchmark_scenarios") -> None:
        self._collection = client.collection(collection_name)

    def save(self, scenario: BenchmarkScenario) -> None:
        self._collection.document(scenario.id).set(scenario.model_dump(mode="python"))

    def get(self, scenario_id: str) -> BenchmarkScenario | None:
        snap = self._collection.document(scenario_id).get()
        if not snap.exists:
            return None
        return BenchmarkScenario(**snap.to_dict())

    def update(self, scenario: BenchmarkScenario) -> None:
        self._collection.document(scenario.id).set(scenario.model_dump(mode="python"))

    def list_all(self) -> list[BenchmarkScenario]:
        items = [BenchmarkScenario(**d.to_dict()) for d in self._collection.stream()]
        return sorted(items, key=lambda s: s.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[BenchmarkScenario]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        items = [BenchmarkScenario(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda s: s.created_at, reverse=True)


class BenchmarkRunRepository(Protocol):
    def save(self, run: BenchmarkRun) -> None: ...
    def get(self, run_id: str) -> BenchmarkRun | None: ...
    def update(self, run: BenchmarkRun) -> None: ...
    def list_by_scenario(self, scenario_id: str) -> list[BenchmarkRun]: ...
    def list_by_project(self, project_id: str) -> list[BenchmarkRun]: ...


class InMemoryBenchmarkRunRepository:
    def __init__(self) -> None:
        self._store: dict[str, BenchmarkRun] = {}

    def save(self, run: BenchmarkRun) -> None:
        self._store[run.id] = run

    def get(self, run_id: str) -> BenchmarkRun | None:
        return self._store.get(run_id)

    def update(self, run: BenchmarkRun) -> None:
        self._store[run.id] = run

    def list_by_scenario(self, scenario_id: str) -> list[BenchmarkRun]:
        items = [r for r in self._store.values() if r.scenario_id == scenario_id]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[BenchmarkRun]:
        items = [r for r in self._store.values() if r.project_id == project_id]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreBenchmarkRunRepository:
    def __init__(self, client, collection_name: str = "benchmark_runs") -> None:
        self._collection = client.collection(collection_name)

    def save(self, run: BenchmarkRun) -> None:
        self._collection.document(run.id).set(run.model_dump(mode="python"))

    def get(self, run_id: str) -> BenchmarkRun | None:
        snap = self._collection.document(run_id).get()
        if not snap.exists:
            return None
        return BenchmarkRun(**snap.to_dict())

    def update(self, run: BenchmarkRun) -> None:
        self._collection.document(run.id).set(run.model_dump(mode="python"))

    def list_by_scenario(self, scenario_id: str) -> list[BenchmarkRun]:
        docs = self._collection.where("scenario_id", "==", scenario_id).stream()
        items = [BenchmarkRun(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[BenchmarkRun]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        items = [BenchmarkRun(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda r: r.created_at, reverse=True)


class BenchmarkRunResultRepository(Protocol):
    def save(self, result: BenchmarkRunResult) -> None: ...
    def get(self, result_id: str) -> BenchmarkRunResult | None: ...
    def list_by_run(self, benchmark_run_id: str) -> list[BenchmarkRunResult]: ...


class InMemoryBenchmarkRunResultRepository:
    def __init__(self) -> None:
        self._store: dict[str, BenchmarkRunResult] = {}

    def save(self, result: BenchmarkRunResult) -> None:
        self._store[result.id] = result

    def get(self, result_id: str) -> BenchmarkRunResult | None:
        return self._store.get(result_id)

    def list_by_run(self, benchmark_run_id: str) -> list[BenchmarkRunResult]:
        items = [
            r for r in self._store.values() if r.benchmark_run_id == benchmark_run_id
        ]
        return sorted(items, key=lambda r: r.created_at)

    def clear(self) -> None:
        self._store.clear()


class FirestoreBenchmarkRunResultRepository:
    def __init__(
        self, client, collection_name: str = "benchmark_run_results"
    ) -> None:
        self._collection = client.collection(collection_name)

    def save(self, result: BenchmarkRunResult) -> None:
        self._collection.document(result.id).set(result.model_dump(mode="python"))

    def get(self, result_id: str) -> BenchmarkRunResult | None:
        snap = self._collection.document(result_id).get()
        if not snap.exists:
            return None
        return BenchmarkRunResult(**snap.to_dict())

    def list_by_run(self, benchmark_run_id: str) -> list[BenchmarkRunResult]:
        docs = (
            self._collection.where("benchmark_run_id", "==", benchmark_run_id).stream()
        )
        items = [BenchmarkRunResult(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda r: r.created_at)


class AgentFailureRecordRepository(Protocol):
    def save(self, record: AgentFailureRecord) -> None: ...
    def get(self, record_id: str) -> AgentFailureRecord | None: ...
    def update(self, record: AgentFailureRecord) -> None: ...
    def list_by_project(self, project_id: str) -> list[AgentFailureRecord]: ...
    def list_by_source(
        self, source_type: str, source_id: str
    ) -> list[AgentFailureRecord]: ...
    def list_by_trial(self, trial_id: str) -> list[AgentFailureRecord]: ...


class InMemoryAgentFailureRecordRepository:
    def __init__(self) -> None:
        self._store: dict[str, AgentFailureRecord] = {}

    def save(self, record: AgentFailureRecord) -> None:
        self._store[record.id] = record

    def get(self, record_id: str) -> AgentFailureRecord | None:
        return self._store.get(record_id)

    def update(self, record: AgentFailureRecord) -> None:
        self._store[record.id] = record

    def list_by_project(self, project_id: str) -> list[AgentFailureRecord]:
        items = [r for r in self._store.values() if r.project_id == project_id]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def list_by_source(
        self, source_type: str, source_id: str
    ) -> list[AgentFailureRecord]:
        items = [
            r
            for r in self._store.values()
            if r.source_type == source_type and r.source_id == source_id
        ]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def list_by_trial(self, trial_id: str) -> list[AgentFailureRecord]:
        items = [r for r in self._store.values() if r.trial_id == trial_id]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreAgentFailureRecordRepository:
    def __init__(self, client, collection_name: str = "agent_failure_records") -> None:
        self._collection = client.collection(collection_name)

    def save(self, record: AgentFailureRecord) -> None:
        self._collection.document(record.id).set(record.model_dump(mode="python"))

    def get(self, record_id: str) -> AgentFailureRecord | None:
        snap = self._collection.document(record_id).get()
        if not snap.exists:
            return None
        return AgentFailureRecord(**snap.to_dict())

    def update(self, record: AgentFailureRecord) -> None:
        self._collection.document(record.id).set(record.model_dump(mode="python"))

    def list_by_project(self, project_id: str) -> list[AgentFailureRecord]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        items = [AgentFailureRecord(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def list_by_source(
        self, source_type: str, source_id: str
    ) -> list[AgentFailureRecord]:
        docs = (
            self._collection.where("source_type", "==", source_type)
            .where("source_id", "==", source_id)
            .stream()
        )
        items = [AgentFailureRecord(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def list_by_trial(self, trial_id: str) -> list[AgentFailureRecord]:
        docs = self._collection.where("trial_id", "==", trial_id).stream()
        items = [AgentFailureRecord(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda r: r.created_at, reverse=True)


class QualityMetricSnapshotRepository(Protocol):
    def save(self, snapshot: QualityMetricSnapshot) -> None: ...
    def get(self, snapshot_id: str) -> QualityMetricSnapshot | None: ...
    def list_by_project(self, project_id: str) -> list[QualityMetricSnapshot]: ...
    def list_by_trial(self, trial_id: str) -> list[QualityMetricSnapshot]: ...


class InMemoryQualityMetricSnapshotRepository:
    def __init__(self) -> None:
        self._store: dict[str, QualityMetricSnapshot] = {}

    def save(self, snapshot: QualityMetricSnapshot) -> None:
        self._store[snapshot.id] = snapshot

    def get(self, snapshot_id: str) -> QualityMetricSnapshot | None:
        return self._store.get(snapshot_id)

    def list_by_project(self, project_id: str) -> list[QualityMetricSnapshot]:
        items = [s for s in self._store.values() if s.project_id == project_id]
        return sorted(items, key=lambda s: s.created_at, reverse=True)

    def list_by_trial(self, trial_id: str) -> list[QualityMetricSnapshot]:
        items = [s for s in self._store.values() if s.trial_id == trial_id]
        return sorted(items, key=lambda s: s.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreQualityMetricSnapshotRepository:
    def __init__(
        self, client, collection_name: str = "quality_metric_snapshots"
    ) -> None:
        self._collection = client.collection(collection_name)

    def save(self, snapshot: QualityMetricSnapshot) -> None:
        self._collection.document(snapshot.id).set(snapshot.model_dump(mode="python"))

    def get(self, snapshot_id: str) -> QualityMetricSnapshot | None:
        snap = self._collection.document(snapshot_id).get()
        if not snap.exists:
            return None
        return QualityMetricSnapshot(**snap.to_dict())

    def list_by_project(self, project_id: str) -> list[QualityMetricSnapshot]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        items = [QualityMetricSnapshot(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda s: s.created_at, reverse=True)

    def list_by_trial(self, trial_id: str) -> list[QualityMetricSnapshot]:
        docs = self._collection.where("trial_id", "==", trial_id).stream()
        items = [QualityMetricSnapshot(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda s: s.created_at, reverse=True)


class ProjectBuildTrialRepository(Protocol):
    def save(self, trial: ProjectBuildTrial) -> None: ...
    def get(self, trial_id: str) -> ProjectBuildTrial | None: ...
    def update(self, trial: ProjectBuildTrial) -> None: ...
    def list_by_project(self, project_id: str) -> list[ProjectBuildTrial]: ...


class InMemoryProjectBuildTrialRepository:
    def __init__(self) -> None:
        self._store: dict[str, ProjectBuildTrial] = {}

    def save(self, trial: ProjectBuildTrial) -> None:
        self._store[trial.id] = trial

    def get(self, trial_id: str) -> ProjectBuildTrial | None:
        return self._store.get(trial_id)

    def update(self, trial: ProjectBuildTrial) -> None:
        self._store[trial.id] = trial

    def list_by_project(self, project_id: str) -> list[ProjectBuildTrial]:
        items = [t for t in self._store.values() if t.project_id == project_id]
        return sorted(items, key=lambda t: t.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreProjectBuildTrialRepository:
    def __init__(self, client, collection_name: str = "project_build_trials") -> None:
        self._collection = client.collection(collection_name)

    def save(self, trial: ProjectBuildTrial) -> None:
        self._collection.document(trial.id).set(trial.model_dump(mode="python"))

    def get(self, trial_id: str) -> ProjectBuildTrial | None:
        snap = self._collection.document(trial_id).get()
        if not snap.exists:
            return None
        return ProjectBuildTrial(**snap.to_dict())

    def update(self, trial: ProjectBuildTrial) -> None:
        self._collection.document(trial.id).set(trial.model_dump(mode="python"))

    def list_by_project(self, project_id: str) -> list[ProjectBuildTrial]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        items = [ProjectBuildTrial(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda t: t.created_at, reverse=True)


class ProjectBuildTrialStageRepository(Protocol):
    def save(self, stage: ProjectBuildTrialStage) -> None: ...
    def get(self, stage_id: str) -> ProjectBuildTrialStage | None: ...
    def update(self, stage: ProjectBuildTrialStage) -> None: ...
    def list_by_trial(self, trial_id: str) -> list[ProjectBuildTrialStage]: ...


class InMemoryProjectBuildTrialStageRepository:
    def __init__(self) -> None:
        self._store: dict[str, ProjectBuildTrialStage] = {}

    def save(self, stage: ProjectBuildTrialStage) -> None:
        self._store[stage.id] = stage

    def get(self, stage_id: str) -> ProjectBuildTrialStage | None:
        return self._store.get(stage_id)

    def update(self, stage: ProjectBuildTrialStage) -> None:
        self._store[stage.id] = stage

    def list_by_trial(self, trial_id: str) -> list[ProjectBuildTrialStage]:
        items = [s for s in self._store.values() if s.trial_id == trial_id]
        return sorted(items, key=lambda s: s.created_at)

    def clear(self) -> None:
        self._store.clear()


class FirestoreProjectBuildTrialStageRepository:
    def __init__(
        self, client, collection_name: str = "project_build_trial_stages"
    ) -> None:
        self._collection = client.collection(collection_name)

    def save(self, stage: ProjectBuildTrialStage) -> None:
        self._collection.document(stage.id).set(stage.model_dump(mode="python"))

    def get(self, stage_id: str) -> ProjectBuildTrialStage | None:
        snap = self._collection.document(stage_id).get()
        if not snap.exists:
            return None
        return ProjectBuildTrialStage(**snap.to_dict())

    def update(self, stage: ProjectBuildTrialStage) -> None:
        self._collection.document(stage.id).set(stage.model_dump(mode="python"))

    def list_by_trial(self, trial_id: str) -> list[ProjectBuildTrialStage]:
        docs = self._collection.where("trial_id", "==", trial_id).stream()
        items = [ProjectBuildTrialStage(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda s: s.created_at)


class SwarmPolicyRepository(Protocol):
    def save(self, policy: SwarmPolicy) -> None: ...
    def get(self, policy_id: str) -> SwarmPolicy | None: ...
    def update(self, policy: SwarmPolicy) -> None: ...
    def list_by_project(self, project_id: str) -> list[SwarmPolicy]: ...


class InMemorySwarmPolicyRepository:
    def __init__(self) -> None:
        self._store: dict[str, SwarmPolicy] = {}

    def save(self, policy: SwarmPolicy) -> None:
        self._store[policy.id] = policy

    def get(self, policy_id: str) -> SwarmPolicy | None:
        return self._store.get(policy_id)

    def update(self, policy: SwarmPolicy) -> None:
        self._store[policy.id] = policy

    def list_by_project(self, project_id: str) -> list[SwarmPolicy]:
        items = [p for p in self._store.values() if p.project_id == project_id]
        return sorted(items, key=lambda p: p.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreSwarmPolicyRepository:
    def __init__(self, client, collection_name: str = "swarm_policies") -> None:
        self._collection = client.collection(collection_name)

    def save(self, policy: SwarmPolicy) -> None:
        self._collection.document(policy.id).set(policy.model_dump(mode="python"))

    def get(self, policy_id: str) -> SwarmPolicy | None:
        snap = self._collection.document(policy_id).get()
        if not snap.exists:
            return None
        return SwarmPolicy(**snap.to_dict())

    def update(self, policy: SwarmPolicy) -> None:
        self._collection.document(policy.id).set(policy.model_dump(mode="python"))

    def list_by_project(self, project_id: str) -> list[SwarmPolicy]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        items = [SwarmPolicy(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda p: p.created_at, reverse=True)


class BudgetPolicyRepository(Protocol):
    def save(self, policy: BudgetPolicy) -> None: ...
    def get(self, policy_id: str) -> BudgetPolicy | None: ...
    def update(self, policy: BudgetPolicy) -> None: ...
    def list_by_project(self, project_id: str) -> list[BudgetPolicy]: ...


class InMemoryBudgetPolicyRepository:
    def __init__(self) -> None:
        self._store: dict[str, BudgetPolicy] = {}

    def save(self, policy: BudgetPolicy) -> None:
        self._store[policy.id] = policy

    def get(self, policy_id: str) -> BudgetPolicy | None:
        return self._store.get(policy_id)

    def update(self, policy: BudgetPolicy) -> None:
        self._store[policy.id] = policy

    def list_by_project(self, project_id: str) -> list[BudgetPolicy]:
        items = [p for p in self._store.values() if p.project_id == project_id]
        return sorted(items, key=lambda p: p.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreBudgetPolicyRepository:
    def __init__(self, client, collection_name: str = "budget_policies") -> None:
        self._collection = client.collection(collection_name)

    def save(self, policy: BudgetPolicy) -> None:
        self._collection.document(policy.id).set(policy.model_dump(mode="python"))

    def get(self, policy_id: str) -> BudgetPolicy | None:
        snap = self._collection.document(policy_id).get()
        if not snap.exists:
            return None
        return BudgetPolicy(**snap.to_dict())

    def update(self, policy: BudgetPolicy) -> None:
        self._collection.document(policy.id).set(policy.model_dump(mode="python"))

    def list_by_project(self, project_id: str) -> list[BudgetPolicy]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        items = [BudgetPolicy(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda p: p.created_at, reverse=True)


class PromptContextCacheRepository(Protocol):
    def save(self, entry: PromptContextCacheEntry) -> None: ...
    def get(self, entry_id: str) -> PromptContextCacheEntry | None: ...
    def get_by_key(self, cache_key: str) -> PromptContextCacheEntry | None: ...
    def list_by_project(self, project_id: str) -> list[PromptContextCacheEntry]: ...
    def list_by_source(
        self, source_type: str, source_id: str
    ) -> list[PromptContextCacheEntry]: ...
    def delete(self, entry_id: str) -> None: ...


class InMemoryPromptContextCacheRepository:
    def __init__(self) -> None:
        self._store: dict[str, PromptContextCacheEntry] = {}

    def save(self, entry: PromptContextCacheEntry) -> None:
        self._store[entry.id] = entry

    def get(self, entry_id: str) -> PromptContextCacheEntry | None:
        return self._store.get(entry_id)

    def get_by_key(self, cache_key: str) -> PromptContextCacheEntry | None:
        for e in self._store.values():
            if e.cache_key == cache_key:
                return e
        return None

    def list_by_project(self, project_id: str) -> list[PromptContextCacheEntry]:
        items = [e for e in self._store.values() if e.project_id == project_id]
        return sorted(items, key=lambda e: e.created_at, reverse=True)

    def list_by_source(
        self, source_type: str, source_id: str
    ) -> list[PromptContextCacheEntry]:
        items = [
            e
            for e in self._store.values()
            if e.source_type == source_type and e.source_id == source_id
        ]
        return sorted(items, key=lambda e: e.created_at, reverse=True)

    def delete(self, entry_id: str) -> None:
        self._store.pop(entry_id, None)

    def clear(self) -> None:
        self._store.clear()


class FirestorePromptContextCacheRepository:
    def __init__(self, client, collection_name: str = "prompt_context_cache") -> None:
        self._collection = client.collection(collection_name)

    def save(self, entry: PromptContextCacheEntry) -> None:
        self._collection.document(entry.id).set(entry.model_dump(mode="python"))

    def get(self, entry_id: str) -> PromptContextCacheEntry | None:
        snap = self._collection.document(entry_id).get()
        if not snap.exists:
            return None
        return PromptContextCacheEntry(**snap.to_dict())

    def get_by_key(self, cache_key: str) -> PromptContextCacheEntry | None:
        docs = list(self._collection.where("cache_key", "==", cache_key).limit(1).stream())
        if not docs:
            return None
        return PromptContextCacheEntry(**docs[0].to_dict())

    def list_by_project(self, project_id: str) -> list[PromptContextCacheEntry]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        items = [PromptContextCacheEntry(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda e: e.created_at, reverse=True)

    def list_by_source(
        self, source_type: str, source_id: str
    ) -> list[PromptContextCacheEntry]:
        docs = (
            self._collection.where("source_type", "==", source_type)
            .where("source_id", "==", source_id)
            .stream()
        )
        items = [PromptContextCacheEntry(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda e: e.created_at, reverse=True)

    def delete(self, entry_id: str) -> None:
        self._collection.document(entry_id).delete()


class ArtifactSummaryRepository(Protocol):
    def save(self, summary: ArtifactSummary) -> None: ...
    def get(self, summary_id: str) -> ArtifactSummary | None: ...
    def list_by_artifact(self, artifact_id: str) -> list[ArtifactSummary]: ...
    def list_by_project(self, project_id: str) -> list[ArtifactSummary]: ...


class InMemoryArtifactSummaryRepository:
    def __init__(self) -> None:
        self._store: dict[str, ArtifactSummary] = {}

    def save(self, summary: ArtifactSummary) -> None:
        self._store[summary.id] = summary

    def get(self, summary_id: str) -> ArtifactSummary | None:
        return self._store.get(summary_id)

    def list_by_artifact(self, artifact_id: str) -> list[ArtifactSummary]:
        items = [s for s in self._store.values() if s.artifact_id == artifact_id]
        return sorted(items, key=lambda s: s.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[ArtifactSummary]:
        items = [s for s in self._store.values() if s.project_id == project_id]
        return sorted(items, key=lambda s: s.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreArtifactSummaryRepository:
    def __init__(self, client, collection_name: str = "artifact_summaries") -> None:
        self._collection = client.collection(collection_name)

    def save(self, summary: ArtifactSummary) -> None:
        self._collection.document(summary.id).set(summary.model_dump(mode="python"))

    def get(self, summary_id: str) -> ArtifactSummary | None:
        snap = self._collection.document(summary_id).get()
        if not snap.exists:
            return None
        return ArtifactSummary(**snap.to_dict())

    def list_by_artifact(self, artifact_id: str) -> list[ArtifactSummary]:
        docs = self._collection.where("artifact_id", "==", artifact_id).stream()
        items = [ArtifactSummary(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda s: s.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[ArtifactSummary]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        items = [ArtifactSummary(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda s: s.created_at, reverse=True)


class ContextPackRepository(Protocol):
    def save(self, pack: ContextPack) -> None: ...
    def get(self, pack_id: str) -> ContextPack | None: ...
    def list_by_project(self, project_id: str) -> list[ContextPack]: ...
    def list_by_source(self, source_type: str, source_id: str) -> list[ContextPack]: ...
    def list_by_target(self, target_type: str, target_id: str) -> list[ContextPack]: ...


class InMemoryContextPackRepository:
    def __init__(self) -> None:
        self._store: dict[str, ContextPack] = {}

    def save(self, pack: ContextPack) -> None:
        self._store[pack.id] = pack

    def get(self, pack_id: str) -> ContextPack | None:
        return self._store.get(pack_id)

    def list_by_project(self, project_id: str) -> list[ContextPack]:
        items = [p for p in self._store.values() if p.project_id == project_id]
        return sorted(items, key=lambda p: p.created_at, reverse=True)

    def list_by_source(self, source_type: str, source_id: str) -> list[ContextPack]:
        items = [
            p
            for p in self._store.values()
            if p.source_type == source_type and p.source_id == source_id
        ]
        return sorted(items, key=lambda p: p.created_at, reverse=True)

    def list_by_target(self, target_type: str, target_id: str) -> list[ContextPack]:
        items = [
            p
            for p in self._store.values()
            if p.target_type == target_type and p.target_id == target_id
        ]
        return sorted(items, key=lambda p: p.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreContextPackRepository:
    def __init__(self, client, collection_name: str = "context_packs") -> None:
        self._collection = client.collection(collection_name)

    def save(self, pack: ContextPack) -> None:
        self._collection.document(pack.id).set(pack.model_dump(mode="python"))

    def get(self, pack_id: str) -> ContextPack | None:
        snap = self._collection.document(pack_id).get()
        if not snap.exists:
            return None
        return ContextPack(**snap.to_dict())

    def list_by_project(self, project_id: str) -> list[ContextPack]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        items = [ContextPack(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda p: p.created_at, reverse=True)

    def list_by_source(self, source_type: str, source_id: str) -> list[ContextPack]:
        docs = (
            self._collection.where("source_type", "==", source_type)
            .where("source_id", "==", source_id)
            .stream()
        )
        items = [ContextPack(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda p: p.created_at, reverse=True)

    def list_by_target(self, target_type: str, target_id: str) -> list[ContextPack]:
        docs = (
            self._collection.where("target_type", "==", target_type)
            .where("target_id", "==", target_id)
            .stream()
        )
        items = [ContextPack(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda p: p.created_at, reverse=True)


class CostRecordRepository(Protocol):
    def save(self, record: CostRecord) -> None: ...
    def get(self, record_id: str) -> CostRecord | None: ...
    def list_by_project(self, project_id: str) -> list[CostRecord]: ...
    def list_by_source(self, source_type: str, source_id: str) -> list[CostRecord]: ...
    def list_by_provider_model(
        self, project_id: str, provider: str | None = None, model: str | None = None
    ) -> list[CostRecord]: ...
    def list_by_workflow(
        self, project_id: str, workflow_type: str
    ) -> list[CostRecord]: ...


class InMemoryCostRecordRepository:
    def __init__(self) -> None:
        self._store: dict[str, CostRecord] = {}

    def save(self, record: CostRecord) -> None:
        self._store[record.id] = record

    def get(self, record_id: str) -> CostRecord | None:
        return self._store.get(record_id)

    def list_by_project(self, project_id: str) -> list[CostRecord]:
        items = [r for r in self._store.values() if r.project_id == project_id]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def list_by_source(self, source_type: str, source_id: str) -> list[CostRecord]:
        items = [
            r
            for r in self._store.values()
            if r.source_type == source_type and r.source_id == source_id
        ]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def list_by_provider_model(
        self, project_id: str, provider: str | None = None, model: str | None = None
    ) -> list[CostRecord]:
        items = [r for r in self._store.values() if r.project_id == project_id]
        if provider is not None:
            items = [r for r in items if r.provider == provider]
        if model is not None:
            items = [r for r in items if r.model == model]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def list_by_workflow(
        self, project_id: str, workflow_type: str
    ) -> list[CostRecord]:
        items = [
            r
            for r in self._store.values()
            if r.project_id == project_id and r.workflow_type == workflow_type
        ]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreCostRecordRepository:
    def __init__(self, client, collection_name: str = "cost_records") -> None:
        self._collection = client.collection(collection_name)

    def save(self, record: CostRecord) -> None:
        self._collection.document(record.id).set(record.model_dump(mode="python"))

    def get(self, record_id: str) -> CostRecord | None:
        snap = self._collection.document(record_id).get()
        if not snap.exists:
            return None
        return CostRecord(**snap.to_dict())

    def list_by_project(self, project_id: str) -> list[CostRecord]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        items = [CostRecord(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def list_by_source(self, source_type: str, source_id: str) -> list[CostRecord]:
        docs = (
            self._collection.where("source_type", "==", source_type)
            .where("source_id", "==", source_id)
            .stream()
        )
        items = [CostRecord(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def list_by_provider_model(
        self, project_id: str, provider: str | None = None, model: str | None = None
    ) -> list[CostRecord]:
        q = self._collection.where("project_id", "==", project_id)
        if provider is not None:
            q = q.where("provider", "==", provider)
        if model is not None:
            q = q.where("model", "==", model)
        items = [CostRecord(**d.to_dict()) for d in q.stream()]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def list_by_workflow(
        self, project_id: str, workflow_type: str
    ) -> list[CostRecord]:
        docs = (
            self._collection.where("project_id", "==", project_id)
            .where("workflow_type", "==", workflow_type)
            .stream()
        )
        items = [CostRecord(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda r: r.created_at, reverse=True)


class ExperimentPlanRepository(Protocol):
    def save(self, plan: ExperimentPlan) -> None: ...
    def get(self, plan_id: str) -> ExperimentPlan | None: ...
    def update(self, plan: ExperimentPlan) -> None: ...
    def list_all(self) -> list[ExperimentPlan]: ...
    def list_by_project(self, project_id: str) -> list[ExperimentPlan]: ...
    def list_by_proposal(self, proposal_id: str) -> list[ExperimentPlan]: ...


class InMemoryExperimentPlanRepository:
    def __init__(self) -> None:
        self._store: dict[str, ExperimentPlan] = {}

    def save(self, plan: ExperimentPlan) -> None:
        self._store[plan.id] = plan

    def get(self, plan_id: str) -> ExperimentPlan | None:
        return self._store.get(plan_id)

    def update(self, plan: ExperimentPlan) -> None:
        self._store[plan.id] = plan

    def list_all(self) -> list[ExperimentPlan]:
        return sorted(self._store.values(), key=lambda p: p.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[ExperimentPlan]:
        items = [p for p in self._store.values() if p.project_id == project_id]
        return sorted(items, key=lambda p: p.created_at, reverse=True)

    def list_by_proposal(self, proposal_id: str) -> list[ExperimentPlan]:
        items = [p for p in self._store.values() if p.proposal_id == proposal_id]
        return sorted(items, key=lambda p: p.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreExperimentPlanRepository:
    def __init__(self, client, collection_name: str = "experiment_plans") -> None:
        self._collection = client.collection(collection_name)

    def save(self, plan: ExperimentPlan) -> None:
        self._collection.document(plan.id).set(plan.model_dump(mode="python"))

    def get(self, plan_id: str) -> ExperimentPlan | None:
        snap = self._collection.document(plan_id).get()
        if not snap.exists:
            return None
        return ExperimentPlan(**snap.to_dict())

    def update(self, plan: ExperimentPlan) -> None:
        self._collection.document(plan.id).set(plan.model_dump(mode="python"))

    def list_all(self) -> list[ExperimentPlan]:
        docs = self._collection.stream()
        items = [ExperimentPlan(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda p: p.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[ExperimentPlan]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        items = [ExperimentPlan(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda p: p.created_at, reverse=True)

    def list_by_proposal(self, proposal_id: str) -> list[ExperimentPlan]:
        docs = self._collection.where("proposal_id", "==", proposal_id).stream()
        items = [ExperimentPlan(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda p: p.created_at, reverse=True)


class ExperimentRunRepository(Protocol):
    def save(self, run: ExperimentRun) -> None: ...
    def get(self, run_id: str) -> ExperimentRun | None: ...
    def update(self, run: ExperimentRun) -> None: ...
    def list_by_plan(self, plan_id: str) -> list[ExperimentRun]: ...
    def list_by_project(self, project_id: str) -> list[ExperimentRun]: ...


class InMemoryExperimentRunRepository:
    def __init__(self) -> None:
        self._store: dict[str, ExperimentRun] = {}

    def save(self, run: ExperimentRun) -> None:
        self._store[run.id] = run

    def get(self, run_id: str) -> ExperimentRun | None:
        return self._store.get(run_id)

    def update(self, run: ExperimentRun) -> None:
        self._store[run.id] = run

    def list_by_plan(self, plan_id: str) -> list[ExperimentRun]:
        items = [
            r for r in self._store.values() if r.experiment_plan_id == plan_id
        ]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[ExperimentRun]:
        items = [r for r in self._store.values() if r.project_id == project_id]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreExperimentRunRepository:
    def __init__(self, client, collection_name: str = "experiment_runs") -> None:
        self._collection = client.collection(collection_name)

    def save(self, run: ExperimentRun) -> None:
        self._collection.document(run.id).set(run.model_dump(mode="python"))

    def get(self, run_id: str) -> ExperimentRun | None:
        snap = self._collection.document(run_id).get()
        if not snap.exists:
            return None
        return ExperimentRun(**snap.to_dict())

    def update(self, run: ExperimentRun) -> None:
        self._collection.document(run.id).set(run.model_dump(mode="python"))

    def list_by_plan(self, plan_id: str) -> list[ExperimentRun]:
        docs = self._collection.where("experiment_plan_id", "==", plan_id).stream()
        items = [ExperimentRun(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[ExperimentRun]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        items = [ExperimentRun(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda r: r.created_at, reverse=True)


class ArchitectureDecisionRecordRepository(Protocol):
    def save(self, adr: ArchitectureDecisionRecord) -> None: ...
    def get(self, adr_id: str) -> ArchitectureDecisionRecord | None: ...
    def update(self, adr: ArchitectureDecisionRecord) -> None: ...
    def list_all(self) -> list[ArchitectureDecisionRecord]: ...
    def list_by_project(
        self, project_id: str
    ) -> list[ArchitectureDecisionRecord]: ...
    def list_by_proposal(
        self, proposal_id: str
    ) -> list[ArchitectureDecisionRecord]: ...


class InMemoryArchitectureDecisionRecordRepository:
    def __init__(self) -> None:
        self._store: dict[str, ArchitectureDecisionRecord] = {}

    def save(self, adr: ArchitectureDecisionRecord) -> None:
        self._store[adr.id] = adr

    def get(self, adr_id: str) -> ArchitectureDecisionRecord | None:
        return self._store.get(adr_id)

    def update(self, adr: ArchitectureDecisionRecord) -> None:
        self._store[adr.id] = adr

    def list_all(self) -> list[ArchitectureDecisionRecord]:
        return sorted(self._store.values(), key=lambda a: a.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[ArchitectureDecisionRecord]:
        items = [a for a in self._store.values() if a.project_id == project_id]
        return sorted(items, key=lambda a: a.created_at, reverse=True)

    def list_by_proposal(self, proposal_id: str) -> list[ArchitectureDecisionRecord]:
        items = [a for a in self._store.values() if a.proposal_id == proposal_id]
        return sorted(items, key=lambda a: a.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreArchitectureDecisionRecordRepository:
    def __init__(
        self, client, collection_name: str = "architecture_decisions"
    ) -> None:
        self._collection = client.collection(collection_name)

    def save(self, adr: ArchitectureDecisionRecord) -> None:
        self._collection.document(adr.id).set(adr.model_dump(mode="python"))

    def get(self, adr_id: str) -> ArchitectureDecisionRecord | None:
        snap = self._collection.document(adr_id).get()
        if not snap.exists:
            return None
        return ArchitectureDecisionRecord(**snap.to_dict())

    def update(self, adr: ArchitectureDecisionRecord) -> None:
        self._collection.document(adr.id).set(adr.model_dump(mode="python"))

    def list_all(self) -> list[ArchitectureDecisionRecord]:
        docs = self._collection.stream()
        items = [ArchitectureDecisionRecord(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda a: a.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[ArchitectureDecisionRecord]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        items = [ArchitectureDecisionRecord(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda a: a.created_at, reverse=True)

    def list_by_proposal(self, proposal_id: str) -> list[ArchitectureDecisionRecord]:
        docs = self._collection.where("proposal_id", "==", proposal_id).stream()
        items = [ArchitectureDecisionRecord(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda a: a.created_at, reverse=True)


class ImprovementProposalRepository(Protocol):
    def save(self, proposal: ImprovementProposal) -> None: ...
    def get(self, proposal_id: str) -> ImprovementProposal | None: ...
    def update(self, proposal: ImprovementProposal) -> None: ...
    def list_all(self) -> list[ImprovementProposal]: ...
    def list_by_project(self, project_id: str) -> list[ImprovementProposal]: ...
    def list_by_source(
        self, source_type: str, source_id: str
    ) -> list[ImprovementProposal]: ...


class InMemoryImprovementProposalRepository:
    def __init__(self) -> None:
        self._store: dict[str, ImprovementProposal] = {}

    def save(self, proposal: ImprovementProposal) -> None:
        self._store[proposal.id] = proposal

    def get(self, proposal_id: str) -> ImprovementProposal | None:
        return self._store.get(proposal_id)

    def update(self, proposal: ImprovementProposal) -> None:
        self._store[proposal.id] = proposal

    def list_all(self) -> list[ImprovementProposal]:
        return sorted(self._store.values(), key=lambda p: p.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[ImprovementProposal]:
        items = [p for p in self._store.values() if p.project_id == project_id]
        return sorted(items, key=lambda p: p.created_at, reverse=True)

    def list_by_source(
        self, source_type: str, source_id: str
    ) -> list[ImprovementProposal]:
        items = [
            p
            for p in self._store.values()
            if p.source_type == source_type and p.source_id == source_id
        ]
        return sorted(items, key=lambda p: p.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreImprovementProposalRepository:
    def __init__(self, client, collection_name: str = "improvement_proposals") -> None:
        self._collection = client.collection(collection_name)

    def save(self, proposal: ImprovementProposal) -> None:
        self._collection.document(proposal.id).set(proposal.model_dump(mode="python"))

    def get(self, proposal_id: str) -> ImprovementProposal | None:
        snap = self._collection.document(proposal_id).get()
        if not snap.exists:
            return None
        return ImprovementProposal(**snap.to_dict())

    def update(self, proposal: ImprovementProposal) -> None:
        self._collection.document(proposal.id).set(proposal.model_dump(mode="python"))

    def list_all(self) -> list[ImprovementProposal]:
        docs = self._collection.stream()
        items = [ImprovementProposal(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda p: p.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[ImprovementProposal]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        items = [ImprovementProposal(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda p: p.created_at, reverse=True)

    def list_by_source(
        self, source_type: str, source_id: str
    ) -> list[ImprovementProposal]:
        docs = (
            self._collection.where("source_type", "==", source_type)
            .where("source_id", "==", source_id)
            .stream()
        )
        items = [ImprovementProposal(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda p: p.created_at, reverse=True)


class ArchitectureReviewRepository(Protocol):
    def save(self, review: ArchitectureReview) -> None: ...
    def get(self, review_id: str) -> ArchitectureReview | None: ...
    def update(self, review: ArchitectureReview) -> None: ...
    def list_all(self) -> list[ArchitectureReview]: ...
    def list_by_project(self, project_id: str) -> list[ArchitectureReview]: ...
    def list_by_target(
        self, target_type: str, target_id: str
    ) -> list[ArchitectureReview]: ...


class InMemoryArchitectureReviewRepository:
    def __init__(self) -> None:
        self._store: dict[str, ArchitectureReview] = {}

    def save(self, review: ArchitectureReview) -> None:
        self._store[review.id] = review

    def get(self, review_id: str) -> ArchitectureReview | None:
        return self._store.get(review_id)

    def update(self, review: ArchitectureReview) -> None:
        self._store[review.id] = review

    def list_all(self) -> list[ArchitectureReview]:
        return sorted(
            self._store.values(), key=lambda r: r.created_at, reverse=True
        )

    def list_by_project(self, project_id: str) -> list[ArchitectureReview]:
        items = [r for r in self._store.values() if r.project_id == project_id]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def list_by_target(
        self, target_type: str, target_id: str
    ) -> list[ArchitectureReview]:
        items = [
            r
            for r in self._store.values()
            if r.target_type == target_type and r.target_id == target_id
        ]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreArchitectureReviewRepository:
    def __init__(self, client, collection_name: str = "architecture_reviews") -> None:
        self._collection = client.collection(collection_name)

    def save(self, review: ArchitectureReview) -> None:
        self._collection.document(review.id).set(review.model_dump(mode="python"))

    def get(self, review_id: str) -> ArchitectureReview | None:
        snap = self._collection.document(review_id).get()
        if not snap.exists:
            return None
        return ArchitectureReview(**snap.to_dict())

    def update(self, review: ArchitectureReview) -> None:
        self._collection.document(review.id).set(review.model_dump(mode="python"))

    def list_all(self) -> list[ArchitectureReview]:
        docs = self._collection.stream()
        items = [ArchitectureReview(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[ArchitectureReview]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        items = [ArchitectureReview(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def list_by_target(
        self, target_type: str, target_id: str
    ) -> list[ArchitectureReview]:
        docs = (
            self._collection.where("target_type", "==", target_type)
            .where("target_id", "==", target_id)
            .stream()
        )
        items = [ArchitectureReview(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda r: r.created_at, reverse=True)


class BackupExportRepository(Protocol):
    def save(self, export: BackupExport) -> None: ...
    def get(self, export_id: str) -> BackupExport | None: ...
    def update(self, export: BackupExport) -> None: ...
    def list_all(self) -> list[BackupExport]: ...
    def list_by_project(self, project_id: str) -> list[BackupExport]: ...


class InMemoryBackupExportRepository:
    def __init__(self) -> None:
        self._store: dict[str, BackupExport] = {}

    def save(self, export: BackupExport) -> None:
        self._store[export.id] = export

    def get(self, export_id: str) -> BackupExport | None:
        return self._store.get(export_id)

    def update(self, export: BackupExport) -> None:
        self._store[export.id] = export

    def list_all(self) -> list[BackupExport]:
        return sorted(self._store.values(), key=lambda e: e.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[BackupExport]:
        items = [e for e in self._store.values() if e.project_id == project_id]
        return sorted(items, key=lambda e: e.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreBackupExportRepository:
    def __init__(self, client, collection_name: str = "backup_exports") -> None:
        self._collection = client.collection(collection_name)

    def save(self, export: BackupExport) -> None:
        self._collection.document(export.id).set(export.model_dump(mode="python"))

    def get(self, export_id: str) -> BackupExport | None:
        snap = self._collection.document(export_id).get()
        if not snap.exists:
            return None
        return BackupExport(**snap.to_dict())

    def update(self, export: BackupExport) -> None:
        self._collection.document(export.id).set(export.model_dump(mode="python"))

    def list_all(self) -> list[BackupExport]:
        docs = self._collection.stream()
        items = [BackupExport(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda e: e.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[BackupExport]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        items = [BackupExport(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda e: e.created_at, reverse=True)


class BackupImportRepository(Protocol):
    def save(self, item: BackupImport) -> None: ...
    def get(self, import_id: str) -> BackupImport | None: ...
    def update(self, item: BackupImport) -> None: ...
    def list_all(self) -> list[BackupImport]: ...
    def list_by_project(self, project_id: str) -> list[BackupImport]: ...


class InMemoryBackupImportRepository:
    def __init__(self) -> None:
        self._store: dict[str, BackupImport] = {}

    def save(self, item: BackupImport) -> None:
        self._store[item.id] = item

    def get(self, import_id: str) -> BackupImport | None:
        return self._store.get(import_id)

    def update(self, item: BackupImport) -> None:
        self._store[item.id] = item

    def list_all(self) -> list[BackupImport]:
        return sorted(self._store.values(), key=lambda i: i.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[BackupImport]:
        items = [i for i in self._store.values() if i.project_id == project_id]
        return sorted(items, key=lambda i: i.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreBackupImportRepository:
    def __init__(self, client, collection_name: str = "backup_imports") -> None:
        self._collection = client.collection(collection_name)

    def save(self, item: BackupImport) -> None:
        self._collection.document(item.id).set(item.model_dump(mode="python"))

    def get(self, import_id: str) -> BackupImport | None:
        snap = self._collection.document(import_id).get()
        if not snap.exists:
            return None
        return BackupImport(**snap.to_dict())

    def update(self, item: BackupImport) -> None:
        self._collection.document(item.id).set(item.model_dump(mode="python"))

    def list_all(self) -> list[BackupImport]:
        docs = self._collection.stream()
        items = [BackupImport(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda i: i.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[BackupImport]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        items = [BackupImport(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda i: i.created_at, reverse=True)


class WorkSafePolicyRepository(Protocol):
    def save(self, policy: WorkSafePolicy) -> None: ...
    def get(self, policy_id: str) -> WorkSafePolicy | None: ...
    def update(self, policy: WorkSafePolicy) -> None: ...
    def list_all(self) -> list[WorkSafePolicy]: ...
    def list_by_project(self, project_id: str) -> list[WorkSafePolicy]: ...
    def list_global(self) -> list[WorkSafePolicy]: ...


class InMemoryWorkSafePolicyRepository:
    def __init__(self) -> None:
        self._store: dict[str, WorkSafePolicy] = {}

    def save(self, policy: WorkSafePolicy) -> None:
        self._store[policy.id] = policy

    def get(self, policy_id: str) -> WorkSafePolicy | None:
        return self._store.get(policy_id)

    def update(self, policy: WorkSafePolicy) -> None:
        self._store[policy.id] = policy

    def list_all(self) -> list[WorkSafePolicy]:
        return sorted(self._store.values(), key=lambda p: p.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[WorkSafePolicy]:
        items = [p for p in self._store.values() if p.project_id == project_id]
        return sorted(items, key=lambda p: p.created_at, reverse=True)

    def list_global(self) -> list[WorkSafePolicy]:
        items = [p for p in self._store.values() if p.project_id is None]
        return sorted(items, key=lambda p: p.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreWorkSafePolicyRepository:
    def __init__(self, client, collection_name: str = "work_safe_policies") -> None:
        self._collection = client.collection(collection_name)

    def save(self, policy: WorkSafePolicy) -> None:
        self._collection.document(policy.id).set(policy.model_dump(mode="python"))

    def get(self, policy_id: str) -> WorkSafePolicy | None:
        snap = self._collection.document(policy_id).get()
        if not snap.exists:
            return None
        return WorkSafePolicy(**snap.to_dict())

    def update(self, policy: WorkSafePolicy) -> None:
        self._collection.document(policy.id).set(policy.model_dump(mode="python"))

    def list_all(self) -> list[WorkSafePolicy]:
        docs = self._collection.stream()
        items = [WorkSafePolicy(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda p: p.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[WorkSafePolicy]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        items = [WorkSafePolicy(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda p: p.created_at, reverse=True)

    def list_global(self) -> list[WorkSafePolicy]:
        docs = self._collection.where("project_id", "==", None).stream()
        items = [WorkSafePolicy(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda p: p.created_at, reverse=True)


class AuditExportRequestRepository(Protocol):
    def save(self, request: AuditExportRequest) -> None: ...
    def get(self, request_id: str) -> AuditExportRequest | None: ...
    def update(self, request: AuditExportRequest) -> None: ...
    def list_all(self) -> list[AuditExportRequest]: ...
    def list_by_project(self, project_id: str) -> list[AuditExportRequest]: ...


class InMemoryAuditExportRequestRepository:
    def __init__(self) -> None:
        self._store: dict[str, AuditExportRequest] = {}

    def save(self, request: AuditExportRequest) -> None:
        self._store[request.id] = request

    def get(self, request_id: str) -> AuditExportRequest | None:
        return self._store.get(request_id)

    def update(self, request: AuditExportRequest) -> None:
        self._store[request.id] = request

    def list_all(self) -> list[AuditExportRequest]:
        return sorted(self._store.values(), key=lambda r: r.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[AuditExportRequest]:
        items = [r for r in self._store.values() if r.project_id == project_id]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreAuditExportRequestRepository:
    def __init__(
        self, client, collection_name: str = "audit_export_requests"
    ) -> None:
        self._collection = client.collection(collection_name)

    def save(self, request: AuditExportRequest) -> None:
        self._collection.document(request.id).set(request.model_dump(mode="python"))

    def get(self, request_id: str) -> AuditExportRequest | None:
        snap = self._collection.document(request_id).get()
        if not snap.exists:
            return None
        return AuditExportRequest(**snap.to_dict())

    def update(self, request: AuditExportRequest) -> None:
        self._collection.document(request.id).set(request.model_dump(mode="python"))

    def list_all(self) -> list[AuditExportRequest]:
        docs = self._collection.stream()
        items = [AuditExportRequest(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[AuditExportRequest]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        items = [AuditExportRequest(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda r: r.created_at, reverse=True)


class ProjectPackRepository(Protocol):
    def save(self, pack: ProjectPack) -> None: ...
    def get(self, pack_id: str) -> ProjectPack | None: ...
    def update(self, pack: ProjectPack) -> None: ...
    def list_all(self) -> list[ProjectPack]: ...
    def get_by_slug(self, slug: str) -> ProjectPack | None: ...


class InMemoryProjectPackRepository:
    def __init__(self) -> None:
        self._store: dict[str, ProjectPack] = {}

    def save(self, pack: ProjectPack) -> None:
        self._store[pack.id] = pack

    def get(self, pack_id: str) -> ProjectPack | None:
        return self._store.get(pack_id)

    def update(self, pack: ProjectPack) -> None:
        self._store[pack.id] = pack

    def list_all(self) -> list[ProjectPack]:
        return sorted(self._store.values(), key=lambda p: p.created_at, reverse=True)

    def get_by_slug(self, slug: str) -> ProjectPack | None:
        for p in self._store.values():
            if p.slug == slug:
                return p
        return None

    def clear(self) -> None:
        self._store.clear()


class FirestoreProjectPackRepository:
    def __init__(self, client, collection_name: str = "project_packs") -> None:
        self._collection = client.collection(collection_name)

    def save(self, pack: ProjectPack) -> None:
        self._collection.document(pack.id).set(pack.model_dump(mode="python"))

    def get(self, pack_id: str) -> ProjectPack | None:
        snap = self._collection.document(pack_id).get()
        if not snap.exists:
            return None
        return ProjectPack(**snap.to_dict())

    def update(self, pack: ProjectPack) -> None:
        self._collection.document(pack.id).set(pack.model_dump(mode="python"))

    def list_all(self) -> list[ProjectPack]:
        docs = self._collection.stream()
        items = [ProjectPack(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda p: p.created_at, reverse=True)

    def get_by_slug(self, slug: str) -> ProjectPack | None:
        docs = list(self._collection.where("slug", "==", slug).stream())
        if not docs:
            return None
        return ProjectPack(**docs[0].to_dict())


class WorkflowTemplateRepository(Protocol):
    def save(self, template: WorkflowTemplate) -> None: ...
    def get(self, template_id: str) -> WorkflowTemplate | None: ...
    def update(self, template: WorkflowTemplate) -> None: ...
    def list_all(self) -> list[WorkflowTemplate]: ...
    def get_by_slug(self, slug: str) -> WorkflowTemplate | None: ...


class InMemoryWorkflowTemplateRepository:
    def __init__(self) -> None:
        self._store: dict[str, WorkflowTemplate] = {}

    def save(self, template: WorkflowTemplate) -> None:
        self._store[template.id] = template

    def get(self, template_id: str) -> WorkflowTemplate | None:
        return self._store.get(template_id)

    def update(self, template: WorkflowTemplate) -> None:
        self._store[template.id] = template

    def list_all(self) -> list[WorkflowTemplate]:
        return sorted(self._store.values(), key=lambda t: t.created_at, reverse=True)

    def get_by_slug(self, slug: str) -> WorkflowTemplate | None:
        for t in self._store.values():
            if t.slug == slug:
                return t
        return None

    def clear(self) -> None:
        self._store.clear()


class FirestoreWorkflowTemplateRepository:
    def __init__(self, client, collection_name: str = "workflow_templates") -> None:
        self._collection = client.collection(collection_name)

    def save(self, template: WorkflowTemplate) -> None:
        self._collection.document(template.id).set(template.model_dump(mode="python"))

    def get(self, template_id: str) -> WorkflowTemplate | None:
        snap = self._collection.document(template_id).get()
        if not snap.exists:
            return None
        return WorkflowTemplate(**snap.to_dict())

    def update(self, template: WorkflowTemplate) -> None:
        self._collection.document(template.id).set(template.model_dump(mode="python"))

    def list_all(self) -> list[WorkflowTemplate]:
        docs = self._collection.stream()
        items = [WorkflowTemplate(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda t: t.created_at, reverse=True)

    def get_by_slug(self, slug: str) -> WorkflowTemplate | None:
        docs = list(self._collection.where("slug", "==", slug).stream())
        if not docs:
            return None
        return WorkflowTemplate(**docs[0].to_dict())


class ProjectTemplateRepository(Protocol):
    def save(self, template: ProjectTemplate) -> None: ...
    def get(self, template_id: str) -> ProjectTemplate | None: ...
    def update(self, template: ProjectTemplate) -> None: ...
    def list_all(self) -> list[ProjectTemplate]: ...
    def get_by_slug(self, slug: str) -> ProjectTemplate | None: ...


class InMemoryProjectTemplateRepository:
    def __init__(self) -> None:
        self._store: dict[str, ProjectTemplate] = {}

    def save(self, template: ProjectTemplate) -> None:
        self._store[template.id] = template

    def get(self, template_id: str) -> ProjectTemplate | None:
        return self._store.get(template_id)

    def update(self, template: ProjectTemplate) -> None:
        self._store[template.id] = template

    def list_all(self) -> list[ProjectTemplate]:
        return sorted(self._store.values(), key=lambda t: t.created_at, reverse=True)

    def get_by_slug(self, slug: str) -> ProjectTemplate | None:
        for t in self._store.values():
            if t.slug == slug:
                return t
        return None

    def clear(self) -> None:
        self._store.clear()


class FirestoreProjectTemplateRepository:
    def __init__(self, client, collection_name: str = "project_templates") -> None:
        self._collection = client.collection(collection_name)

    def save(self, template: ProjectTemplate) -> None:
        self._collection.document(template.id).set(template.model_dump(mode="python"))

    def get(self, template_id: str) -> ProjectTemplate | None:
        snap = self._collection.document(template_id).get()
        if not snap.exists:
            return None
        return ProjectTemplate(**snap.to_dict())

    def update(self, template: ProjectTemplate) -> None:
        self._collection.document(template.id).set(template.model_dump(mode="python"))

    def list_all(self) -> list[ProjectTemplate]:
        docs = self._collection.stream()
        items = [ProjectTemplate(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda t: t.created_at, reverse=True)

    def get_by_slug(self, slug: str) -> ProjectTemplate | None:
        docs = list(self._collection.where("slug", "==", slug).stream())
        if not docs:
            return None
        return ProjectTemplate(**docs[0].to_dict())


class ProjectRetrospectiveRepository(Protocol):
    def save(self, retro: ProjectRetrospective) -> None: ...
    def get(self, retro_id: str) -> ProjectRetrospective | None: ...
    def update(self, retro: ProjectRetrospective) -> None: ...
    def list_all(self) -> list[ProjectRetrospective]: ...
    def list_by_project(self, project_id: str) -> list[ProjectRetrospective]: ...
    def list_by_trial(self, trial_id: str) -> list[ProjectRetrospective]: ...


class InMemoryProjectRetrospectiveRepository:
    def __init__(self) -> None:
        self._store: dict[str, ProjectRetrospective] = {}

    def save(self, retro: ProjectRetrospective) -> None:
        self._store[retro.id] = retro

    def get(self, retro_id: str) -> ProjectRetrospective | None:
        return self._store.get(retro_id)

    def update(self, retro: ProjectRetrospective) -> None:
        self._store[retro.id] = retro

    def list_all(self) -> list[ProjectRetrospective]:
        return sorted(self._store.values(), key=lambda r: r.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[ProjectRetrospective]:
        items = [r for r in self._store.values() if r.project_id == project_id]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def list_by_trial(self, trial_id: str) -> list[ProjectRetrospective]:
        items = [r for r in self._store.values() if r.trial_id == trial_id]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreProjectRetrospectiveRepository:
    def __init__(
        self, client, collection_name: str = "project_retrospectives"
    ) -> None:
        self._collection = client.collection(collection_name)

    def save(self, retro: ProjectRetrospective) -> None:
        self._collection.document(retro.id).set(retro.model_dump(mode="python"))

    def get(self, retro_id: str) -> ProjectRetrospective | None:
        snap = self._collection.document(retro_id).get()
        if not snap.exists:
            return None
        return ProjectRetrospective(**snap.to_dict())

    def update(self, retro: ProjectRetrospective) -> None:
        self._collection.document(retro.id).set(retro.model_dump(mode="python"))

    def list_all(self) -> list[ProjectRetrospective]:
        docs = self._collection.stream()
        items = [ProjectRetrospective(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[ProjectRetrospective]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        items = [ProjectRetrospective(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda r: r.created_at, reverse=True)

    def list_by_trial(self, trial_id: str) -> list[ProjectRetrospective]:
        docs = self._collection.where("trial_id", "==", trial_id).stream()
        items = [ProjectRetrospective(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda r: r.created_at, reverse=True)


class ResearchBriefRepository(Protocol):
    def save(self, brief: ResearchBrief) -> None: ...
    def get(self, brief_id: str) -> ResearchBrief | None: ...
    def update(self, brief: ResearchBrief) -> None: ...
    def list_all(self) -> list[ResearchBrief]: ...
    def list_by_project(self, project_id: str) -> list[ResearchBrief]: ...


class InMemoryResearchBriefRepository:
    def __init__(self) -> None:
        self._store: dict[str, ResearchBrief] = {}

    def save(self, brief: ResearchBrief) -> None:
        self._store[brief.id] = brief

    def get(self, brief_id: str) -> ResearchBrief | None:
        return self._store.get(brief_id)

    def update(self, brief: ResearchBrief) -> None:
        self._store[brief.id] = brief

    def list_all(self) -> list[ResearchBrief]:
        return sorted(self._store.values(), key=lambda b: b.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[ResearchBrief]:
        items = [b for b in self._store.values() if b.project_id == project_id]
        return sorted(items, key=lambda b: b.created_at, reverse=True)

    def clear(self) -> None:
        self._store.clear()


class FirestoreResearchBriefRepository:
    def __init__(self, client, collection_name: str = "research_briefs") -> None:
        self._collection = client.collection(collection_name)

    def save(self, brief: ResearchBrief) -> None:
        self._collection.document(brief.id).set(brief.model_dump(mode="python"))

    def get(self, brief_id: str) -> ResearchBrief | None:
        snap = self._collection.document(brief_id).get()
        if not snap.exists:
            return None
        return ResearchBrief(**snap.to_dict())

    def update(self, brief: ResearchBrief) -> None:
        self._collection.document(brief.id).set(brief.model_dump(mode="python"))

    def list_all(self) -> list[ResearchBrief]:
        docs = self._collection.stream()
        items = [ResearchBrief(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda b: b.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[ResearchBrief]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        items = [ResearchBrief(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda b: b.created_at, reverse=True)


class ResearchSourceRepository(Protocol):
    def save(self, source: ResearchSource) -> None: ...
    def get(self, source_id: str) -> ResearchSource | None: ...
    def update(self, source: ResearchSource) -> None: ...
    def delete(self, source_id: str) -> None: ...
    def list_all(self) -> list[ResearchSource]: ...
    def list_by_project(self, project_id: str) -> list[ResearchSource]: ...
    def get_by_cache_key(self, cache_key: str) -> ResearchSource | None: ...


class InMemoryResearchSourceRepository:
    def __init__(self) -> None:
        self._store: dict[str, ResearchSource] = {}

    def save(self, source: ResearchSource) -> None:
        self._store[source.id] = source

    def get(self, source_id: str) -> ResearchSource | None:
        return self._store.get(source_id)

    def update(self, source: ResearchSource) -> None:
        self._store[source.id] = source

    def delete(self, source_id: str) -> None:
        self._store.pop(source_id, None)

    def list_all(self) -> list[ResearchSource]:
        return sorted(self._store.values(), key=lambda s: s.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[ResearchSource]:
        items = [s for s in self._store.values() if s.project_id == project_id]
        return sorted(items, key=lambda s: s.created_at, reverse=True)

    def get_by_cache_key(self, cache_key: str) -> ResearchSource | None:
        for s in self._store.values():
            if s.cache_key == cache_key:
                return s
        return None

    def clear(self) -> None:
        self._store.clear()


class FirestoreResearchSourceRepository:
    def __init__(self, client, collection_name: str = "research_sources") -> None:
        self._collection = client.collection(collection_name)

    def save(self, source: ResearchSource) -> None:
        self._collection.document(source.id).set(source.model_dump(mode="python"))

    def get(self, source_id: str) -> ResearchSource | None:
        snap = self._collection.document(source_id).get()
        if not snap.exists:
            return None
        return ResearchSource(**snap.to_dict())

    def update(self, source: ResearchSource) -> None:
        self._collection.document(source.id).set(source.model_dump(mode="python"))

    def delete(self, source_id: str) -> None:
        self._collection.document(source_id).delete()

    def list_all(self) -> list[ResearchSource]:
        docs = self._collection.stream()
        items = [ResearchSource(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda s: s.created_at, reverse=True)

    def list_by_project(self, project_id: str) -> list[ResearchSource]:
        docs = self._collection.where("project_id", "==", project_id).stream()
        items = [ResearchSource(**d.to_dict()) for d in docs]
        return sorted(items, key=lambda s: s.created_at, reverse=True)

    def get_by_cache_key(self, cache_key: str) -> ResearchSource | None:
        docs = list(self._collection.where("cache_key", "==", cache_key).stream())
        if not docs:
            return None
        return ResearchSource(**docs[0].to_dict())


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
    cost_record: CostRecordRepository
    context_pack: ContextPackRepository
    artifact_summary: ArtifactSummaryRepository
    prompt_cache: PromptContextCacheRepository
    budget_policy: BudgetPolicyRepository
    swarm_policy: SwarmPolicyRepository
    project_build_trial: ProjectBuildTrialRepository
    project_build_trial_stage: ProjectBuildTrialStageRepository
    quality_metric_snapshot: QualityMetricSnapshotRepository
    agent_failure_record: AgentFailureRecordRepository
    benchmark_scenario: BenchmarkScenarioRepository
    benchmark_run: BenchmarkRunRepository
    benchmark_run_result: BenchmarkRunResultRepository
    research_brief: ResearchBriefRepository
    research_source: ResearchSourceRepository
    architecture_review: ArchitectureReviewRepository
    improvement_proposal: ImprovementProposalRepository
    architecture_decision: ArchitectureDecisionRecordRepository
    experiment_plan: ExperimentPlanRepository
    experiment_run: ExperimentRunRepository
    project_retrospective: ProjectRetrospectiveRepository
    project_template: ProjectTemplateRepository
    workflow_template: WorkflowTemplateRepository
    project_pack: ProjectPackRepository
    work_safe_policy: WorkSafePolicyRepository
    audit_export_request: AuditExportRequestRepository
    backup_export: BackupExportRepository
    backup_import: BackupImportRepository


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
            cost_record=InMemoryCostRecordRepository(),
            context_pack=InMemoryContextPackRepository(),
            artifact_summary=InMemoryArtifactSummaryRepository(),
            prompt_cache=InMemoryPromptContextCacheRepository(),
            budget_policy=InMemoryBudgetPolicyRepository(),
            swarm_policy=InMemorySwarmPolicyRepository(),
            project_build_trial=InMemoryProjectBuildTrialRepository(),
            project_build_trial_stage=InMemoryProjectBuildTrialStageRepository(),
            quality_metric_snapshot=InMemoryQualityMetricSnapshotRepository(),
            agent_failure_record=InMemoryAgentFailureRecordRepository(),
            benchmark_scenario=InMemoryBenchmarkScenarioRepository(),
            benchmark_run=InMemoryBenchmarkRunRepository(),
            benchmark_run_result=InMemoryBenchmarkRunResultRepository(),
            research_brief=InMemoryResearchBriefRepository(),
            research_source=InMemoryResearchSourceRepository(),
            architecture_review=InMemoryArchitectureReviewRepository(),
            improvement_proposal=InMemoryImprovementProposalRepository(),
            architecture_decision=InMemoryArchitectureDecisionRecordRepository(),
            experiment_plan=InMemoryExperimentPlanRepository(),
            experiment_run=InMemoryExperimentRunRepository(),
            project_retrospective=InMemoryProjectRetrospectiveRepository(),
            project_template=InMemoryProjectTemplateRepository(),
            workflow_template=InMemoryWorkflowTemplateRepository(),
            project_pack=InMemoryProjectPackRepository(),
            work_safe_policy=InMemoryWorkSafePolicyRepository(),
            audit_export_request=InMemoryAuditExportRequestRepository(),
            backup_export=InMemoryBackupExportRepository(),
            backup_import=InMemoryBackupImportRepository(),
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
            cost_record=FirestoreCostRecordRepository(client),
            context_pack=FirestoreContextPackRepository(client),
            artifact_summary=FirestoreArtifactSummaryRepository(client),
            prompt_cache=FirestorePromptContextCacheRepository(client),
            budget_policy=FirestoreBudgetPolicyRepository(client),
            swarm_policy=FirestoreSwarmPolicyRepository(client),
            project_build_trial=FirestoreProjectBuildTrialRepository(client),
            project_build_trial_stage=FirestoreProjectBuildTrialStageRepository(client),
            quality_metric_snapshot=FirestoreQualityMetricSnapshotRepository(client),
            agent_failure_record=FirestoreAgentFailureRecordRepository(client),
            benchmark_scenario=FirestoreBenchmarkScenarioRepository(client),
            benchmark_run=FirestoreBenchmarkRunRepository(client),
            benchmark_run_result=FirestoreBenchmarkRunResultRepository(client),
            research_brief=FirestoreResearchBriefRepository(client),
            research_source=FirestoreResearchSourceRepository(client),
            architecture_review=FirestoreArchitectureReviewRepository(client),
            improvement_proposal=FirestoreImprovementProposalRepository(client),
            architecture_decision=FirestoreArchitectureDecisionRecordRepository(
                client
            ),
            experiment_plan=FirestoreExperimentPlanRepository(client),
            experiment_run=FirestoreExperimentRunRepository(client),
            project_retrospective=FirestoreProjectRetrospectiveRepository(client),
            project_template=FirestoreProjectTemplateRepository(client),
            workflow_template=FirestoreWorkflowTemplateRepository(client),
            project_pack=FirestoreProjectPackRepository(client),
            work_safe_policy=FirestoreWorkSafePolicyRepository(client),
            audit_export_request=FirestoreAuditExportRequestRepository(client),
            backup_export=FirestoreBackupExportRepository(client),
            backup_import=FirestoreBackupImportRepository(client),
        )
    if config.REPOSITORY_PROVIDER == "local_document":
        if config.LOCAL_DOCUMENT_DB_PROVIDER != "mongodb":
            raise ValueError(
                "Unsupported LOCAL_DOCUMENT_DB_PROVIDER="
                f"{config.LOCAL_DOCUMENT_DB_PROVIDER!r}. Supported: mongodb"
            )
        from .repositories_mongo import build_mongo_repositories

        return build_mongo_repositories()
    raise ValueError(
        f"Unknown REPOSITORY_PROVIDER: {config.REPOSITORY_PROVIDER!r}. "
        "Supported: memory, firestore, local_document"
    )
