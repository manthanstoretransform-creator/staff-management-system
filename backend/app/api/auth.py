from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.user import UserRead, DevLoginRequest, LoginRequest
from app.schemas.token import TokenPair
from app.services.auth import AuthService
from app.models.user import User
from app.core.security import get_current_user
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post(
    "/login",
    response_model=TokenPair,
    summary="Sign in with Hubstaff credentials",
    description=(
        "Desktop and Swagger clients use this endpoint. The backend securely "
        "forwards the supplied credentials to the configured Hubstaff provider "
        "login URL, provisions the local user when needed, and returns an SMS JWT."
    ),
    responses={
        401: {"description": "Provider rejected the supplied credentials"},
        502: {"description": "Provider rejected or blocked the backend request"},
        503: {"description": "Provider is unavailable"},
        504: {"description": "Provider timed out"},
    },
)
async def login(payload: LoginRequest, db: Session = Depends(get_db)):
    try:
        return await AuthService.login_exchange(db, payload.username, payload.password)
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication exchange failed: {str(e)}")

@router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/dev-login", response_model=TokenPair)
def dev_login(payload: DevLoginRequest, db: Session = Depends(get_db)):
    if settings.ENV == "production":
        raise HTTPException(status_code=404)
    return AuthService.dev_login(db, payload.email, payload.password)
