"""GET /tasks/{id} (SPEC.md sections 1 and 3): a visible task, otherwise a uniform 404.

An administrator or observer reads every task; a member only a task they created or are
currently assigned. A missing or unreadable task is 404 with {"detail": "task not found"}
for every role, the same answer the work log and history endpoints give.
"""

import pytest


HEADERS = {name: {"Authorization": f"Bearer demo-{name}"} for name in ("admin", "alice", "bob", "observer")}
IDS = {"admin": 1, "alice": 2, "bob": 3, "observer": 4}
NOT_FOUND = {"detail": "task not found"}
MISSING_TASK_ID = 999_999

# name: (creator, assignee)
SHAPES = {
    "alice-unassigned": ("alice", None),
    "alice-for-bob": ("alice", "bob"),
    "bob-for-admin": ("bob", "admin"),
    "admin-for-alice": ("admin", "alice"),
    "admin-unassigned": ("admin", None),
}


def create(client, shape):
    creator, assignee = SHAPES[shape]
    body = {"title": f"Task {shape}", "assignee_id": IDS.get(assignee)}
    response = client.post("/tasks", json=body, headers=HEADERS[creator])
    assert response.status_code == 201, response.text
    return response.json()


def read(client, task_id, actor):
    return client.get(f"/tasks/{task_id}", headers=HEADERS[actor])


def patch(client, task_id, body, actor):
    return client.patch(f"/tasks/{task_id}", json=body, headers=HEADERS[actor])


def stored(client, task_id):
    response = read(client, task_id, "admin")
    assert response.status_code == 200, response.text
    return response.json()


def assert_reads(client, task_id, actor):
    response = read(client, task_id, actor)
    assert response.status_code == 200, response.text
    assert response.json() == stored(client, task_id)


def assert_hidden(client, task_id, actor):
    # The refusal says nothing about the task: the same status, body and type as a missing task.
    response = read(client, task_id, actor)
    missing = read(client, MISSING_TASK_ID, actor)
    assert (response.status_code, response.json()) == (404, NOT_FOUND)
    assert (response.content, response.headers["content-type"]) == (
        missing.content, missing.headers["content-type"])
    assert stored(client, task_id)["id"] == task_id


# --- who may read ---------------------------------------------------------------------


@pytest.mark.parametrize("actor", ["admin", "observer"])
@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_admin_and_observer_read_every_task(client, shape, actor):
    task = create(client, shape)
    response = read(client, task["id"], actor)
    assert response.status_code == 200, response.text
    assert response.json() == task


@pytest.mark.parametrize(("shape", "actor"), [
    ("alice-unassigned", "alice"),   # creator
    ("alice-for-bob", "alice"),      # creator of a task assigned to another member
    ("alice-for-bob", "bob"),        # current assignee of another member's task
    ("bob-for-admin", "bob"),        # creator of a task assigned to the admin
    ("admin-for-alice", "alice"),    # current assignee of the admin's task
])
def test_member_reads_as_creator_or_current_assignee(client, shape, actor):
    task = create(client, shape)
    response = read(client, task["id"], actor)
    assert response.status_code == 200, response.text
    assert response.json() == task


# --- unreadable and missing -----------------------------------------------------------


@pytest.mark.parametrize(("shape", "actor"), [
    ("alice-unassigned", "bob"),
    ("bob-for-admin", "alice"),
    ("admin-for-alice", "bob"),
    ("admin-unassigned", "alice"),
    ("admin-unassigned", "bob"),
])
def test_member_neither_creator_nor_assignee_gets_404(client, shape, actor):
    task = create(client, shape)
    assert_hidden(client, task["id"], actor)


@pytest.mark.parametrize(("change", "by"), [
    ({"assignee_id": 3}, "admin"),       # the admin hands the task to Bob
    ({"assignee_id": None}, "admin"),    # the admin clears the assignment
    ({"assignee_id": 3}, "alice"),       # Alice hands the task away herself
], ids=["reassigned", "unassigned", "handed-away"])
def test_former_assignee_gets_404(client, change, by):
    task = create(client, "admin-for-alice")
    assert_reads(client, task["id"], "alice")
    assert patch(client, task["id"], change, by).status_code == 200
    assert_hidden(client, task["id"], "alice")
    if change["assignee_id"] == 3:
        assert_reads(client, task["id"], "bob")
    else:
        assert_hidden(client, task["id"], "bob")


def test_creator_keeps_read_access_after_reassignment(client):
    task = create(client, "alice-for-bob")
    assert patch(client, task["id"], {"assignee_id": 1}, "admin").status_code == 200
    assert_reads(client, task["id"], "alice")
    assert_hidden(client, task["id"], "bob")


def test_member_cannot_grant_self_read_access_by_assigning_self(client):
    # SPEC.md section 6.2: an unauthorized patch with the member's own ID grants nothing.
    task = create(client, "alice-unassigned")
    refused = patch(client, task["id"], {"assignee_id": 3}, "bob")
    assert (refused.status_code, refused.json()) == (404, NOT_FOUND)
    assert stored(client, task["id"]) == task
    assert_hidden(client, task["id"], "bob")


@pytest.mark.parametrize("actor", sorted(HEADERS))
def test_missing_task_is_404_for_every_role(client, actor):
    existing = create(client, "admin-unassigned")
    for task_id in (existing["id"] + 1, 0, MISSING_TASK_ID):
        response = read(client, task_id, actor)
        assert (response.status_code, response.json()) == (404, NOT_FOUND), task_id
