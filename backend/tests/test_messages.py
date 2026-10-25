import pytest
from httpx import AsyncClient

from app.services.message import message_service


async def _create_group(client: AsyncClient, headers: dict, name: str = "Study Hall") -> dict:
    response = await client.post(
        "/api/groups",
        json={"name": name, "course_code": "CS301"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _post(client: AsyncClient, headers: dict, group_id: str, content: str) -> dict:
    response = await client.post(
        f"/api/groups/{group_id}/messages",
        json={"content": content},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
async def chat_group(client: AsyncClient, auth_header):
    """An owner, a joined member, an outsider, and a group."""
    owner_headers, owner = await auth_header(email="chat-owner@university.edu")
    member_headers, member = await auth_header(email="chat-member@university.edu")
    outsider_headers, outsider = await auth_header(email="chat-outsider@university.edu")
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
        "outsider": outsider,
    }


@pytest.mark.asyncio
async def test_post_and_list_message(client: AsyncClient, chat_group) -> None:
    ctx = chat_group
    posted = await _post(client, ctx["member_headers"], ctx["group"]["id"], "Anyone here?")

    assert posted["content"] == "Anyone here?"
    assert posted["user_id"] == ctx["member"]["id"]
    assert posted["author"]["first_name"] == ctx["member"]["first_name"]

    response = await client.get(
        f"/api/groups/{ctx['group']['id']}/messages", headers=ctx["owner_headers"]
    )
    assert response.status_code == 200
    body = response.json()
    assert [item["content"] for item in body["items"]] == ["Anyone here?"]
    assert body["has_more"] is False
    assert body["next_cursor"] is None


@pytest.mark.asyncio
async def test_message_content_is_trimmed(client: AsyncClient, chat_group) -> None:
    ctx = chat_group
    posted = await _post(client, ctx["owner_headers"], ctx["group"]["id"], "  padded  ")
    assert posted["content"] == "padded"


@pytest.mark.asyncio
async def test_whitespace_only_message_rejected(client: AsyncClient, chat_group) -> None:
    ctx = chat_group
    response = await client.post(
        f"/api/groups/{ctx['group']['id']}/messages",
        json={"content": "   "},
        headers=ctx["owner_headers"],
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_message_length_capped(client: AsyncClient, chat_group) -> None:
    ctx = chat_group
    response = await client.post(
        f"/api/groups/{ctx['group']['id']}/messages",
        json={"content": "x" * 2001},
        headers=ctx["owner_headers"],
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_non_member_cannot_read_or_write(client: AsyncClient, chat_group) -> None:
    ctx = chat_group
    await _post(client, ctx["owner_headers"], ctx["group"]["id"], "private chatter")

    read = await client.get(
        f"/api/groups/{ctx['group']['id']}/messages", headers=ctx["outsider_headers"]
    )
    assert read.status_code == 403
    assert read.json()["error"]["code"] == "not_a_member"

    write = await client.post(
        f"/api/groups/{ctx['group']['id']}/messages",
        json={"content": "let me in"},
        headers=ctx["outsider_headers"],
    )
    assert write.status_code == 403


@pytest.mark.asyncio
async def test_anonymous_request_rejected(client: AsyncClient, chat_group) -> None:
    response = await client.get(f"/api/groups/{chat_group['group']['id']}/messages")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_history_is_oldest_first(client: AsyncClient, chat_group) -> None:
    ctx = chat_group
    for text in ("one", "two", "three"):
        await _post(client, ctx["owner_headers"], ctx["group"]["id"], text)

    response = await client.get(
        f"/api/groups/{ctx['group']['id']}/messages", headers=ctx["owner_headers"]
    )
    assert [item["content"] for item in response.json()["items"]] == ["one", "two", "three"]


@pytest.mark.asyncio
async def test_keyset_pagination_walks_back_without_gaps(
    client: AsyncClient, chat_group
) -> None:
    """Paging backwards must cover every message exactly once."""
    ctx = chat_group
    group_id = ctx["group"]["id"]
    sent = [f"message {index}" for index in range(7)]
    for text in sent:
        await _post(client, ctx["owner_headers"], group_id, text)

    collected: list[str] = []
    cursor = None
    pages = 0
    while True:
        params = {"limit": 3}
        if cursor:
            params["before"] = cursor
        response = await client.get(
            f"/api/groups/{group_id}/messages", params=params, headers=ctx["owner_headers"]
        )
        assert response.status_code == 200
        body = response.json()
        collected = [item["content"] for item in body["items"]] + collected
        pages += 1
        if not body["has_more"]:
            break
        cursor = body["next_cursor"]
        assert cursor is not None

    assert collected == sent
    assert pages == 3


@pytest.mark.asyncio
async def test_new_message_during_paging_does_not_shift_pages(
    client: AsyncClient, chat_group
) -> None:
    """The reason for keyset over OFFSET: inserts must not shift older pages."""
    ctx = chat_group
    group_id = ctx["group"]["id"]
    for index in range(4):
        await _post(client, ctx["owner_headers"], group_id, f"old {index}")

    first = await client.get(
        f"/api/groups/{group_id}/messages",
        params={"limit": 2},
        headers=ctx["owner_headers"],
    )
    cursor = first.json()["next_cursor"]

    await _post(client, ctx["member_headers"], group_id, "brand new")

    second = await client.get(
        f"/api/groups/{group_id}/messages",
        params={"limit": 2, "before": cursor},
        headers=ctx["owner_headers"],
    )
    # With OFFSET=2 this page would have repeated "old 1"; anchored on a
    # cursor it still returns the two genuinely older messages.
    assert [item["content"] for item in second.json()["items"]] == ["old 0", "old 1"]


@pytest.mark.asyncio
async def test_cursor_from_another_group_rejected(
    client: AsyncClient, chat_group, auth_header
) -> None:
    ctx = chat_group
    other_group = await _create_group(client, ctx["owner_headers"], name="Other Group")
    foreign = await _post(client, ctx["owner_headers"], other_group["id"], "elsewhere")

    response = await client.get(
        f"/api/groups/{ctx['group']['id']}/messages",
        params={"before": foreign["id"]},
        headers=ctx["owner_headers"],
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_cursor"


@pytest.mark.asyncio
async def test_messages_are_isolated_per_group(client: AsyncClient, chat_group) -> None:
    ctx = chat_group
    other_group = await _create_group(client, ctx["owner_headers"], name="Second Group")
    await _post(client, ctx["owner_headers"], ctx["group"]["id"], "in first")
    await _post(client, ctx["owner_headers"], other_group["id"], "in second")

    response = await client.get(
        f"/api/groups/{other_group['id']}/messages", headers=ctx["owner_headers"]
    )
    assert [item["content"] for item in response.json()["items"]] == ["in second"]


@pytest.mark.asyncio
async def test_author_can_delete_own_message(client: AsyncClient, chat_group) -> None:
    ctx = chat_group
    message = await _post(client, ctx["member_headers"], ctx["group"]["id"], "oops")

    response = await client.delete(
        f"/api/messages/{message['id']}", headers=ctx["member_headers"]
    )
    assert response.status_code == 204

    history = await client.get(
        f"/api/groups/{ctx['group']['id']}/messages", headers=ctx["member_headers"]
    )
    assert history.json()["items"] == []


@pytest.mark.asyncio
async def test_owner_can_moderate_any_message(client: AsyncClient, chat_group) -> None:
    ctx = chat_group
    message = await _post(client, ctx["member_headers"], ctx["group"]["id"], "inappropriate")

    response = await client.delete(
        f"/api/messages/{message['id']}", headers=ctx["owner_headers"]
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_member_cannot_delete_another_members_message(
    client: AsyncClient, chat_group, auth_header
) -> None:
    ctx = chat_group
    other_headers, _ = await auth_header(email="chat-third@university.edu")
    join = await client.post(
        f"/api/groups/{ctx['group']['id']}/join", headers=other_headers
    )
    assert join.status_code == 200

    message = await _post(client, ctx["member_headers"], ctx["group"]["id"], "mine")
    response = await client.delete(f"/api/messages/{message['id']}", headers=other_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_non_member_cannot_delete_message(client: AsyncClient, chat_group) -> None:
    ctx = chat_group
    message = await _post(client, ctx["member_headers"], ctx["group"]["id"], "mine")
    response = await client.delete(
        f"/api/messages/{message['id']}", headers=ctx["outsider_headers"]
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_missing_message_returns_404(client: AsyncClient, chat_group) -> None:
    response = await client.delete(
        "/api/messages/00000000-0000-0000-0000-000000000000",
        headers=chat_group["owner_headers"],
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rapid_posting_is_throttled(client: AsyncClient, chat_group) -> None:
    ctx = chat_group
    limit = message_service.throttle.max_events
    for index in range(limit):
        await _post(client, ctx["member_headers"], ctx["group"]["id"], f"spam {index}")

    response = await client.post(
        f"/api/groups/{ctx['group']['id']}/messages",
        json={"content": "one too many"},
        headers=ctx["member_headers"],
    )
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"

    # The limit is per user, so another member is unaffected.
    ok = await client.post(
        f"/api/groups/{ctx['group']['id']}/messages",
        json={"content": "still fine"},
        headers=ctx["owner_headers"],
    )
    assert ok.status_code == 201


@pytest.mark.asyncio
async def test_leaving_group_keeps_history(client: AsyncClient, chat_group) -> None:
    """Messages survive the author leaving; only the group deletes them."""
    ctx = chat_group
    await _post(client, ctx["member_headers"], ctx["group"]["id"], "see you later")

    leave = await client.delete(
        f"/api/groups/{ctx['group']['id']}/leave", headers=ctx["member_headers"]
    )
    assert leave.status_code in (200, 204)

    history = await client.get(
        f"/api/groups/{ctx['group']['id']}/messages", headers=ctx["owner_headers"]
    )
    assert [item["content"] for item in history.json()["items"]] == ["see you later"]
