"""Inbox: persistence, targeting, unread state, and the live user stream."""

import asyncio
import contextlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from httpx import AsyncClient

from app.api.routes import notifications as notifications_route


def _iso(offset: timedelta) -> str:
    return (datetime.now(UTC) + offset).isoformat()


async def _create_group(client: AsyncClient, headers: dict, name: str = "Notify Group") -> dict:
    response = await client.post(
        "/api/groups", json={"name": name, "course_code": "CS700"}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def _parse(frame: str) -> dict:
    parsed: dict = {}
    for line in frame.strip().splitlines():
        key, _, value = line.partition(":")
        value = value.lstrip()
        if key == "event":
            parsed["event"] = value
        elif key == "data":
            parsed["data"] = json.loads(value)
        elif key == "id":
            parsed["id"] = value
    return parsed


async def _next(stream, *, timeout: float = 5.0) -> dict:
    return _parse(await asyncio.wait_for(anext(stream), timeout=timeout))


@pytest.fixture
async def notify_group(client: AsyncClient, auth_header):
    owner_headers, owner = await auth_header(email="note-owner@university.edu")
    member_headers, member = await auth_header(email="note-member@university.edu")
    outsider_headers, outsider = await auth_header(email="note-outsider@university.edu")
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
async def test_assigning_a_task_notifies_the_assignee_not_the_assigner(
    client: AsyncClient, notify_group
) -> None:
    ctx = notify_group
    response = await client.post(
        f"/api/groups/{ctx['group']['id']}/tasks",
        json={"title": "Read chapter 4", "assigned_to": ctx["member"]["id"]},
        headers=ctx["owner_headers"],
    )
    assert response.status_code == 201, response.text
    task = response.json()

    inbox = await client.get("/api/notifications", headers=ctx["member_headers"])
    assert inbox.status_code == 200
    items = inbox.json()["items"]
    assert len(items) == 1
    assert items[0]["type"] == "task_assigned"
    assert items[0]["entity_id"] == task["id"]
    assert items[0]["href"] == f"/app/groups/{ctx['group']['id']}/tasks"
    assert items[0]["read_at"] is None
    assert "Read chapter 4" in items[0]["body"]
    assert items[0]["actor"]["first_name"] == ctx["owner"]["first_name"]

    assigner = await client.get("/api/notifications", headers=ctx["owner_headers"])
    assert assigner.json()["items"] == []


@pytest.mark.asyncio
async def test_self_assignment_does_not_notify(client: AsyncClient, notify_group) -> None:
    ctx = notify_group
    response = await client.post(
        f"/api/groups/{ctx['group']['id']}/tasks",
        json={"title": "Own work", "assigned_to": ctx["owner"]["id"]},
        headers=ctx["owner_headers"],
    )
    assert response.status_code == 201
    inbox = await client.get("/api/notifications", headers=ctx["owner_headers"])
    assert inbox.json()["items"] == []


@pytest.mark.asyncio
async def test_reassignment_notifies_only_the_new_assignee(
    client: AsyncClient, notify_group
) -> None:
    ctx = notify_group
    created = await client.post(
        f"/api/groups/{ctx['group']['id']}/tasks",
        json={"title": "Shared work", "assigned_to": ctx["member"]["id"]},
        headers=ctx["owner_headers"],
    )
    task_id = created.json()["id"]

    # Same assignee again must not add a second row.
    again = await client.patch(
        f"/api/tasks/{task_id}",
        json={"assigned_to": ctx["member"]["id"]},
        headers=ctx["owner_headers"],
    )
    assert again.status_code == 200
    member_inbox = await client.get("/api/notifications", headers=ctx["member_headers"])
    assert len(member_inbox.json()["items"]) == 1

    moved = await client.patch(
        f"/api/tasks/{task_id}",
        json={"assigned_to": ctx["owner"]["id"]},
        headers=ctx["member_headers"],
    )
    assert moved.status_code == 200

    owner_inbox = await client.get("/api/notifications", headers=ctx["owner_headers"])
    assert [item["type"] for item in owner_inbox.json()["items"]] == ["task_assigned"]
    # The previous assignee does not get a "taken off" notification.
    member_after = await client.get("/api/notifications", headers=ctx["member_headers"])
    assert len(member_after.json()["items"]) == 1


@pytest.mark.asyncio
async def test_unassigned_task_does_not_notify(client: AsyncClient, notify_group) -> None:
    ctx = notify_group
    response = await client.post(
        f"/api/groups/{ctx['group']['id']}/tasks",
        json={"title": "Unowned"},
        headers=ctx["owner_headers"],
    )
    assert response.status_code == 201
    inbox = await client.get("/api/notifications", headers=ctx["member_headers"])
    assert inbox.json()["items"] == []


@pytest.mark.asyncio
async def test_new_session_notifies_other_members_not_the_organiser(
    client: AsyncClient, notify_group
) -> None:
    ctx = notify_group
    response = await client.post(
        f"/api/groups/{ctx['group']['id']}/sessions",
        json={
            "title": "Chapter 7 review",
            "start_time": _iso(timedelta(days=1)),
            "end_time": _iso(timedelta(days=1, hours=2)),
        },
        headers=ctx["owner_headers"],
    )
    assert response.status_code == 201, response.text

    member = await client.get("/api/notifications", headers=ctx["member_headers"])
    items = member.json()["items"]
    assert len(items) == 1
    assert items[0]["type"] == "session_created"
    assert "Chapter 7 review" in items[0]["body"]

    organiser = await client.get("/api/notifications", headers=ctx["owner_headers"])
    assert organiser.json()["items"] == []
    outsider = await client.get("/api/notifications", headers=ctx["outsider_headers"])
    assert outsider.json()["items"] == []


@pytest.mark.asyncio
async def test_sharing_a_resource_notifies_other_members(
    client: AsyncClient, notify_group
) -> None:
    ctx = notify_group
    response = await client.post(
        f"/api/groups/{ctx['group']['id']}/resources",
        json={"title": "Lecture slides", "url": "https://example.edu/slides.pdf"},
        headers=ctx["member_headers"],
    )
    assert response.status_code == 201, response.text

    owner = await client.get("/api/notifications", headers=ctx["owner_headers"])
    assert owner.json()["items"][0]["type"] == "resource_shared"
    member = await client.get("/api/notifications", headers=ctx["member_headers"])
    assert member.json()["items"] == []


@pytest.mark.asyncio
async def test_rsvp_notifies_organiser_and_is_idempotent(
    client: AsyncClient, notify_group
) -> None:
    ctx = notify_group
    created = await client.post(
        f"/api/groups/{ctx['group']['id']}/sessions",
        json={
            "title": "Office hours",
            "start_time": _iso(timedelta(days=2)),
            "end_time": _iso(timedelta(days=2, hours=1)),
        },
        headers=ctx["owner_headers"],
    )
    session_id = created.json()["id"]

    first = await client.put(
        f"/api/sessions/{session_id}/rsvp",
        json={"status": "going"},
        headers=ctx["member_headers"],
    )
    assert first.status_code == 200
    second = await client.put(
        f"/api/sessions/{session_id}/rsvp",
        json={"status": "going"},
        headers=ctx["member_headers"],
    )
    assert second.status_code == 200

    owner = await client.get("/api/notifications", headers=ctx["owner_headers"])
    rsvps = [item for item in owner.json()["items"] if item["type"] == "rsvp_updated"]
    assert len(rsvps) == 1
    assert "going" in rsvps[0]["body"]


@pytest.mark.asyncio
async def test_chat_messages_do_not_create_inbox_rows(
    client: AsyncClient, notify_group
) -> None:
    ctx = notify_group
    posted = await client.post(
        f"/api/groups/{ctx['group']['id']}/messages",
        json={"content": "Anyone here?"},
        headers=ctx["owner_headers"],
    )
    assert posted.status_code == 201
    inbox = await client.get("/api/notifications", headers=ctx["member_headers"])
    assert inbox.json()["items"] == []


@pytest.mark.asyncio
async def test_unread_count_and_mark_read(client: AsyncClient, notify_group) -> None:
    ctx = notify_group
    await client.post(
        f"/api/groups/{ctx['group']['id']}/tasks",
        json={"title": "One", "assigned_to": ctx["member"]["id"]},
        headers=ctx["owner_headers"],
    )
    await client.post(
        f"/api/groups/{ctx['group']['id']}/tasks",
        json={"title": "Two", "assigned_to": ctx["member"]["id"]},
        headers=ctx["owner_headers"],
    )

    count = await client.get("/api/notifications/unread-count", headers=ctx["member_headers"])
    assert count.json()["unread"] == 2

    inbox = await client.get("/api/notifications", headers=ctx["member_headers"])
    first_id = inbox.json()["items"][0]["id"]
    marked = await client.patch(
        f"/api/notifications/{first_id}/read", headers=ctx["member_headers"]
    )
    assert marked.status_code == 200
    assert marked.json()["read_at"] is not None

    count = await client.get("/api/notifications/unread-count", headers=ctx["member_headers"])
    assert count.json()["unread"] == 1

    cleared = await client.post("/api/notifications/read-all", headers=ctx["member_headers"])
    assert cleared.json()["unread"] == 0
    count = await client.get("/api/notifications/unread-count", headers=ctx["member_headers"])
    assert count.json()["unread"] == 0


@pytest.mark.asyncio
async def test_cannot_read_someone_elses_notification(
    client: AsyncClient, notify_group
) -> None:
    ctx = notify_group
    await client.post(
        f"/api/groups/{ctx['group']['id']}/tasks",
        json={"title": "Private", "assigned_to": ctx["member"]["id"]},
        headers=ctx["owner_headers"],
    )
    inbox = await client.get("/api/notifications", headers=ctx["member_headers"])
    note_id = inbox.json()["items"][0]["id"]

    stolen = await client.patch(
        f"/api/notifications/{note_id}/read", headers=ctx["owner_headers"]
    )
    assert stolen.status_code == 404
    missing = await client.patch(
        "/api/notifications/00000000-0000-0000-0000-000000000000/read",
        headers=ctx["owner_headers"],
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_inbox_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/notifications")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unread_filter(client: AsyncClient, notify_group) -> None:
    ctx = notify_group
    await client.post(
        f"/api/groups/{ctx['group']['id']}/tasks",
        json={"title": "Keep unread", "assigned_to": ctx["member"]["id"]},
        headers=ctx["owner_headers"],
    )
    await client.post(
        f"/api/groups/{ctx['group']['id']}/tasks",
        json={"title": "Will read", "assigned_to": ctx["member"]["id"]},
        headers=ctx["owner_headers"],
    )
    inbox = await client.get("/api/notifications", headers=ctx["member_headers"])
    read_id = inbox.json()["items"][0]["id"]
    await client.patch(f"/api/notifications/{read_id}/read", headers=ctx["member_headers"])

    unread = await client.get(
        "/api/notifications", params={"unread_only": True}, headers=ctx["member_headers"]
    )
    assert unread.json()["total"] == 1
    assert unread.json()["items"][0]["title"] == "Task assigned to you"


@pytest.fixture
async def event_stream():
    opened = []

    def _open(user_id: str, last_event_id: str | None = None):
        stream = notifications_route._event_stream(
            user_id=UUID(user_id),
            last_event_id=UUID(last_event_id) if last_event_id else None,
        )
        opened.append(stream)
        return stream

    yield _open
    for stream in opened:
        with contextlib.suppress(Exception):
            await stream.aclose()


@pytest.mark.asyncio
async def test_stream_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/notifications/stream")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_member_receives_assignment_on_their_stream(
    client: AsyncClient, notify_group, event_stream
) -> None:
    ctx = notify_group
    stream = event_stream(ctx["member"]["id"])
    ready = await _next(stream)
    assert ready["event"] == "ready"
    assert ready["data"]["user_id"] == ctx["member"]["id"]

    await client.post(
        f"/api/groups/{ctx['group']['id']}/tasks",
        json={"title": "Live assign", "assigned_to": ctx["member"]["id"]},
        headers=ctx["owner_headers"],
    )
    event = await _next(stream)
    assert event["event"] == "notification.created"
    assert event["data"]["type"] == "task_assigned"
    assert event["data"]["entity_id"]
    assert event["id"] == event["data"]["id"]


@pytest.mark.asyncio
async def test_events_do_not_leak_across_users(
    client: AsyncClient, notify_group, event_stream
) -> None:
    ctx = notify_group
    stream = event_stream(ctx["outsider"]["id"])
    assert (await _next(stream))["event"] == "ready"

    await client.post(
        f"/api/groups/{ctx['group']['id']}/tasks",
        json={"title": "Not for Carl", "assigned_to": ctx["member"]["id"]},
        headers=ctx["owner_headers"],
    )
    # Outsider must only see a heartbeat if anything; the assignment is not theirs.
    with pytest.raises(TimeoutError):
        await _next(stream, timeout=0.4)


@pytest.mark.asyncio
async def test_last_event_id_replays_missed_notifications(
    client: AsyncClient, notify_group, event_stream
) -> None:
    ctx = notify_group
    first = await client.post(
        f"/api/groups/{ctx['group']['id']}/tasks",
        json={"title": "Before drop", "assigned_to": ctx["member"]["id"]},
        headers=ctx["owner_headers"],
    )
    assert first.status_code == 201
    inbox = await client.get("/api/notifications", headers=ctx["member_headers"])
    first_id = inbox.json()["items"][0]["id"]

    missed = await client.post(
        f"/api/groups/{ctx['group']['id']}/tasks",
        json={"title": "Missed while away", "assigned_to": ctx["member"]["id"]},
        headers=ctx["owner_headers"],
    )
    assert missed.status_code == 201

    stream = event_stream(ctx["member"]["id"], last_event_id=first_id)
    replayed = await _next(stream)
    assert replayed["event"] == "notification.created"
    assert "Missed while away" in replayed["data"]["body"]
    assert (await _next(stream))["event"] == "ready"
