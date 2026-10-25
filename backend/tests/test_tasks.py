import pytest
from httpx import AsyncClient


async def _create_group(client: AsyncClient, headers: dict, name: str = "Algorithms Night") -> dict:
    response = await client.post(
        "/api/groups",
        json={"name": name, "course_code": "CS201"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_task(client: AsyncClient, headers: dict, group_id: str, **overrides) -> dict:
    payload = {"title": "Read chapter 4"}
    payload.update(overrides)
    response = await client.post(f"/api/groups/{group_id}/tasks", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
async def group_with_member(client: AsyncClient, auth_header):
    """An owner, a joined member, and their group."""
    owner_headers, owner = await auth_header(email="task-owner@university.edu")
    member_headers, member = await auth_header(email="task-member@university.edu")
    group = await _create_group(client, owner_headers)
    join = await client.post(f"/api/groups/{group['id']}/join", headers=member_headers)
    assert join.status_code == 200
    return {
        "group": group,
        "owner_headers": owner_headers,
        "owner": owner,
        "member_headers": member_headers,
        "member": member,
    }


@pytest.mark.asyncio
async def test_create_task_defaults(client: AsyncClient, group_with_member) -> None:
    ctx = group_with_member
    task = await _create_task(client, ctx["owner_headers"], ctx["group"]["id"])
    assert task["status"] == "TODO"
    assert task["priority"] == "MEDIUM"
    assert task["assigned_to"] is None
    assert task["created_by"] == ctx["owner"]["id"]
    assert task["creator"]["email"] == ctx["owner"]["email"]
    assert task["can_delete"] is True


@pytest.mark.asyncio
async def test_create_task_with_assignee_and_due_date(client: AsyncClient, group_with_member) -> None:
    ctx = group_with_member
    task = await _create_task(
        client,
        ctx["owner_headers"],
        ctx["group"]["id"],
        title="Finish problem set",
        description="Questions 1-5",
        assigned_to=ctx["member"]["id"],
        priority="HIGH",
        due_date="2026-10-01T17:00:00Z",
    )
    assert task["assigned_to"] == ctx["member"]["id"]
    assert task["assignee"]["email"] == ctx["member"]["email"]
    assert task["priority"] == "HIGH"
    assert task["due_date"].startswith("2026-10-01")


@pytest.mark.asyncio
async def test_cannot_assign_to_non_member(client: AsyncClient, group_with_member, auth_header) -> None:
    ctx = group_with_member
    _outsider_headers, outsider = await auth_header(email="outsider@university.edu")
    response = await client.post(
        f"/api/groups/{ctx['group']['id']}/tasks",
        json={"title": "Nope", "assigned_to": outsider["id"]},
        headers=ctx["owner_headers"],
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "assignee_not_member"


@pytest.mark.asyncio
async def test_blank_title_is_rejected(client: AsyncClient, group_with_member) -> None:
    ctx = group_with_member
    response = await client.post(
        f"/api/groups/{ctx['group']['id']}/tasks",
        json={"title": "   "},
        headers=ctx["owner_headers"],
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_invalid_status_is_rejected(client: AsyncClient, group_with_member) -> None:
    ctx = group_with_member
    response = await client.post(
        f"/api/groups/{ctx['group']['id']}/tasks",
        json={"title": "Bad status", "status": "ARCHIVED"},
        headers=ctx["owner_headers"],
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_tasks_and_filter_by_status(client: AsyncClient, group_with_member) -> None:
    ctx = group_with_member
    group_id = ctx["group"]["id"]
    await _create_task(client, ctx["owner_headers"], group_id, title="One")
    await _create_task(client, ctx["member_headers"], group_id, title="Two", status="DONE")

    everything = await client.get(f"/api/groups/{group_id}/tasks", headers=ctx["member_headers"])
    assert everything.status_code == 200
    assert everything.json()["total"] == 2

    done = await client.get(
        f"/api/groups/{group_id}/tasks",
        params={"status": "DONE"},
        headers=ctx["member_headers"],
    )
    assert done.json()["total"] == 1
    assert done.json()["items"][0]["title"] == "Two"


@pytest.mark.asyncio
async def test_list_tasks_filter_by_assignee(client: AsyncClient, group_with_member) -> None:
    ctx = group_with_member
    group_id = ctx["group"]["id"]
    await _create_task(client, ctx["owner_headers"], group_id, title="Unassigned")
    await _create_task(
        client,
        ctx["owner_headers"],
        group_id,
        title="Mine",
        assigned_to=ctx["member"]["id"],
    )
    response = await client.get(
        f"/api/groups/{group_id}/tasks",
        params={"assigned_to": ctx["member"]["id"]},
        headers=ctx["member_headers"],
    )
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["title"] == "Mine"


@pytest.mark.asyncio
async def test_tasks_ordered_by_due_date_with_undated_last(
    client: AsyncClient, group_with_member
) -> None:
    ctx = group_with_member
    group_id = ctx["group"]["id"]
    await _create_task(client, ctx["owner_headers"], group_id, title="No due date")
    await _create_task(
        client, ctx["owner_headers"], group_id, title="Later", due_date="2026-12-01T09:00:00Z"
    )
    await _create_task(
        client, ctx["owner_headers"], group_id, title="Sooner", due_date="2026-10-01T09:00:00Z"
    )
    response = await client.get(f"/api/groups/{group_id}/tasks", headers=ctx["owner_headers"])
    titles = [item["title"] for item in response.json()["items"]]
    assert titles == ["Sooner", "Later", "No due date"]


@pytest.mark.asyncio
async def test_member_can_move_task_between_statuses(client: AsyncClient, group_with_member) -> None:
    ctx = group_with_member
    task = await _create_task(client, ctx["owner_headers"], ctx["group"]["id"])

    in_progress = await client.patch(
        f"/api/tasks/{task['id']}",
        json={"status": "IN_PROGRESS"},
        headers=ctx["member_headers"],
    )
    assert in_progress.status_code == 200
    assert in_progress.json()["status"] == "IN_PROGRESS"

    done = await client.patch(
        f"/api/tasks/{task['id']}",
        json={"status": "DONE"},
        headers=ctx["member_headers"],
    )
    assert done.json()["status"] == "DONE"


@pytest.mark.asyncio
async def test_update_can_clear_assignee_and_due_date(client: AsyncClient, group_with_member) -> None:
    ctx = group_with_member
    task = await _create_task(
        client,
        ctx["owner_headers"],
        ctx["group"]["id"],
        assigned_to=ctx["member"]["id"],
        due_date="2026-10-01T17:00:00Z",
    )
    response = await client.patch(
        f"/api/tasks/{task['id']}",
        json={"assigned_to": None, "due_date": None},
        headers=ctx["owner_headers"],
    )
    assert response.status_code == 200
    assert response.json()["assigned_to"] is None
    assert response.json()["assignee"] is None
    assert response.json()["due_date"] is None


@pytest.mark.asyncio
async def test_empty_update_is_rejected(client: AsyncClient, group_with_member) -> None:
    ctx = group_with_member
    task = await _create_task(client, ctx["owner_headers"], ctx["group"]["id"])
    response = await client.patch(
        f"/api/tasks/{task['id']}", json={}, headers=ctx["owner_headers"]
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "empty_update"


@pytest.mark.asyncio
async def test_outsider_cannot_read_or_update_task(
    client: AsyncClient, group_with_member, auth_header
) -> None:
    """A task id from another group must not be usable by guessing it."""
    ctx = group_with_member
    outsider_headers, _ = await auth_header(email="outsider2@university.edu")
    task = await _create_task(client, ctx["owner_headers"], ctx["group"]["id"])

    read = await client.get(f"/api/tasks/{task['id']}", headers=outsider_headers)
    assert read.status_code == 403
    assert read.json()["error"]["code"] == "not_a_member"

    update = await client.patch(
        f"/api/tasks/{task['id']}",
        json={"title": "Hijacked"},
        headers=outsider_headers,
    )
    assert update.status_code == 403

    delete = await client.delete(f"/api/tasks/{task['id']}", headers=outsider_headers)
    assert delete.status_code == 403


@pytest.mark.asyncio
async def test_outsider_cannot_list_or_create_tasks(
    client: AsyncClient, group_with_member, auth_header
) -> None:
    ctx = group_with_member
    outsider_headers, _ = await auth_header(email="outsider3@university.edu")
    listed = await client.get(
        f"/api/groups/{ctx['group']['id']}/tasks", headers=outsider_headers
    )
    assert listed.status_code == 403
    created = await client.post(
        f"/api/groups/{ctx['group']['id']}/tasks",
        json={"title": "Sneaky"},
        headers=outsider_headers,
    )
    assert created.status_code == 403


@pytest.mark.asyncio
async def test_creator_can_delete_own_task(client: AsyncClient, group_with_member) -> None:
    ctx = group_with_member
    task = await _create_task(client, ctx["member_headers"], ctx["group"]["id"])
    response = await client.delete(f"/api/tasks/{task['id']}", headers=ctx["member_headers"])
    assert response.status_code == 204
    missing = await client.get(f"/api/tasks/{task['id']}", headers=ctx["member_headers"])
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_owner_can_delete_any_task(client: AsyncClient, group_with_member) -> None:
    ctx = group_with_member
    task = await _create_task(client, ctx["member_headers"], ctx["group"]["id"])
    response = await client.delete(f"/api/tasks/{task['id']}", headers=ctx["owner_headers"])
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_plain_member_cannot_delete_someone_elses_task(
    client: AsyncClient, group_with_member
) -> None:
    ctx = group_with_member
    task = await _create_task(client, ctx["owner_headers"], ctx["group"]["id"])
    response = await client.delete(f"/api/tasks/{task['id']}", headers=ctx["member_headers"])
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert task["can_delete"] is True  # owner sees the affordance


@pytest.mark.asyncio
async def test_can_delete_flag_reflects_permissions(client: AsyncClient, group_with_member) -> None:
    ctx = group_with_member
    await _create_task(client, ctx["owner_headers"], ctx["group"]["id"])
    listed = await client.get(
        f"/api/groups/{ctx['group']['id']}/tasks", headers=ctx["member_headers"]
    )
    assert listed.json()["items"][0]["can_delete"] is False


@pytest.mark.asyncio
async def test_unknown_task_is_404(client: AsyncClient, group_with_member) -> None:
    ctx = group_with_member
    response = await client.get(
        "/api/tasks/11111111-1111-1111-1111-111111111111", headers=ctx["owner_headers"]
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "task_not_found"


@pytest.mark.asyncio
async def test_tasks_require_auth(client: AsyncClient, group_with_member) -> None:
    ctx = group_with_member
    response = await client.get(f"/api/groups/{ctx['group']['id']}/tasks")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_my_tasks_across_groups(client: AsyncClient, group_with_member) -> None:
    ctx = group_with_member
    await _create_task(
        client,
        ctx["owner_headers"],
        ctx["group"]["id"],
        title="Assigned to member",
        assigned_to=ctx["member"]["id"],
        due_date="2026-10-01T09:00:00Z",
    )
    await _create_task(client, ctx["owner_headers"], ctx["group"]["id"], title="Unassigned")

    response = await client.get("/api/tasks/mine", headers=ctx["member_headers"])
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["title"] == "Assigned to member"
    assert body[0]["group_name"] == ctx["group"]["name"]


@pytest.mark.asyncio
async def test_my_tasks_excludes_done_by_default(client: AsyncClient, group_with_member) -> None:
    ctx = group_with_member
    task = await _create_task(
        client,
        ctx["owner_headers"],
        ctx["group"]["id"],
        assigned_to=ctx["member"]["id"],
    )
    await client.patch(
        f"/api/tasks/{task['id']}", json={"status": "DONE"}, headers=ctx["member_headers"]
    )
    default = await client.get("/api/tasks/mine", headers=ctx["member_headers"])
    assert default.json() == []
    including = await client.get(
        "/api/tasks/mine", params={"include_done": True}, headers=ctx["member_headers"]
    )
    assert len(including.json()) == 1


@pytest.mark.asyncio
async def test_leaving_a_group_unassigns_tasks(client: AsyncClient, group_with_member) -> None:
    ctx = group_with_member
    task = await _create_task(
        client,
        ctx["owner_headers"],
        ctx["group"]["id"],
        assigned_to=ctx["member"]["id"],
    )
    left = await client.delete(
        f"/api/groups/{ctx['group']['id']}/leave", headers=ctx["member_headers"]
    )
    assert left.status_code == 204

    after = await client.get(f"/api/tasks/{task['id']}", headers=ctx["owner_headers"])
    assert after.status_code == 200
    assert after.json()["assigned_to"] is None


@pytest.mark.asyncio
async def test_removing_a_member_unassigns_tasks(client: AsyncClient, group_with_member) -> None:
    ctx = group_with_member
    task = await _create_task(
        client,
        ctx["owner_headers"],
        ctx["group"]["id"],
        assigned_to=ctx["member"]["id"],
    )
    removed = await client.delete(
        f"/api/groups/{ctx['group']['id']}/members/{ctx['member']['id']}",
        headers=ctx["owner_headers"],
    )
    assert removed.status_code == 204

    after = await client.get(f"/api/tasks/{task['id']}", headers=ctx["owner_headers"])
    assert after.json()["assigned_to"] is None


@pytest.mark.asyncio
async def test_deleting_group_removes_its_tasks(client: AsyncClient, group_with_member) -> None:
    ctx = group_with_member
    task = await _create_task(client, ctx["owner_headers"], ctx["group"]["id"])
    deleted = await client.delete(
        f"/api/groups/{ctx['group']['id']}", headers=ctx["owner_headers"]
    )
    assert deleted.status_code == 204
    missing = await client.get(f"/api/tasks/{task['id']}", headers=ctx["owner_headers"])
    assert missing.status_code == 404
