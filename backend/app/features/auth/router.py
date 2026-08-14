from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.features.auth.schemas import LoginRequest, TokenResponse, UserResponse
from app.features.auth.service import authenticate

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    username = authenticate(body.username, body.password)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    return TokenResponse(access_token=create_access_token(username))


@router.get("/me", response_model=UserResponse)
def me(username: Annotated[str, Depends(get_current_user)]) -> UserResponse:
    return UserResponse(username=username)
