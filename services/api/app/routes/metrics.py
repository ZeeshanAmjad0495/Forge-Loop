"""Task 82: Prometheus-text metrics endpoint.

Aggregate counters/summaries only — no secrets/tokens/prompts/PII.
Auth is required (consistent with the other runtime endpoints; ForgeLoop
exposes no anonymous surface). Returns 404 when metrics are disabled.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from .. import config
from ..auth import require_auth
from ..services.metrics import render

router = APIRouter()


@router.get("/metrics", response_class=PlainTextResponse)
def get_metrics(_: str = Depends(require_auth)) -> PlainTextResponse:
    if not (config.OBSERVABILITY_ENABLED and config.METRICS_ENABLED):
        raise HTTPException(status_code=404, detail="Metrics are disabled")
    return PlainTextResponse(
        render(), media_type="text/plain; version=0.0.4; charset=utf-8"
    )
