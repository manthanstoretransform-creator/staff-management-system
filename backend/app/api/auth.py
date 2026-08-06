from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.user import HubstaffLoginPayload, UserRead
from app.schemas.token import TokenPair
from app.services.auth import AuthService
from app.models.user import User
from app.core.security import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=TokenPair)
def login(payload: HubstaffLoginPayload, db: Session = Depends(get_db)):
    try:
        return AuthService.login_exchange(db, payload)
    except Exception as e:
        # It's helpful to log this or raise a clean 500 error if something goes wrong
        raise HTTPException(status_code=500, detail=f"Authentication exchange failed: {str(e)}")

@router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
