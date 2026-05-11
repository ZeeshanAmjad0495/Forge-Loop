from fastapi import APIRouter, Depends

from ..auth import require_auth
from ..llm import get_default_provider_name, list_provider_status
from ..models import ProviderInfo, ProvidersResponse

router = APIRouter()


@router.get("/llm/providers", response_model=ProvidersResponse)
def get_providers(_: str = Depends(require_auth)):
    return ProvidersResponse(
        default_provider=get_default_provider_name(),
        providers=[ProviderInfo(**p) for p in list_provider_status()],
    )
