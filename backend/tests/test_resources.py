import pytest
from httpx import AsyncClient


async def _create_group(client: AsyncClient, headers: dict, name: str = "Reading Group") -> dict:
    response = await client.post(
        "/api/groups", json={"name": name, "course_code": "CS700"}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_resource(client: AsyncClient, headers: dict, group_id: str, **overrides) -> dict:
    payload = {"title": "Lecture slides", "url": "https://example.edu/slides.pdf"}
    payload.update(overrides)
    response = await client.post(
        f"/api/groups/{group_id}/resources", json=payload, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
async def resource_group(client: AsyncClient, auth_header):
    owner_headers, owner = await auth_header(email="res-owner@university.edu")
    member_headers, member = await auth_header(email="res-member@university.edu")
    outsider_headers, _ = await auth_header(email="res-outsider@university.edu")
    group = await _create_group(client, owner_headers)
    join = await client.post(f"/api/groups/{group['id']}/join", headers=member_headers)
    assert join.status_code == 200
    return {
        "group": group,
        "owner_headers": owner_headers,
        "owner": owner,
        "member_headers": member_headers,
        "member": member,
        "outsider_headers": outsider_headers,
    }


@pytest.mark.asyncio
async def test_share_a_link(client: AsyncClient, resource_group) -> None:
    ctx = resource_group
    created = await _create_resource(
        client,
        ctx["member_headers"],
        ctx["group"]["id"],
        description="Weeks 1-4",
    )

    assert created["title"] == "Lecture slides"
    assert created["url"] == "https://example.edu/slides.pdf"
    assert created["description"] == "Weeks 1-4"
    assert created["creator"]["email"] == ctx["member"]["email"]
    assert created["can_delete"] is True


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(document.cookie)",
        "JavaScript:alert(1)",
        "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
        "file:///etc/passwd",
        "not a url at all",
        "https://",
    ],
)
@pytest.mark.asyncio
async def test_dangerous_or_malformed_links_rejected(
    client: AsyncClient, resource_group, url: str
) -> None:
    """Resources render as anchors, so a `javascript:` URL would be stored XSS."""
    ctx = resource_group
    response = await client.post(
        f"/api/groups/{ctx['group']['id']}/resources",
        json={"title": "Sneaky", "url": url},
        headers=ctx["owner_headers"],
    )
    assert response.status_code == 422, url


@pytest.mark.parametrize(
    "url",
    ["http://example.edu/notes", "https://example.edu/a?b=c&d=e#frag"],
)
@pytest.mark.asyncio
async def test_ordinary_links_accepted(client: AsyncClient, resource_group, url: str) -> None:
    ctx = resource_group
    created = await _create_resource(client, ctx["owner_headers"], ctx["group"]["id"], url=url)
    assert created["url"] == url


