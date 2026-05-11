"""MongoDB-backed implementations of the repository protocols defined in
``app.repositories`` (Task 40A: local document database provider).

The module is safe to import without ``pymongo`` installed — the dependency
is only resolved inside :func:`build_mongo_repositories`, which is the only
entry point the factory in ``app.repositories`` calls when
``REPOSITORY_PROVIDER=local_document``.
"""

from __future__ import annotations

import re
from typing import Any, Generic, TypeVar
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel

from . import config
from .models import (
    AgentRun,
    Approval,
    Artifact,
    AuditEvent,
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
    ProjectContext,
    ProjectMemoryCandidate,
    PullRequestDraft,
    PullRequestReview,
    RepoSafetyProfile,
    Requirement,
    RequirementAnalysis,
    ReviewFeedback,
    RevisionWorkItem,
    Subtask,
    Ticket,
    ToolRun,
    ToolRunnerDefinition,
    Workspace,
    WorkspaceBranch,
)

T = TypeVar("T", bound=BaseModel)

_COLLECTION_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


def safe_collection_name(name: str) -> str:
    """Validate a Mongo collection name. Returns the name unchanged on success.

    Defense-in-depth check; collection names are constants in this module, but
    the helper prevents accidental drift to invalid characters.
    """
    if not _COLLECTION_NAME_RE.match(name):
        raise ValueError(f"Invalid Mongo collection name: {name!r}")
    return name


def to_mongo_document(model: BaseModel, *, id_field: str = "id") -> dict[str, Any]:
    """Serialize a Pydantic model to a Mongo document.

    Uses ``model_dump(mode="python")`` so native ``datetime`` / nested dict /
    list values are preserved (BSON handles them directly). The chosen
    ``id_field`` value is mirrored into ``_id`` so Mongo uses our string ID
    as the primary key (no ObjectId).
    """
    doc = model.model_dump(mode="python")
    doc["_id"] = doc[id_field]
    return doc


def from_mongo_document(doc: dict[str, Any], model_cls: type[T]) -> T:
    """Deserialize a Mongo document back into a Pydantic model."""
    payload = dict(doc)
    payload.pop("_id", None)
    return model_cls.model_validate(payload)


def _redact_mongo_uri(uri: str) -> str:
    """Strip any ``user:pass@`` segment so a URI is safe to log."""
    try:
        parts = urlsplit(uri)
    except Exception:
        return "<invalid-uri>"
    if not parts.netloc:
        return uri
    netloc = parts.netloc
    if "@" in netloc:
        netloc = netloc.rsplit("@", 1)[1]
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


# ---------------------------------------------------------------------------
# Generic base
# ---------------------------------------------------------------------------


class MongoDocumentRepository(Generic[T]):
    """Base class for Mongo-backed repositories.

    Subclasses set ``collection_name`` and ``model_cls``. The default
    implementations cover save / get / update / list_by_field / list_by_fields
    using the model's ``id`` attribute as the document key.
    """

    collection_name: str = ""
    model_cls: type[BaseModel] = BaseModel
    id_field: str = "id"

    def __init__(self, db: Any, collection_name: str | None = None) -> None:
        name = safe_collection_name(collection_name or self.collection_name)
        self._collection = db[name]

    # --- write ---------------------------------------------------------
    def save(self, model: T) -> None:
        doc = to_mongo_document(model, id_field=self.id_field)
        self._collection.replace_one({"_id": doc["_id"]}, doc, upsert=True)

    # Most protocols expose both save and update with identical semantics.
    update = save

    # --- read ----------------------------------------------------------
    def _get_by_id(self, value: str) -> T | None:
        doc = self._collection.find_one({"_id": value})
        if doc is None:
            return None
        return from_mongo_document(doc, self.model_cls)  # type: ignore[return-value]

    def get(self, id: str) -> T | None:
        return self._get_by_id(id)

    def list_by_field(self, field: str, value: Any) -> list[T]:
        return [
            from_mongo_document(d, self.model_cls)  # type: ignore[misc]
            for d in self._collection.find({field: value})
        ]

    def list_by_fields(self, filters: dict[str, Any]) -> list[T]:
        return [
            from_mongo_document(d, self.model_cls)  # type: ignore[misc]
            for d in self._collection.find(filters)
        ]

    def list_all(self) -> list[T]:
        return [
            from_mongo_document(d, self.model_cls)  # type: ignore[misc]
            for d in self._collection.find({})
        ]


