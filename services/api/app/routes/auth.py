from fastapi import APIRouter, Depends, HTTPException

from ..auth import create_access_token, require_auth, verify_credentials
from ..models import LoginRequest, LoginResponse, MeResponse

router = APIRouter()


@router.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest):
    if not verify_credentials(body.email, body.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    try:
        token = create_access_token(body.email)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Auth misconfigured")
    return LoginResponse(access_token=token)


@router.get("/auth/me", response_model=MeResponse)
def me(current_user: str = Depends(require_auth)):
    return MeResponse(email=current_user)
