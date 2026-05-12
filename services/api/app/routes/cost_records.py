from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import require_auth
from ..models import CostRecord, CostRecordCreate
from ..repositories_state import cost_record_repo, project_repo
from ..services.cost_tracking import record_cost

router = APIRouter()


@router.get(
    "/projects/{project_id}/cost-records",
    response_model=list[CostRecord],
)
def list_cost_records(
    project_id: str,
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
    workflow_type: str | None = Query(default=None),
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if workflow_type is not None:
        return cost_record_repo.list_by_workflow(project_id, workflow_type)
    if provider is not None or model is not None:
        return cost_record_repo.list_by_provider_model(
            project_id, provider=provider, model=model
        )
    return cost_record_repo.list_by_project(project_id)


@router.get(
    "/cost-records/{cost_record_id}",
    response_model=CostRecord,
)
def get_cost_record(
    cost_record_id: str,
    current_user: str = Depends(require_auth),
):
    record = cost_record_repo.get(cost_record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Cost record not found")
    return record


@router.post(
    "/projects/{project_id}/cost-records",
    response_model=CostRecord,
    status_code=201,
)
def create_cost_record(
    project_id: str,
    body: CostRecordCreate,
    current_user: str = Depends(require_auth),
):
    if project_repo.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return record_cost(
        cost_record_repo,
        project_id=project_id,
        source_type=body.source_type,
        source_id=body.source_id,
        workflow_type=body.workflow_type,
        provider=body.provider,
        model=body.model,
        input_tokens=body.input_tokens,
        output_tokens=body.output_tokens,
        cached_input_tokens=body.cached_input_tokens,
        estimated_input_cost_usd=body.estimated_input_cost_usd,
        estimated_output_cost_usd=body.estimated_output_cost_usd,
        estimated_cached_input_cost_usd=body.estimated_cached_input_cost_usd,
        currency=body.currency,
        metadata=body.metadata,
    )
