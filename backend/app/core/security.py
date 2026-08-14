from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Valid bcrypt hash used only to keep verify timing similar when a user is missing.
DUMMY_PASSWORD_HASH = (
    "$2b$12$d2KUQzgffuDXDFpizotfyecZPvTvMOmHavBvrVczWDwmFMpJvHaWy"
)


def verify_password(plain: str, hashed: str) -> bool:
    return bool(pwd_context.verify(plain, hashed))


def create_access_token(subject: str) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(days=settings.jwt_expire_days)
    payload: dict[str, object] = {"sub": subject, "exp": expire}
    return str(
        jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    )


def decode_access_token(token: str) -> str | None:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        return None
    subject = payload.get("sub")
    if not isinstance(subject, str) or subject == "":
        return None
    return subject
