from fastapi import APIRouter, Body, Depends

from ..auth import require_auth
from ..models import (
    AiderExecuteRequest,
    AiderPreparePackageRequest,
    AiderRecordResultRequest,
    ToolRun,
)
from ..services import aider_execution, aider_workflow

router = APIRouter()


@router.post(
    "/dev-tasks/{dev_task_id}/aider/prepare",
    response_model=ToolRun,
    status_code=201,
)
def prepare_aider_package(
    dev_task_id: str,
    body: AiderPreparePackageRequest | None = Body(default=None),
    current_user: str = Depends(require_auth),
):
    body = body or AiderPreparePackageRequest()
    return aider_workflow.prepare_package(
        dev_task_id,
        body.tool_runner_definition_id,
        body.code_repository_id,
        current_user,
    )


@router.post(
    "/dev-tasks/{dev_task_id}/aider/execute",
    response_model=ToolRun,
)
def execute_aider(
    dev_task_id: str,
    body: AiderExecuteRequest,
    current_user: str = Depends(require_auth),
):
    return aider_execution.execute(dev_task_id, body, current_user)


@router.post(
    "/tool-runs/{tool_run_id}/aider/record-result",
    response_model=ToolRun,
)
def record_aider_result(
    tool_run_id: str,
    body: AiderRecordResultRequest,
    current_user: str = Depends(require_auth),
):
    return aider_workflow.record_result(
        tool_run_id, body.summary, body.output, body.conclusion, current_user
    )