def _sorted_desc(items: list[T], key: str = "created_at") -> list[T]:
    return sorted(items, key=lambda m: getattr(m, key), reverse=True)


# ---------------------------------------------------------------------------
# Concrete repositories — one per protocol in app.repositories
# ---------------------------------------------------------------------------


class MongoTicketRepository(MongoDocumentRepository[Ticket]):
    collection_name = "tickets"
    model_cls = Ticket

    def list_by_project(self, project_id: str) -> list[Ticket]:
        return self.list_by_field("project_id", project_id)


class MongoAgentRunRepository(MongoDocumentRepository[AgentRun]):
    collection_name = "agent_runs"
    model_cls = AgentRun


class MongoArtifactRepository(MongoDocumentRepository[Artifact]):
    collection_name = "artifacts"
    model_cls = Artifact

    def list_by_ticket(self, ticket_id: str) -> list[Artifact]:
        return self.list_by_field("ticket_id", ticket_id)


class MongoProjectRepository(MongoDocumentRepository[Project]):
    collection_name = "projects"
    model_cls = Project


class MongoProjectContextRepository(MongoDocumentRepository[ProjectContext]):
    collection_name = "project_contexts"
    model_cls = ProjectContext
    # ProjectContext has no `id` field; project_id is the document key.
    id_field = "project_id"

    def get(self, project_id: str) -> ProjectContext | None:  # type: ignore[override]
        return self._get_by_id(project_id)


class MongoRequirementAnalysisRepository(MongoDocumentRepository[RequirementAnalysis]):
    collection_name = "requirement_analyses"
    model_cls = RequirementAnalysis

    def list_by_ticket(self, ticket_id: str) -> list[RequirementAnalysis]:
        return self.list_by_field("ticket_id", ticket_id)

    def get_latest_by_ticket(self, ticket_id: str) -> RequirementAnalysis | None:
        matches = self.list_by_ticket(ticket_id)
        if not matches:
            return None
        return max(matches, key=lambda a: a.created_at)

    def list_by_requirement(self, requirement_id: str) -> list[RequirementAnalysis]:
        return self.list_by_field("requirement_id", requirement_id)

    def get_latest_by_requirement(
        self, requirement_id: str
    ) -> RequirementAnalysis | None:
        matches = self.list_by_requirement(requirement_id)
        if not matches:
            return None
        return max(matches, key=lambda a: a.created_at)


class MongoRequirementRepository(MongoDocumentRepository[Requirement]):
    collection_name = "requirements"
    model_cls = Requirement

    def list_by_project(self, project_id: str) -> list[Requirement]:
        return self.list_by_field("project_id", project_id)


class MongoDevTaskRepository(MongoDocumentRepository[DevTask]):
    collection_name = "dev_tasks"
    model_cls = DevTask

    def list_by_project(self, project_id: str) -> list[DevTask]:
        return self.list_by_field("project_id", project_id)


class MongoSubtaskRepository(MongoDocumentRepository[Subtask]):
    collection_name = "subtasks"
    model_cls = Subtask

    def list_by_dev_task(self, dev_task_id: str) -> list[Subtask]:
        return self.list_by_field("dev_task_id", dev_task_id)


class MongoApprovalRepository(MongoDocumentRepository[Approval]):
    collection_name = "approvals"
    model_cls = Approval

    def list_by_project(self, project_id: str) -> list[Approval]:
        return _sorted_desc(self.list_by_field("project_id", project_id))

    def find_approved_for_target(
        self, target_type: str, target_id: str
    ) -> Approval | None:
        doc = self._collection.find_one(
            {
                "target_type": target_type,
                "target_id": target_id,
                "status": "approved",
            }
        )
        if doc is None:
            return None
        return from_mongo_document(doc, Approval)


