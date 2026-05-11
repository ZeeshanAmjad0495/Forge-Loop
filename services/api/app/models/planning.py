from pydantic import BaseModel

from .agents import AgentRun
from .artifacts import Artifact


class PlanningRunResponse(BaseModel):
    agent_run: AgentRun
    artifact: Artifact


class PlanningRunCreate(BaseModel):
    provider: str | None = None
