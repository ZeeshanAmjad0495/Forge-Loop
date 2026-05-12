"""Cost-per-feature reporting (Release 10, Task 61).

Advisory cost summaries built on top of the Release 9 ``CostRecord`` data.
Not billing. Not invoices. Best-effort grouping by provider / model /
source_type.
"""

from __future__ import annotations

from collections import defaultdict

from ..models import CostRecord
from ..repositories import CostRecordRepository


def _empty_report() -> dict:
    return {
        "total_estimated_cost_usd": 0.0,
        "by_provider": {},
        "by_model": {},
        "by_source_type": {},
        "by_workflow_type": {},
        "record_count": 0,
        "currency": "USD",
        "notes": [],
    }


def _summarize(records: list[CostRecord]) -> dict:
    report = _empty_report()
    if not records:
        return report

    total = 0.0
    by_provider: dict[str, float] = defaultdict(float)
    by_model: dict[str, float] = defaultdict(float)
    by_source: dict[str, float] = defaultdict(float)
    by_workflow: dict[str, float] = defaultdict(float)
    for r in records:
        cost = float(r.estimated_total_cost_usd or 0.0)
        total += cost
        by_provider[r.provider] += cost
        by_model[r.model] += cost
        by_source[r.source_type] += cost
        by_workflow[r.workflow_type] += cost

    report["total_estimated_cost_usd"] = round(total, 6)
    report["by_provider"] = {k: round(v, 6) for k, v in by_provider.items()}
    report["by_model"] = {k: round(v, 6) for k, v in by_model.items()}
    report["by_source_type"] = {k: round(v, 6) for k, v in by_source.items()}
    report["by_workflow_type"] = {k: round(v, 6) for k, v in by_workflow.items()}
    report["record_count"] = len(records)
    # Currency: take the first record's currency. If a project mixes currencies,
    # leave a note.
    currencies = {r.currency for r in records if r.currency}
    if len(currencies) == 1:
        report["currency"] = next(iter(currencies))
    elif len(currencies) > 1:
        report["currency"] = "MIXED"
        report["notes"].append(
            "Cost records use multiple currencies; totals sum nominal values only."
        )
    return report


def project_cost_report(
    cost_record_repo: CostRecordRepository, *, project_id: str
) -> dict:
    records = cost_record_repo.list_by_project(project_id)
    return _summarize(records)


def cost_report_for_source(
    cost_record_repo: CostRecordRepository,
    *,
    project_id: str,
    source_type: str,
    source_id: str,
) -> dict:
    # Filter to the project to keep cross-project records from leaking.
    project_records = cost_record_repo.list_by_project(project_id)
    records = [
        r
        for r in project_records
        if r.source_type == source_type and r.source_id == source_id
    ]
    report = _summarize(records)
    if not records:
        report["notes"].append(
            f"No cost records linked to {source_type}/{source_id}; report is empty by design."
        )
    return report
