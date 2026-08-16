from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
) -> str:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized
    subject = decode_access_token(credentials.credentials)
    if subject is None:
        raise unauthorized
    return subject


def require_alice(
    username: Annotated[str, Depends(get_current_user)],
) -> str:
    if username != "alice":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Observability is only available to Alice",
        )
    return username
