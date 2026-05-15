from fastapi import APIRouter, Depends

from ..auth import require_auth
from ..models import IntegrationRunCreate, IntegrationRunResult
from ..services import integration_runs

router = APIRouter()


@router.post(
    "/workspaces/{workspace_id}/integration-runs",
    response_model=IntegrationRunResult,
    status_code=201,
)
def create_integration_run(
    workspace_id: str,
    body: IntegrationRunCreate,
    current_user: str = Depends(require_auth),
):
    return integration_runs.create_integration_run(workspace_id, body, current_user)
