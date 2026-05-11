from fastapi import APIRouter, Body, Depends

from ..auth import require_auth
from ..models import (
    OpenHandsPreparePackageRequest,
    OpenHandsPrepareResponse,
    OpenHandsRecordResultRequest,
    ToolRun,
)
from ..services import openhands_workflow

router = APIRouter()


@router.post(
    "/dev-tasks/{dev_task_id}/openhands/prepare",
    response_model=OpenHandsPrepareResponse,
    status_code=201,
)
def prepare_openhands_package(
    dev_task_id: str,
    body: OpenHandsPreparePackageRequest | None = Body(default=None),
    current_user: str = Depends(require_auth),
):
    return openhands_workflow.prepare_package(dev_task_id, body, current_user)


@router.post(
    "/tool-runs/{tool_run_id}/openhands/record-result",
    response_model=ToolRun,
)
def record_openhands_result(
    tool_run_id: str,
    body: OpenHandsRecordResultRequest,
    current_user: str = Depends(require_auth),
):
    return openhands_workflow.record_result(tool_run_id, body, current_user)
