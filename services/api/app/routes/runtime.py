"""Runtime inspection routes (Release 8).

`GET /runtime/profile`  — sanitized runtime profile summary (Task 41).
`GET /runtime/config`   — resolved runtime configuration view (Task 45).
`GET /runtime/cloud-compatibility` — cloud-profile compatibility check (Task 46).

None of these endpoints mutate state, make network calls, or expose
secret values.
"""

from fastapi import APIRouter, Depends

from ..auth import require_auth
from ..services.cloud_compatibility import build_cloud_compatibility_report
from ..services.runtime_config import build_resolved_runtime_config
from ..services.runtime_profile import build_runtime_summary

router = APIRouter()


@router.get("/runtime/profile")
def get_runtime_profile(_: str = Depends(require_auth)) -> dict:
    return build_runtime_summary()


@router.get("/runtime/config")
def get_runtime_config(_: str = Depends(require_auth)) -> dict:
    return build_resolved_runtime_config()


@router.get("/runtime/cloud-compatibility")
def get_runtime_cloud_compatibility(_: str = Depends(require_auth)) -> dict:
    return build_cloud_compatibility_report()