class MongoAuditEventRepository(MongoDocumentRepository[AuditEvent]):
    collection_name = "audit_events"
    model_cls = AuditEvent

    def list_by_project(self, project_id: str) -> list[AuditEvent]:
        return _sorted_desc(self.list_by_field("project_id", project_id))


class MongoCodeRepositoryRepository(MongoDocumentRepository[CodeRepository]):
    collection_name = "code_repositories"
    model_cls = CodeRepository

    def list_by_project(self, project_id: str) -> list[CodeRepository]:
        return self.list_by_field("project_id", project_id)


class MongoRepoSafetyProfileRepository(MongoDocumentRepository[RepoSafetyProfile]):
    collection_name = "repo_safety_profiles"
    model_cls = RepoSafetyProfile

    def get_by_repo(self, code_repository_id: str) -> RepoSafetyProfile | None:
        doc = self._collection.find_one({"code_repository_id": code_repository_id})
        if doc is None:
            return None
        return from_mongo_document(doc, RepoSafetyProfile)


class MongoEpicRepository(MongoDocumentRepository[Epic]):
    collection_name = "epics"
    model_cls = Epic

    def list_by_project(self, project_id: str) -> list[Epic]:
        return self.list_by_field("project_id", project_id)

    def list_by_requirement(self, requirement_id: str) -> list[Epic]:
        return self.list_by_field("requirement_id", requirement_id)


class MongoCheckDefinitionRepository(MongoDocumentRepository[CheckDefinition]):
    collection_name = "check_definitions"
    model_cls = CheckDefinition

    def list_by_project(self, project_id: str) -> list[CheckDefinition]:
        return self.list_by_field("project_id", project_id)


class MongoCheckRunRepository(MongoDocumentRepository[CheckRun]):
    collection_name = "check_runs"
    model_cls = CheckRun

    def list_by_project(self, project_id: str) -> list[CheckRun]:
        return self.list_by_field("project_id", project_id)

    def list_by_target(self, target_type: str, target_id: str) -> list[CheckRun]:
        return self.list_by_fields(
            {"target_type": target_type, "target_id": target_id}
        )


class MongoToolRunnerDefinitionRepository(
    MongoDocumentRepository[ToolRunnerDefinition]
):
    collection_name = "tool_runner_definitions"
    model_cls = ToolRunnerDefinition

    def list_by_project(self, project_id: str) -> list[ToolRunnerDefinition]:
        return self.list_by_field("project_id", project_id)


class MongoToolRunRepository(MongoDocumentRepository[ToolRun]):
    collection_name = "tool_runs"
    model_cls = ToolRun

    def list_by_project(self, project_id: str) -> list[ToolRun]:
        return self.list_by_field("project_id", project_id)

    def list_by_target(self, target_type: str, target_id: str) -> list[ToolRun]:
        return self.list_by_fields(
            {"target_type": target_type, "target_id": target_id}
        )


class MongoPullRequestDraftRepository(MongoDocumentRepository[PullRequestDraft]):
    collection_name = "pull_request_drafts"
    model_cls = PullRequestDraft

    def list_by_project(self, project_id: str) -> list[PullRequestDraft]:
        return _sorted_desc(self.list_by_field("project_id", project_id))

    def list_by_dev_task(self, dev_task_id: str) -> list[PullRequestDraft]:
        return self.list_by_field("dev_task_id", dev_task_id)


class MongoPullRequestReviewRepository(MongoDocumentRepository[PullRequestReview]):
    collection_name = "pull_request_reviews"
    model_cls = PullRequestReview

    def list_by_pr_draft(self, pr_draft_id: str) -> list[PullRequestReview]:
        return _sorted_desc(self.list_by_field("pr_draft_id", pr_draft_id))


