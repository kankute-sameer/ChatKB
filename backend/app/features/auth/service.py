from app.core.config import get_settings
from app.core.security import DUMMY_PASSWORD_HASH, verify_password


def authenticate(username: str, password: str) -> str | None:
    settings = get_settings()
    hashed = settings.auth_users.get(username)
    if hashed is None:
        verify_password(password, DUMMY_PASSWORD_HASH)
        return None
    if not verify_password(password, hashed):
        return None
    return username
