from datetime import datetime

from pydantic import BaseModel


class QualityMetricSnapshot(BaseModel):
    id: str
    project_id: str
    trial_id: str | None = None
    source_type: str = "project"
    source_id: str | None = None
    metrics: dict = {}
    summary: str | None = None
    created_at: datetime
    updated_at: datetime


class QualityMetricsResponse(BaseModel):
    project_id: str
    trial_id: str | None = None
    metrics: dict
    summary: str = ""
