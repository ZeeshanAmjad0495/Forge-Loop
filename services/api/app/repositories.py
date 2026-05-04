from typing import Protocol

from . import config
from .models import AgentRun, Artifact, Ticket


class TicketRepository(Protocol):
    def save(self, ticket: Ticket) -> None: ...
    def get(self, ticket_id: str) -> Ticket | None: ...


class InMemoryTicketRepository:
    def __init__(self) -> None:
        self._store: dict[str, Ticket] = {}

    def save(self, ticket: Ticket) -> None:
        self._store[ticket.id] = ticket

    def get(self, ticket_id: str) -> Ticket | None:
        return self._store.get(ticket_id)


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


def get_repositories() -> tuple[TicketRepository, AgentRunRepository, ArtifactRepository]:
    if config.REPOSITORY_PROVIDER == "memory":
        return (
            InMemoryTicketRepository(),
            InMemoryAgentRunRepository(),
            InMemoryArtifactRepository(),
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
        )
    raise ValueError(
        f"Unknown REPOSITORY_PROVIDER: {config.REPOSITORY_PROVIDER!r}. Supported: memory, firestore"
    )
