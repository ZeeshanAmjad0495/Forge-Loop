"""Small, shared route-layer helpers.

Used only where the S2 audit explicitly called out duplication: ~30
404-or-load sites and 8 provider-resolution sites. Sites with idiosyncratic
404 detail strings keep their inline form to preserve byte-identical
HTTP responses.
"""

from fastapi import HTTPException

from ..llm import ProviderError, get_default_provider_name, get_provider_by_name


def load_or_404(repo, object_id: str, label: str):
    obj = repo.get(object_id)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return obj


def require_project(project_repo, project_id: str):
    return load_or_404(project_repo, project_id, "Project")


def resolve_provider_or_400(provider_name: str | None):
    name = provider_name or get_default_provider_name()
    try:
        return get_provider_by_name(name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ProviderError as e:
        raise HTTPException(status_code=400, detail=str(e))
