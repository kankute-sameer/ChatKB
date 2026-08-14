from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from jose import jwt

from app.core.config import get_settings
from app.tests.conftest import TEST_PASSWORD, TEST_USERNAME


def test_login_success_returns_token(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert body["access_token"] != ""


def test_login_wrong_password_returns_401(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"username": TEST_USERNAME, "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


def test_login_unknown_username_returns_401(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"username": "unknown", "password": TEST_PASSWORD},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


def test_me_with_valid_token_returns_username(client: TestClient) -> None:
    login = client.post(
        "/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    token = login.json()["access_token"]
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"username": TEST_USERNAME}


def test_me_with_no_token_returns_401(client: TestClient) -> None:
    response = client.get("/auth/me")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_me_with_garbage_token_returns_401(client: TestClient) -> None:
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_me_with_expired_token_returns_401(client: TestClient) -> None:
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": TEST_USERNAME,
            "exp": datetime.now(UTC) - timedelta(hours=1),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
