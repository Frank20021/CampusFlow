import pytest
from httpx import AsyncClient


async def _create_group(client: AsyncClient, headers: dict, **overrides) -> dict:
    payload = {
        "name": "Algorithms Night",
        "description": "Weekly problem solving",
        "course_code": "CS201",
    }
    payload.update(overrides)
    response = await client.post("/api/groups", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_create_group_makes_creator_owner(client: AsyncClient, auth_header) -> None:
    headers, user = await auth_header()
    group = await _create_group(client, headers)
    assert group["my_role"] == "owner"
    assert group["owner_id"] == user["id"]
    assert group["member_count"] == 1


@pytest.mark.asyncio
async def test_list_groups_discover_and_mine(client: AsyncClient, auth_header) -> None:
    owner_headers, _ = await auth_header(email="owner@university.edu")
    other_headers, _ = await auth_header(email="other@university.edu")
    await _create_group(client, owner_headers, name="Owner Group")

    discover = await client.get("/api/groups", headers=other_headers)
    assert discover.status_code == 200
    assert discover.json()["total"] == 1
    assert discover.json()["items"][0]["my_role"] is None

    mine = await client.get("/api/groups", params={"mine": True}, headers=other_headers)
    assert mine.json()["total"] == 0

    owner_mine = await client.get("/api/groups", params={"mine": True}, headers=owner_headers)
    assert owner_mine.json()["total"] == 1


@pytest.mark.asyncio
async def test_join_and_leave_group(client: AsyncClient, auth_header) -> None:
    owner_headers, _ = await auth_header(email="owner@university.edu")
    member_headers, member = await auth_header(email="member@university.edu")
    group = await _create_group(client, owner_headers)

    joined = await client.post(f"/api/groups/{group['id']}/join", headers=member_headers)
    assert joined.status_code == 200
    assert joined.json()["my_role"] == "member"
    assert joined.json()["member_count"] == 2

    duplicate = await client.post(f"/api/groups/{group['id']}/join", headers=member_headers)
    assert duplicate.status_code == 409

    left = await client.delete(f"/api/groups/{group['id']}/leave", headers=member_headers)
    assert left.status_code == 204

    after = await client.get(f"/api/groups/{group['id']}", headers=owner_headers)
    assert after.json()["member_count"] == 1


@pytest.mark.asyncio
async def test_owner_cannot_leave(client: AsyncClient, auth_header) -> None:
    headers, _ = await auth_header()
    group = await _create_group(client, headers)
    response = await client.delete(f"/api/groups/{group['id']}/leave", headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "owner_cannot_leave"


@pytest.mark.asyncio
async def test_non_member_cannot_list_members(client: AsyncClient, auth_header) -> None:
    owner_headers, _ = await auth_header(email="owner@university.edu")
    outsider_headers, _ = await auth_header(email="outsider@university.edu")
    group = await _create_group(client, owner_headers)
    response = await client.get(f"/api/groups/{group['id']}/members", headers=outsider_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_a_member"


@pytest.mark.asyncio
async def test_member_list_is_visible_to_members(client: AsyncClient, auth_header) -> None:
    owner_headers, owner = await auth_header(email="owner@university.edu")
    member_headers, member = await auth_header(email="member@university.edu")
    group = await _create_group(client, owner_headers)
    await client.post(f"/api/groups/{group['id']}/join", headers=member_headers)
    response = await client.get(f"/api/groups/{group['id']}/members", headers=member_headers)
    assert response.status_code == 200
    emails = {item["email"] for item in response.json()}
    assert owner["email"] in emails
    assert member["email"] in emails


@pytest.mark.asyncio
async def test_member_cannot_update_or_delete_group(client: AsyncClient, auth_header) -> None:
    owner_headers, _ = await auth_header(email="owner@university.edu")
    member_headers, _ = await auth_header(email="member@university.edu")
    group = await _create_group(client, owner_headers)
    await client.post(f"/api/groups/{group['id']}/join", headers=member_headers)

    update = await client.patch(
        f"/api/groups/{group['id']}",
        json={"name": "Hijacked"},
        headers=member_headers,
    )
    assert update.status_code == 403

    delete = await client.delete(f"/api/groups/{group['id']}", headers=member_headers)
    assert delete.status_code == 403


@pytest.mark.asyncio
async def test_owner_can_update_and_delete_group(client: AsyncClient, auth_header) -> None:
    headers, _ = await auth_header()
    group = await _create_group(client, headers)
    updated = await client.patch(
        f"/api/groups/{group['id']}",
        json={"name": "Updated Circle"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated Circle"

    deleted = await client.delete(f"/api/groups/{group['id']}", headers=headers)
    assert deleted.status_code == 204
    missing = await client.get(f"/api/groups/{group['id']}", headers=headers)
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_owner_can_promote_and_remove_member(client: AsyncClient, auth_header) -> None:
    owner_headers, _ = await auth_header(email="owner@university.edu")
    member_headers, member = await auth_header(email="member@university.edu")
    group = await _create_group(client, owner_headers)
    await client.post(f"/api/groups/{group['id']}/join", headers=member_headers)

    promoted = await client.patch(
        f"/api/groups/{group['id']}/members/{member['id']}",
        json={"role": "admin"},
        headers=owner_headers,
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "admin"

    removed = await client.delete(
        f"/api/groups/{group['id']}/members/{member['id']}",
        headers=owner_headers,
    )
    assert removed.status_code == 204


@pytest.mark.asyncio
async def test_cannot_remove_owner(client: AsyncClient, auth_header) -> None:
    owner_headers, owner = await auth_header(email="owner@university.edu")
    member_headers, _ = await auth_header(email="member@university.edu")
    group = await _create_group(client, owner_headers)
    await client.post(f"/api/groups/{group['id']}/join", headers=member_headers)
    response = await client.delete(
        f"/api/groups/{group['id']}/members/{owner['id']}",
        headers=owner_headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "cannot_remove_owner"


@pytest.mark.asyncio
async def test_unknown_group_is_404(client: AsyncClient, auth_header) -> None:
    headers, _ = await auth_header()
    response = await client.get(
        "/api/groups/11111111-1111-1111-1111-111111111111",
        headers=headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_groups_require_auth(client: AsyncClient) -> None:
    response = await client.get("/api/groups")
    assert response.status_code == 401
