import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_returns_token_and_user(client: AsyncClient, register_payload) -> None:
    payload = register_payload()
    response = await client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == payload["email"]
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email(client: AsyncClient, register_payload) -> None:
    payload = register_payload()
    first = await client.post("/api/auth/register", json=payload)
    assert first.status_code == 201
    second = await client.post("/api/auth/register", json=payload)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "email_taken"


@pytest.mark.asyncio
async def test_register_normalizes_email_case(client: AsyncClient, register_payload) -> None:
    payload = register_payload(email="Casey@University.EDU")
    response = await client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    assert response.json()["user"]["email"] == "casey@university.edu"


@pytest.mark.asyncio
async def test_register_rejects_weak_password(client: AsyncClient, register_payload) -> None:
    response = await client.post("/api/auth/register", json=register_payload(password="password"))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, register_payload) -> None:
    payload = register_payload()
    await client.post("/api/auth/register", json=payload)
    response = await client.post(
        "/api/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert response.status_code == 200
    assert response.json()["user"]["email"] == payload["email"]


@pytest.mark.asyncio
async def test_login_rejects_wrong_password(client: AsyncClient, register_payload) -> None:
    payload = register_payload()
    await client.post("/api/auth/register", json=payload)
    response = await client.post(
        "/api/auth/login",
        json={"email": payload["email"], "password": "WrongPass1"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


@pytest.mark.asyncio
async def test_login_unknown_email_does_not_leak_existence(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/login",
        json={"email": "nobody@university.edu", "password": "Secret123"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/users/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


@pytest.mark.asyncio
async def test_me_rejects_invalid_token(client: AsyncClient) -> None:
    response = await client.get("/api/users/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


@pytest.mark.asyncio
async def test_update_profile(client: AsyncClient, auth_header) -> None:
    headers, user = await auth_header()
    response = await client.patch(
        "/api/users/me",
        json={"university": "MIT", "major": "Electrical Engineering"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == user["id"]
    assert body["university"] == "MIT"
    assert body["major"] == "Electrical Engineering"
