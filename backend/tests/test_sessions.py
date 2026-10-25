from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient


def _iso(offset: timedelta) -> str:
    return (datetime.now(UTC) + offset).isoformat()


async def _create_group(client: AsyncClient, headers: dict, name: str = "Finals Prep") -> dict:
    response = await client.post(
        "/api/groups", json={"name": name, "course_code": "CS600"}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_session(client: AsyncClient, headers: dict, group_id: str, **overrides) -> dict:
    payload = {
        "title": "Chapter 7 review",
        "start_time": _iso(timedelta(days=1)),
        "end_time": _iso(timedelta(days=1, hours=2)),
    }
    payload.update(overrides)
    response = await client.post(
        f"/api/groups/{group_id}/sessions", json=payload, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
async def session_group(client: AsyncClient, auth_header):
    owner_headers, owner = await auth_header(email="sess-owner@university.edu")
    member_headers, member = await auth_header(email="sess-member@university.edu")
    outsider_headers, _ = await auth_header(email="sess-outsider@university.edu")
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
async def test_create_session(client: AsyncClient, session_group) -> None:
    ctx = session_group
    created = await _create_session(
        client,
        ctx["member_headers"],
        ctx["group"]["id"],
        description="Bring the practice set",
        location="Library room 4",
    )

    assert created["title"] == "Chapter 7 review"
    assert created["location"] == "Library room 4"
    assert created["created_by"] == ctx["member"]["id"]
    assert created["creator"]["email"] == ctx["member"]["email"]
    assert created["can_manage"] is True


@pytest.mark.asyncio
async def test_organiser_is_counted_as_attending(client: AsyncClient, session_group) -> None:
    """A new session should never show up with nobody going, not even the host."""
    ctx = session_group
    created = await _create_session(client, ctx["member_headers"], ctx["group"]["id"])

    assert created["my_rsvp"] == "going"
    assert created["rsvp_counts"]["going"] == 1


@pytest.mark.asyncio
async def test_end_must_be_after_start(client: AsyncClient, session_group) -> None:
    ctx = session_group
    response = await client.post(
        f"/api/groups/{ctx['group']['id']}/sessions",
        json={
            "title": "Backwards",
            "start_time": _iso(timedelta(days=1, hours=2)),
            "end_time": _iso(timedelta(days=1)),
        },
        headers=ctx["owner_headers"],
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_zero_length_session_rejected(client: AsyncClient, session_group) -> None:
    ctx = session_group
    same = _iso(timedelta(days=1))
    response = await client.post(
        f"/api/groups/{ctx['group']['id']}/sessions",
        json={"title": "Instant", "start_time": same, "end_time": same},
        headers=ctx["owner_headers"],
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_absurdly_long_session_rejected(client: AsyncClient, session_group) -> None:
    """Usually a mistyped year, and it would smear across every calendar view."""
    ctx = session_group
    response = await client.post(
        f"/api/groups/{ctx['group']['id']}/sessions",
        json={
            "title": "Marathon",
            "start_time": _iso(timedelta(days=1)),
            "end_time": _iso(timedelta(days=40)),
        },
        headers=ctx["owner_headers"],
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_blank_title_rejected(client: AsyncClient, session_group) -> None:
    ctx = session_group
    response = await client.post(
        f"/api/groups/{ctx['group']['id']}/sessions",
        json={
            "title": "   ",
            "start_time": _iso(timedelta(days=1)),
            "end_time": _iso(timedelta(days=1, hours=1)),
        },
        headers=ctx["owner_headers"],
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_non_member_cannot_create_or_list(client: AsyncClient, session_group) -> None:
    ctx = session_group
    await _create_session(client, ctx["owner_headers"], ctx["group"]["id"])

    listed = await client.get(
        f"/api/groups/{ctx['group']['id']}/sessions", headers=ctx["outsider_headers"]
    )
    assert listed.status_code == 403

    created = await client.post(
        f"/api/groups/{ctx['group']['id']}/sessions",
        json={
            "title": "Gatecrash",
            "start_time": _iso(timedelta(days=1)),
            "end_time": _iso(timedelta(days=1, hours=1)),
        },
        headers=ctx["outsider_headers"],
    )
    assert created.status_code == 403


@pytest.mark.asyncio
async def test_sessions_listed_in_chronological_order(
    client: AsyncClient, session_group
) -> None:
    ctx = session_group
    group_id = ctx["group"]["id"]
    await _create_session(
        client,
        ctx["owner_headers"],
        group_id,
        title="Later",
        start_time=_iso(timedelta(days=5)),
        end_time=_iso(timedelta(days=5, hours=1)),
    )
    await _create_session(
        client,
        ctx["owner_headers"],
        group_id,
        title="Sooner",
        start_time=_iso(timedelta(days=2)),
        end_time=_iso(timedelta(days=2, hours=1)),
    )

    response = await client.get(
        f"/api/groups/{group_id}/sessions", headers=ctx["owner_headers"]
    )
    assert [item["title"] for item in response.json()["items"]] == ["Sooner", "Later"]


@pytest.mark.asyncio
async def test_upcoming_filter_excludes_finished_sessions(
    client: AsyncClient, session_group
) -> None:
    ctx = session_group
    group_id = ctx["group"]["id"]
    await _create_session(
        client,
        ctx["owner_headers"],
        group_id,
        title="Last week",
        start_time=_iso(timedelta(days=-7)),
        end_time=_iso(timedelta(days=-7, hours=1)),
    )
    await _create_session(client, ctx["owner_headers"], group_id, title="Tomorrow")

    everything = await client.get(
        f"/api/groups/{group_id}/sessions", headers=ctx["owner_headers"]
    )
    assert everything.json()["total"] == 2

    upcoming = await client.get(
        f"/api/groups/{group_id}/sessions?upcoming=true", headers=ctx["owner_headers"]
    )
    assert [item["title"] for item in upcoming.json()["items"]] == ["Tomorrow"]


@pytest.mark.asyncio
async def test_session_in_progress_still_counts_as_upcoming(
    client: AsyncClient, session_group
) -> None:
    """Started an hour ago, runs until tonight — you can still join it."""
    ctx = session_group
    await _create_session(
        client,
        ctx["owner_headers"],
        ctx["group"]["id"],
        title="Happening now",
        start_time=_iso(timedelta(hours=-1)),
        end_time=_iso(timedelta(hours=2)),
    )

    upcoming = await client.get(
        f"/api/groups/{ctx['group']['id']}/sessions?upcoming=true",
        headers=ctx["owner_headers"],
    )
    assert [item["title"] for item in upcoming.json()["items"]] == ["Happening now"]


@pytest.mark.asyncio
async def test_date_range_filter_for_calendar_month(
    client: AsyncClient, session_group
) -> None:
    ctx = session_group
    group_id = ctx["group"]["id"]
    await _create_session(
        client, ctx["owner_headers"], group_id, title="In range",
        start_time=_iso(timedelta(days=3)), end_time=_iso(timedelta(days=3, hours=1)),
    )
    await _create_session(
        client, ctx["owner_headers"], group_id, title="Out of range",
        start_time=_iso(timedelta(days=60)), end_time=_iso(timedelta(days=60, hours=1)),
    )

    response = await client.get(
        f"/api/groups/{group_id}/sessions",
        params={"starts_after": _iso(timedelta(days=1)), "starts_before": _iso(timedelta(days=10))},
        headers=ctx["owner_headers"],
    )
    assert [item["title"] for item in response.json()["items"]] == ["In range"]


@pytest.mark.asyncio
async def test_organiser_can_update_session(client: AsyncClient, session_group) -> None:
    ctx = session_group
    created = await _create_session(client, ctx["member_headers"], ctx["group"]["id"])

    response = await client.patch(
        f"/api/sessions/{created['id']}",
        json={"title": "Moved to room 2", "location": "Library room 2"},
        headers=ctx["member_headers"],
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Moved to room 2"
    assert response.json()["location"] == "Library room 2"


@pytest.mark.asyncio
async def test_partial_update_validates_against_stored_times(
    client: AsyncClient, session_group
) -> None:
    """Moving only the end time must still be checked against the stored start."""
    ctx = session_group
    created = await _create_session(client, ctx["owner_headers"], ctx["group"]["id"])

    response = await client.patch(
        f"/api/sessions/{created['id']}",
        json={"end_time": _iso(timedelta(hours=1))},
        headers=ctx["owner_headers"],
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_time_window"


@pytest.mark.asyncio
async def test_owner_can_manage_another_members_session(
    client: AsyncClient, session_group
) -> None:
    ctx = session_group
    created = await _create_session(client, ctx["member_headers"], ctx["group"]["id"])

    response = await client.patch(
        f"/api/sessions/{created['id']}",
        json={"title": "Rescheduled by owner"},
        headers=ctx["owner_headers"],
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_plain_member_cannot_edit_someone_elses_session(
    client: AsyncClient, session_group, auth_header
) -> None:
    ctx = session_group
    other_headers, _ = await auth_header(email="sess-third@university.edu")
    join = await client.post(
        f"/api/groups/{ctx['group']['id']}/join", headers=other_headers
    )
    assert join.status_code == 200

    created = await _create_session(client, ctx["member_headers"], ctx["group"]["id"])
    response = await client.patch(
        f"/api/sessions/{created['id']}", json={"title": "Hijack"}, headers=other_headers
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_session(client: AsyncClient, session_group) -> None:
    ctx = session_group
    created = await _create_session(client, ctx["member_headers"], ctx["group"]["id"])

    deleted = await client.delete(
        f"/api/sessions/{created['id']}", headers=ctx["member_headers"]
    )
    assert deleted.status_code == 204

    missing = await client.get(
        f"/api/sessions/{created['id']}", headers=ctx["member_headers"]
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_session_from_another_group_is_not_reachable(
    client: AsyncClient, session_group, auth_header
) -> None:
    """The id is not a capability: membership of *that* group is required."""
    ctx = session_group
    created = await _create_session(client, ctx["owner_headers"], ctx["group"]["id"])

    response = await client.get(
        f"/api/sessions/{created['id']}", headers=ctx["outsider_headers"]
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_a_member"


@pytest.mark.asyncio
async def test_rsvp_updates_counts(client: AsyncClient, session_group) -> None:
    ctx = session_group
    created = await _create_session(client, ctx["owner_headers"], ctx["group"]["id"])

    response = await client.put(
        f"/api/sessions/{created['id']}/rsvp",
        json={"status": "maybe"},
        headers=ctx["member_headers"],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["my_rsvp"] == "maybe"
    assert body["rsvp_counts"] == {"going": 1, "maybe": 1, "declined": 0}


@pytest.mark.asyncio
async def test_rsvp_is_idempotent(client: AsyncClient, session_group) -> None:
    """Answering twice replaces the answer rather than stacking duplicates."""
    ctx = session_group
    created = await _create_session(client, ctx["owner_headers"], ctx["group"]["id"])
    url = f"/api/sessions/{created['id']}/rsvp"

    await client.put(url, json={"status": "going"}, headers=ctx["member_headers"])
    await client.put(url, json={"status": "going"}, headers=ctx["member_headers"])
    final = await client.put(url, json={"status": "declined"}, headers=ctx["member_headers"])

    assert final.json()["rsvp_counts"] == {"going": 1, "maybe": 0, "declined": 1}


@pytest.mark.asyncio
async def test_rsvp_can_be_withdrawn(client: AsyncClient, session_group) -> None:
    ctx = session_group
    created = await _create_session(client, ctx["owner_headers"], ctx["group"]["id"])
    url = f"/api/sessions/{created['id']}/rsvp"

    await client.put(url, json={"status": "going"}, headers=ctx["member_headers"])
    cleared = await client.delete(url, headers=ctx["member_headers"])

    assert cleared.status_code == 200
    assert cleared.json()["my_rsvp"] is None
    assert cleared.json()["rsvp_counts"]["going"] == 1


@pytest.mark.asyncio
async def test_invalid_rsvp_status_rejected(client: AsyncClient, session_group) -> None:
    ctx = session_group
    created = await _create_session(client, ctx["owner_headers"], ctx["group"]["id"])

    response = await client.put(
        f"/api/sessions/{created['id']}/rsvp",
        json={"status": "perhaps"},
        headers=ctx["member_headers"],
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_non_member_cannot_rsvp(client: AsyncClient, session_group) -> None:
    ctx = session_group
    created = await _create_session(client, ctx["owner_headers"], ctx["group"]["id"])

    response = await client.put(
        f"/api/sessions/{created['id']}/rsvp",
        json={"status": "going"},
        headers=ctx["outsider_headers"],
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_attendee_list(client: AsyncClient, session_group) -> None:
    ctx = session_group
    created = await _create_session(client, ctx["owner_headers"], ctx["group"]["id"])
    await client.put(
        f"/api/sessions/{created['id']}/rsvp",
        json={"status": "declined"},
        headers=ctx["member_headers"],
    )

    response = await client.get(
        f"/api/sessions/{created['id']}/rsvps", headers=ctx["member_headers"]
    )
    assert response.status_code == 200
    by_email = {row["user"]["email"]: row["status"] for row in response.json()}
    assert by_email[ctx["owner"]["email"]] == "going"
    assert by_email[ctx["member"]["email"]] == "declined"


@pytest.mark.asyncio
async def test_deleting_session_removes_its_rsvps(client: AsyncClient, session_group) -> None:
    ctx = session_group
    created = await _create_session(client, ctx["owner_headers"], ctx["group"]["id"])
    await client.put(
        f"/api/sessions/{created['id']}/rsvp",
        json={"status": "going"},
        headers=ctx["member_headers"],
    )

    deleted = await client.delete(
        f"/api/sessions/{created['id']}", headers=ctx["owner_headers"]
    )
    assert deleted.status_code == 204
    # No orphaned RSVPs left behind to resurrect a deleted session.
    assert (
        await client.get(f"/api/sessions/{created['id']}/rsvps", headers=ctx["owner_headers"])
    ).status_code == 404


@pytest.mark.asyncio
async def test_my_sessions_spans_groups_and_excludes_past(
    client: AsyncClient, session_group
) -> None:
    ctx = session_group
    second = await _create_group(client, ctx["member_headers"], name="Second Group")
    await _create_session(
        client, ctx["owner_headers"], ctx["group"]["id"], title="Group one session"
    )
    await _create_session(
        client, ctx["member_headers"], second["id"], title="Group two session",
        start_time=_iso(timedelta(days=2)), end_time=_iso(timedelta(days=2, hours=1)),
    )
    await _create_session(
        client, ctx["owner_headers"], ctx["group"]["id"], title="Already done",
        start_time=_iso(timedelta(days=-3)), end_time=_iso(timedelta(days=-3, hours=1)),
    )

    response = await client.get("/api/sessions/mine", headers=ctx["member_headers"])
    assert response.status_code == 200
    titles = [item["title"] for item in response.json()]
    assert titles == ["Group one session", "Group two session"]
    assert response.json()[0]["group_name"] == ctx["group"]["name"]


@pytest.mark.asyncio
async def test_my_sessions_drops_groups_after_leaving(
    client: AsyncClient, session_group
) -> None:
    ctx = session_group
    await _create_session(client, ctx["owner_headers"], ctx["group"]["id"])

    assert len((await client.get("/api/sessions/mine", headers=ctx["member_headers"])).json()) == 1

    leave = await client.delete(
        f"/api/groups/{ctx['group']['id']}/leave", headers=ctx["member_headers"]
    )
    assert leave.status_code == 204

    after = await client.get("/api/sessions/mine", headers=ctx["member_headers"])
    assert after.json() == []


@pytest.mark.asyncio
async def test_deleting_group_removes_its_sessions(
    client: AsyncClient, session_group
) -> None:
    ctx = session_group
    created = await _create_session(client, ctx["owner_headers"], ctx["group"]["id"])

    deleted = await client.delete(
        f"/api/groups/{ctx['group']['id']}", headers=ctx["owner_headers"]
    )
    assert deleted.status_code == 204

    response = await client.get(
        f"/api/sessions/{created['id']}", headers=ctx["owner_headers"]
    )
    assert response.status_code == 404