@pytest.mark.asyncio
async def test_blank_title_rejected(client: AsyncClient, resource_group) -> None:
    ctx = resource_group
    response = await client.post(
        f"/api/groups/{ctx['group']['id']}/resources",
        json={"title": "   ", "url": "https://example.edu"},
        headers=ctx["owner_headers"],
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_non_member_cannot_read_or_add(client: AsyncClient, resource_group) -> None:
    ctx = resource_group
    await _create_resource(client, ctx["owner_headers"], ctx["group"]["id"])

    listed = await client.get(
        f"/api/groups/{ctx['group']['id']}/resources", headers=ctx["outsider_headers"]
    )
    assert listed.status_code == 403

    added = await client.post(
        f"/api/groups/{ctx['group']['id']}/resources",
        json={"title": "Spam", "url": "https://spam.example"},
        headers=ctx["outsider_headers"],
    )
    assert added.status_code == 403


@pytest.mark.asyncio
async def test_resources_are_listed_newest_first(client: AsyncClient, resource_group) -> None:
    ctx = resource_group
    for title in ("First", "Second", "Third"):
        await _create_resource(client, ctx["owner_headers"], ctx["group"]["id"], title=title)

    response = await client.get(
        f"/api/groups/{ctx['group']['id']}/resources", headers=ctx["owner_headers"]
    )
    assert [item["title"] for item in response.json()["items"]] == ["Third", "Second", "First"]


@pytest.mark.asyncio
async def test_search_matches_title_and_description(
    client: AsyncClient, resource_group
) -> None:
    ctx = resource_group
    group_id = ctx["group"]["id"]
    await _create_resource(client, ctx["owner_headers"], group_id, title="Graph theory notes")
    await _create_resource(
        client, ctx["owner_headers"], group_id, title="Unrelated",
        description="covers graph colouring",
    )
    await _create_resource(client, ctx["owner_headers"], group_id, title="Calculus sheet")

    response = await client.get(
        f"/api/groups/{group_id}/resources",
        params={"search": "graph"},
        headers=ctx["owner_headers"],
    )
    assert response.json()["total"] == 2


@pytest.mark.asyncio
async def test_creator_can_delete_their_resource(client: AsyncClient, resource_group) -> None:
    ctx = resource_group
    created = await _create_resource(client, ctx["member_headers"], ctx["group"]["id"])

    deleted = await client.delete(
        f"/api/resources/{created['id']}", headers=ctx["member_headers"]
    )
    assert deleted.status_code == 204

    listed = await client.get(
        f"/api/groups/{ctx['group']['id']}/resources", headers=ctx["member_headers"]
    )
    assert listed.json()["items"] == []


@pytest.mark.asyncio
async def test_owner_can_remove_any_resource(client: AsyncClient, resource_group) -> None:
    """Owners moderate inappropriate content, including links they did not add."""
    ctx = resource_group
    created = await _create_resource(client, ctx["member_headers"], ctx["group"]["id"])

    deleted = await client.delete(
        f"/api/resources/{created['id']}", headers=ctx["owner_headers"]
    )
    assert deleted.status_code == 204


@pytest.mark.asyncio
async def test_member_cannot_delete_another_members_resource(
    client: AsyncClient, resource_group, auth_header
) -> None:
    ctx = resource_group
    other_headers, _ = await auth_header(email="res-third@university.edu")
    join = await client.post(
        f"/api/groups/{ctx['group']['id']}/join", headers=other_headers
    )
    assert join.status_code == 200

    created = await _create_resource(client, ctx["member_headers"], ctx["group"]["id"])
    response = await client.delete(f"/api/resources/{created['id']}", headers=other_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_can_delete_flag_reflects_the_viewer(
    client: AsyncClient, resource_group, auth_header
) -> None:
    ctx = resource_group
    other_headers, _ = await auth_header(email="res-fourth@university.edu")
    await client.post(f"/api/groups/{ctx['group']['id']}/join", headers=other_headers)
    await _create_resource(client, ctx["member_headers"], ctx["group"]["id"])

    as_other = await client.get(
        f"/api/groups/{ctx['group']['id']}/resources", headers=other_headers
    )
    assert as_other.json()["items"][0]["can_delete"] is False

    as_owner = await client.get(
        f"/api/groups/{ctx['group']['id']}/resources", headers=ctx["owner_headers"]
    )
    assert as_owner.json()["items"][0]["can_delete"] is True


@pytest.mark.asyncio
async def test_update_resource(client: AsyncClient, resource_group) -> None:
    ctx = resource_group
    created = await _create_resource(client, ctx["member_headers"], ctx["group"]["id"])

    response = await client.patch(
        f"/api/resources/{created['id']}",
        json={"title": "Updated slides", "url": "https://example.edu/v2.pdf"},
        headers=ctx["member_headers"],
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated slides"
    assert response.json()["url"] == "https://example.edu/v2.pdf"


@pytest.mark.asyncio
async def test_update_rejects_dangerous_url(client: AsyncClient, resource_group) -> None:
    """The validator has to guard edits too, not only creation."""
    ctx = resource_group
    created = await _create_resource(client, ctx["member_headers"], ctx["group"]["id"])

    response = await client.patch(
        f"/api/resources/{created['id']}",
        json={"url": "javascript:alert(1)"},
        headers=ctx["member_headers"],
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_resource_from_another_group_not_reachable(
    client: AsyncClient, resource_group
) -> None:
    ctx = resource_group
    created = await _create_resource(client, ctx["owner_headers"], ctx["group"]["id"])

    response = await client.delete(
        f"/api/resources/{created['id']}", headers=ctx["outsider_headers"]
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_missing_resource_returns_404(client: AsyncClient, resource_group) -> None:
    response = await client.delete(
        "/api/resources/00000000-0000-0000-0000-000000000000",
        headers=resource_group["owner_headers"],
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_deleting_group_removes_its_resources(
    client: AsyncClient, resource_group
) -> None:
    ctx = resource_group
    created = await _create_resource(client, ctx["owner_headers"], ctx["group"]["id"])

    deleted = await client.delete(
        f"/api/groups/{ctx['group']['id']}", headers=ctx["owner_headers"]
    )
    assert deleted.status_code == 204

    response = await client.patch(
        f"/api/resources/{created['id']}", json={"title": "x"}, headers=ctx["owner_headers"]
    )
    assert response.status_code == 404