class MongoCIEventRepository(MongoDocumentRepository[CIEvent]):
    collection_name = "ci_events"
    model_cls = CIEvent

    def list_by_project(self, project_id: str) -> list[CIEvent]:
        return _sorted_desc(self.list_by_field("project_id", project_id))

    def list_by_pr_draft(self, pr_draft_id: str) -> list[CIEvent]:
        return _sorted_desc(self.list_by_field("pr_draft_id", pr_draft_id))

    def list_by_dev_task(self, dev_task_id: str) -> list[CIEvent]:
        return _sorted_desc(self.list_by_field("dev_task_id", dev_task_id))


class MongoCIAnalysisRepository(MongoDocumentRepository[CIAnalysis]):
    collection_name = "ci_analyses"
    model_cls = CIAnalysis

    def list_by_ci_event(self, ci_event_id: str) -> list[CIAnalysis]:
        return _sorted_desc(self.list_by_field("ci_event_id", ci_event_id))


class MongoIncidentRepository(MongoDocumentRepository[Incident]):
    collection_name = "incidents"
    model_cls = Incident

    def list_by_project(self, project_id: str) -> list[Incident]:
        return _sorted_desc(self.list_by_field("project_id", project_id))


class MongoIncidentAnalysisRepository(MongoDocumentRepository[IncidentAnalysis]):
    collection_name = "incident_analyses"
    model_cls = IncidentAnalysis

    def list_by_incident(self, incident_id: str) -> list[IncidentAnalysis]:
        return _sorted_desc(self.list_by_field("incident_id", incident_id))


class MongoMemoryLearningRunRepository(MongoDocumentRepository[MemoryLearningRun]):
    collection_name = "memory_learning_runs"
    model_cls = MemoryLearningRun

    def list_by_project(self, project_id: str) -> list[MemoryLearningRun]:
        return _sorted_desc(self.list_by_field("project_id", project_id))


class MongoProjectMemoryCandidateRepository(
    MongoDocumentRepository[ProjectMemoryCandidate]
):
    collection_name = "project_memory_candidates"
    model_cls = ProjectMemoryCandidate

    def list_by_project(self, project_id: str) -> list[ProjectMemoryCandidate]:
        return _sorted_desc(self.list_by_field("project_id", project_id))

    def list_by_learning_run(
        self, learning_run_id: str
    ) -> list[ProjectMemoryCandidate]:
        return _sorted_desc(self.list_by_field("learning_run_id", learning_run_id))


class MongoWorkspaceRepository(MongoDocumentRepository[Workspace]):
    collection_name = "workspaces"
    model_cls = Workspace

    def list_by_project(self, project_id: str) -> list[Workspace]:
        return self.list_by_field("project_id", project_id)

    def list_by_code_repository(self, code_repository_id: str) -> list[Workspace]:
        return self.list_by_field("code_repository_id", code_repository_id)


class MongoCommandDefinitionRepository(MongoDocumentRepository[CommandDefinition]):
    collection_name = "command_definitions"
    model_cls = CommandDefinition

    def list_by_project(self, project_id: str) -> list[CommandDefinition]:
        return self.list_by_field("project_id", project_id)

    def list_by_workspace(self, workspace_id: str) -> list[CommandDefinition]:
        return self.list_by_field("workspace_id", workspace_id)


class MongoCommandRunRepository(MongoDocumentRepository[CommandRun]):
    collection_name = "command_runs"
    model_cls = CommandRun

    def list_by_project(self, project_id: str) -> list[CommandRun]:
        return self.list_by_field("project_id", project_id)

    def list_by_workspace(self, workspace_id: str) -> list[CommandRun]:
        return self.list_by_field("workspace_id", workspace_id)

    def list_by_target(self, target_type: str, target_id: str) -> list[CommandRun]:
        return self.list_by_fields(
            {"target_type": target_type, "target_id": target_id}
        )


