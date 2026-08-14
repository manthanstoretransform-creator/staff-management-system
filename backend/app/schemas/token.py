from pydantic import BaseModel
from app.schemas.user import UserRead

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserRead
