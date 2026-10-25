"""SSE stream behaviour: authorization, live delivery, heartbeats, replay.

Two levels of test here, on purpose.

`httpx`'s ASGI transport buffers a response body before handing it back, so
it can never observe an endless stream — pointing it at the stream endpoint
simply hangs. So the framing and replay logic is driven through the event
generator directly, and one test runs a real uvicorn server to prove the full
network path actually delivers bytes incrementally. That second test is the
one that would catch "works in tests, silently buffers in the browser".
"""

import asyncio
import contextlib
import json
import socket
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
import uvicorn
from httpx import AsyncClient

from app.api.routes import messages as messages_route
from app.main import create_app


async def _create_group(client: AsyncClient, headers: dict, name: str = "Live Group") -> dict:
    response = await client.post(
        "/api/groups", json={"name": name, "course_code": "CS404"}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _post(client: AsyncClient, headers: dict, group_id: str, content: str) -> dict:
    response = await client.post(
        f"/api/groups/{group_id}/messages", json={"content": content}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def _parse(frame: str) -> dict:
    """Turn one raw SSE frame into {id?, event, data}."""
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
async def live_group(client: AsyncClient, auth_header):
    owner_headers, owner = await auth_header(email="live-owner@university.edu")
    member_headers, member = await auth_header(email="live-member@university.edu")
    outsider_headers, _ = await auth_header(email="live-outsider@university.edu")
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


@pytest.fixture
async def event_stream():
    """Open generators, closed for the test so the pump task never leaks."""
    opened = []

    def _open(group_id: str, last_event_id: str | None = None):
        stream = messages_route._event_stream(
            group_id=UUID(group_id),
            last_event_id=UUID(last_event_id) if last_event_id else None,
        )
        opened.append(stream)
        return stream

    yield _open
    for stream in opened:
        with contextlib.suppress(Exception):
            await stream.aclose()


# --- Authorization (these responses finish, so the ASGI client is fine) ---


@pytest.mark.asyncio
async def test_stream_requires_authentication(client: AsyncClient, live_group) -> None:
    response = await client.get(f"/api/groups/{live_group['group']['id']}/stream")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_stream_requires_membership(client: AsyncClient, live_group) -> None:
    response = await client.get(
        f"/api/groups/{live_group['group']['id']}/stream",
        headers=live_group["outsider_headers"],
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_a_member"


@pytest.mark.asyncio
async def test_stream_rejects_unknown_group(client: AsyncClient, live_group) -> None:
    response = await client.get(
        "/api/groups/00000000-0000-0000-0000-000000000000/stream",
        headers=live_group["member_headers"],
    )
    assert response.status_code == 404


# --- Event generator behaviour ---


@pytest.mark.asyncio
async def test_member_receives_message_posted_by_another_member(
    client: AsyncClient, live_group, event_stream
) -> None:
    ctx = live_group
    group_id = ctx["group"]["id"]
    stream = event_stream(group_id)

    ready = await _next(stream)
    assert ready["event"] == "ready"
    assert ready["data"]["group_id"] == group_id

    posted = await _post(client, ctx["owner_headers"], group_id, "starting now")

    event = await _next(stream)
    assert event["event"] == "message.created"
    assert event["data"]["id"] == posted["id"]
    assert event["data"]["content"] == "starting now"
    assert event["data"]["author"]["first_name"] == ctx["owner"]["first_name"]
    # The frame id is what a client echoes back as Last-Event-ID.
    assert event["id"] == posted["id"]


@pytest.mark.asyncio
async def test_deletion_is_broadcast(client: AsyncClient, live_group, event_stream) -> None:
    ctx = live_group
    group_id = ctx["group"]["id"]
    message = await _post(client, ctx["owner_headers"], group_id, "will be removed")

    stream = event_stream(group_id)
    assert (await _next(stream))["event"] == "ready"

    deleted = await client.delete(
        f"/api/messages/{message['id']}", headers=ctx["owner_headers"]
    )
    assert deleted.status_code == 204

    event = await _next(stream)
    assert event["event"] == "message.deleted"
    assert event["data"]["id"] == message["id"]
    # No frame id: a deleted row cannot anchor a Last-Event-ID replay.
    assert "id" not in event


@pytest.mark.asyncio
async def test_stream_sends_heartbeats_while_idle(
    live_group, event_stream, monkeypatch
) -> None:
    """An idle chat still proves liveness, so proxies do not time it out."""
    monkeypatch.setattr(messages_route, "HEARTBEAT_SECONDS", 0.05)
    stream = event_stream(live_group["group"]["id"])

    assert (await _next(stream))["event"] == "ready"
    assert (await _next(stream))["event"] == "ping"


@pytest.mark.asyncio
async def test_last_event_id_replays_the_gap(
    client: AsyncClient, live_group, event_stream
) -> None:
    """Reconnecting after a drop must not silently lose messages."""
    ctx = live_group
    group_id = ctx["group"]["id"]

    first = await _post(client, ctx["owner_headers"], group_id, "before the drop")
    missed_one = await _post(client, ctx["owner_headers"], group_id, "missed one")
    missed_two = await _post(client, ctx["owner_headers"], group_id, "missed two")

    stream = event_stream(group_id, last_event_id=first["id"])

    replayed = [await _next(stream), await _next(stream)]
    assert [event["data"]["id"] for event in replayed] == [
        missed_one["id"],
        missed_two["id"],
    ]
    assert (await _next(stream))["event"] == "ready"


@pytest.mark.asyncio
async def test_replay_does_not_duplicate_live_events(
    client: AsyncClient, live_group, event_stream
) -> None:
    """A message caught by both replay and the subscription arrives once."""
    ctx = live_group
    group_id = ctx["group"]["id"]
    first = await _post(client, ctx["owner_headers"], group_id, "anchor")

    stream = event_stream(group_id, last_event_id=first["id"])
    # Nothing is replayed yet because the generator has not been started.
    overlapping = await _post(client, ctx["owner_headers"], group_id, "both paths")

    replayed = await _next(stream)
    assert replayed["data"]["id"] == overlapping["id"]
    assert (await _next(stream))["event"] == "ready"

    # The same message is still sitting in the subscription queue; it must be
    # swallowed rather than rendered twice.
    following = await _post(client, ctx["owner_headers"], group_id, "next one")
    event = await _next(stream)
    assert event["data"]["id"] == following["id"]


@pytest.mark.asyncio
async def test_unknown_last_event_id_is_ignored(
    client: AsyncClient, live_group, event_stream
) -> None:
    """A stale cursor for a deleted message must not break the connection."""
    ctx = live_group
    stream = event_stream(
        ctx["group"]["id"], last_event_id="00000000-0000-0000-0000-000000000000"
    )
    assert (await _next(stream))["event"] == "ready"


@pytest.mark.asyncio
async def test_events_do_not_leak_across_groups(
    client: AsyncClient, live_group, event_stream
) -> None:
    ctx = live_group
    other = await _create_group(client, ctx["owner_headers"], name="Unrelated Group")

    stream = event_stream(ctx["group"]["id"])
    assert (await _next(stream))["event"] == "ready"

    await _post(client, ctx["owner_headers"], other["id"], "not for you")
    expected = await _post(client, ctx["owner_headers"], ctx["group"]["id"], "for you")

    event = await _next(stream)
    assert event["data"]["id"] == expected["id"]
    assert event["data"]["content"] == "for you"


# --- End-to-end over a real socket ---


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


# loop_scope pinned to the test: async fixtures default to the session loop in
# this project, and a uvicorn task parked in a loop that is not running while
# the test executes would never accept the connection.
@pytest_asyncio.fixture(loop_scope="function")
async def live_server():
    port = _free_port()
    config = uvicorn.Config(
        create_app(), host="127.0.0.1", port=port, log_level="error", lifespan="off"
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.02)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(task, timeout=5)


@pytest.mark.asyncio
async def test_stream_delivers_over_real_http(
    client: AsyncClient, live_group, live_server
) -> None:
    """Bytes must reach the client before the response ends, not after."""
    ctx = live_group
    group_id = ctx["group"]["id"]

    async with httpx.AsyncClient(base_url=live_server, timeout=10) as http:
        async with http.stream(
            "GET", f"/api/groups/{group_id}/stream", headers=ctx["member_headers"]
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            assert response.headers.get("x-accel-buffering") == "no"

            frames = _aiter_frames(response)
            assert (await asyncio.wait_for(anext(frames), 5))["event"] == "ready"

            posted = await _post(client, ctx["owner_headers"], group_id, "over the wire")

            event = await asyncio.wait_for(anext(frames), 5)
            assert event["event"] == "message.created"
            assert event["data"]["content"] == "over the wire"
            assert event["data"]["id"] == posted["id"]


async def _aiter_frames(response):
    buffer: list[str] = []
    async for line in response.aiter_lines():
        if line == "":
            if buffer:
                yield _parse("\n".join(buffer))
                buffer = []
            continue
        buffer.append(line)