class MongoWorkspaceBranchRepository(MongoDocumentRepository[WorkspaceBranch]):
    collection_name = "workspace_branches"
    model_cls = WorkspaceBranch

    def list_by_workspace(self, workspace_id: str) -> list[WorkspaceBranch]:
        return self.list_by_field("workspace_id", workspace_id)

    def list_by_project(self, project_id: str) -> list[WorkspaceBranch]:
        return self.list_by_field("project_id", project_id)


class MongoGitCommitRecordRepository(MongoDocumentRepository[GitCommitRecord]):
    collection_name = "git_commit_records"
    model_cls = GitCommitRecord

    def list_by_branch(self, branch_id: str) -> list[GitCommitRecord]:
        return self.list_by_field("workspace_branch_id", branch_id)

    def list_by_workspace(self, workspace_id: str) -> list[GitCommitRecord]:
        return self.list_by_field("workspace_id", workspace_id)


class MongoReviewFeedbackRepository(MongoDocumentRepository[ReviewFeedback]):
    collection_name = "review_feedback"
    model_cls = ReviewFeedback

    def list_by_pr_draft(self, pr_draft_id: str) -> list[ReviewFeedback]:
        return _sorted_desc(self.list_by_field("pr_draft_id", pr_draft_id))

    def list_by_pr_review(self, pr_review_id: str) -> list[ReviewFeedback]:
        return _sorted_desc(self.list_by_field("pr_review_id", pr_review_id))

    def list_by_project(self, project_id: str) -> list[ReviewFeedback]:
        return _sorted_desc(self.list_by_field("project_id", project_id))


class MongoRevisionWorkItemRepository(MongoDocumentRepository[RevisionWorkItem]):
    collection_name = "revision_work_items"
    model_cls = RevisionWorkItem

    def list_by_pr_draft(self, pr_draft_id: str) -> list[RevisionWorkItem]:
        return _sorted_desc(self.list_by_field("pr_draft_id", pr_draft_id))

    def list_by_feedback(self, feedback_id: str) -> list[RevisionWorkItem]:
        return _sorted_desc(self.list_by_field("review_feedback_id", feedback_id))

    def list_by_project(self, project_id: str) -> list[RevisionWorkItem]:
        return _sorted_desc(self.list_by_field("project_id", project_id))


# ---------------------------------------------------------------------------
# Index management
# ---------------------------------------------------------------------------


_INDEX_PLAN: dict[str, list[Any]] = {
    "tickets": ["project_id"],
    "artifacts": ["ticket_id"],
    "requirement_analyses": ["ticket_id", "requirement_id"],
    "requirements": ["project_id"],
    "dev_tasks": ["project_id"],
    "subtasks": ["dev_task_id"],
    "approvals": [
        "project_id",
        [("target_type", 1), ("target_id", 1), ("status", 1)],
    ],
    "audit_events": ["project_id", "created_at"],
    "code_repositories": ["project_id"],
    "repo_safety_profiles": ["code_repository_id"],
    "epics": ["project_id", "requirement_id"],
    "check_definitions": ["project_id"],
    "check_runs": [
        "project_id",
        [("target_type", 1), ("target_id", 1)],
    ],
    "tool_runner_definitions": ["project_id"],
    "tool_runs": [
        "project_id",
        [("target_type", 1), ("target_id", 1)],
    ],
    "pull_request_drafts": ["project_id", "dev_task_id"],
    "pull_request_reviews": ["pr_draft_id"],
    "ci_events": ["project_id", "pr_draft_id", "dev_task_id"],
    "ci_analyses": ["ci_event_id"],
    "incidents": ["project_id"],
    "incident_analyses": ["incident_id"],
    "memory_learning_runs": ["project_id"],
    "project_memory_candidates": ["project_id", "learning_run_id"],
    "workspaces": ["project_id", "code_repository_id"],
    "command_definitions": ["project_id", "workspace_id"],
    "command_runs": [
        "project_id",
        "workspace_id",
        [("target_type", 1), ("target_id", 1)],
    ],
    "workspace_branches": ["workspace_id", "project_id"],
    "git_commit_records": ["workspace_branch_id", "workspace_id"],
    "review_feedback": ["pr_draft_id", "pr_review_id", "project_id"],
    "revision_work_items": [
        "pr_draft_id",
        "pr_review_id",
        "project_id",
        "review_feedback_id",
    ],
}


def _ensure_indexes(db: Any) -> None:
    """Create the indexes listed in :data:`_INDEX_PLAN`. Idempotent."""
    for collection_name, indexes in _INDEX_PLAN.items():
        coll = db[collection_name]
        for spec in indexes:
            if isinstance(spec, str):
                coll.create_index(spec, background=True)
            else:
                coll.create_index(spec, background=True)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_mongo_repositories():
    """Build a :class:`Repositories` container backed by MongoDB.

    Imports ``pymongo`` lazily so memory and Firestore providers do not
    require it. Connects with the configured timeouts and pings the server
    so an unreachable Mongo fails fast at startup with a clear error.
    """
    try:
        import pymongo
        from pymongo.errors import PyMongoError
    except ImportError as exc:  # pragma: no cover - exercised only without pymongo
        raise RuntimeError(
            "REPOSITORY_PROVIDER=local_document requires pymongo. "
            "Install with: pip install '.[local_document]'"
        ) from exc

    # Local import to avoid a circular import at module load time.
    from .repositories import Repositories

    redacted = _redact_mongo_uri(config.MONGODB_URI)
    try:
        client = pymongo.MongoClient(
            config.MONGODB_URI,
            connectTimeoutMS=config.MONGODB_CONNECT_TIMEOUT_MS,
            serverSelectionTimeoutMS=config.MONGODB_SERVER_SELECTION_TIMEOUT_MS,
            tz_aware=True,
        )
        client.admin.command("ping")
    except PyMongoError as exc:
        raise RuntimeError(
            f"MongoDB unreachable at {redacted} (database={config.MONGODB_DATABASE}): {exc}"
        ) from exc

    db = client[config.MONGODB_DATABASE]
    _ensure_indexes(db)

    return Repositories(
        ticket=MongoTicketRepository(db),
        agent_run=MongoAgentRunRepository(db),
        artifact=MongoArtifactRepository(db),
        project=MongoProjectRepository(db),
        project_context=MongoProjectContextRepository(db),
        requirement_analysis=MongoRequirementAnalysisRepository(db),
        requirement=MongoRequirementRepository(db),
        dev_task=MongoDevTaskRepository(db),
        subtask=MongoSubtaskRepository(db),
        approval=MongoApprovalRepository(db),
        audit_event=MongoAuditEventRepository(db),
        code_repository=MongoCodeRepositoryRepository(db),
        repo_safety_profile=MongoRepoSafetyProfileRepository(db),
        epic=MongoEpicRepository(db),
        check_definition=MongoCheckDefinitionRepository(db),
        check_run=MongoCheckRunRepository(db),
        tool_runner_definition=MongoToolRunnerDefinitionRepository(db),
        tool_run=MongoToolRunRepository(db),
        pr_draft=MongoPullRequestDraftRepository(db),
        pr_review=MongoPullRequestReviewRepository(db),
        ci_event=MongoCIEventRepository(db),
        ci_analysis=MongoCIAnalysisRepository(db),
        incident=MongoIncidentRepository(db),
        incident_analysis=MongoIncidentAnalysisRepository(db),
        memory_learning_run=MongoMemoryLearningRunRepository(db),
        memory_candidate=MongoProjectMemoryCandidateRepository(db),
        workspace=MongoWorkspaceRepository(db),
        command_definition=MongoCommandDefinitionRepository(db),
        command_run=MongoCommandRunRepository(db),
        workspace_branch=MongoWorkspaceBranchRepository(db),
        git_commit_record=MongoGitCommitRecordRepository(db),
        review_feedback=MongoReviewFeedbackRepository(db),
        revision_work_item=MongoRevisionWorkItemRepository(db),
    )
