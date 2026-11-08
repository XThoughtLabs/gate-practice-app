"""PATCH /tasks/{id} permissions (SPEC.md section 6.2): changes to someone else's task.

An admin may patch any task; a member only a task they created or are currently assigned.
A missing or unreadable task is a uniform 404; a readable task the actor may not change
(an observer's) is 403. Refusals change neither the task nor its status history.
"""

import pytest


HEADERS = {name: {"Authorization": f"Bearer demo-{name}"} for name in ("admin", "alice", "bob", "observer")}
IDS = {"admin": 1, "alice": 2, "bob": 3, "observer": 4}
NOT_FOUND = {"detail": "task not found"}

# name: (creator, assignee)
SHAPES = {
    "alice-unassigned": ("alice", None),
    "alice-for-bob": ("alice", "bob"),
    "bob-for-admin": ("bob", "admin"),
    "admin-for-alice": ("admin", "alice"),
    "admin-unassigned": ("admin", None),
}

# A body that changes fields and the status, so a wrongly accepted patch shows in both.
CHANGE = {"title": "Changed", "priority": 5, "status": "in_progress"}


def create(client, shape):
    creator, assignee = SHAPES[shape]
    body = {"title": f"Task {shape}", "assignee_id": IDS.get(assignee)}
    response = client.post("/tasks", json=body, headers=HEADERS[creator])
    assert response.status_code == 201, response.text
    return response.json()


def patch(client, task_id, body, actor):
    return client.patch(f"/tasks/{task_id}", json=body, headers=HEADERS[actor])


def set_status(client, task_id, status, actor="admin"):
    response = patch(client, task_id, {"status": status}, actor)
    assert response.status_code == 200, response.text
    return response.json()


def state(client, task_id):
    """The task's stored fields and its status history, as the administrator reads them."""
    task = client.get(f"/tasks/{task_id}", headers=HEADERS["admin"])
    events = client.get(f"/tasks/{task_id}/history", headers=HEADERS["admin"])
    assert (task.status_code, events.status_code) == (200, 200), (task.text, events.text)
    return task.json(), events.json()["items"]


def assert_refused(client, task_id, body, actor, status):
    before = state(client, task_id)
    response = patch(client, task_id, body, actor)
    assert response.status_code == status, response.text
    if status == 404:
        assert response.json() == NOT_FOUND
    assert state(client, task_id) == before


def assert_applied(client, task_id, body, actor):
    _, events = state(client, task_id)
    response = patch(client, task_id, body, actor)
    assert response.status_code == 200, response.text
    task, after = state(client, task_id)
    assert response.json() == task
    assert {field: task[field] for field in body} == body
    assert [(e["actor_id"], e["from_status"], e["to_status"]) for e in after[len(events):]] == [
        (IDS[actor], "todo", "in_progress")]


# --- who may patch --------------------------------------------------------------------


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_admin_patches_any_task(client, shape):
    task = create(client, shape)
    assert_applied(client, task["id"], CHANGE, "admin")


@pytest.mark.parametrize(("shape", "actor"), [
    ("alice-unassigned", "alice"),   # creator
    ("alice-for-bob", "alice"),      # creator of a task assigned to another member
    ("alice-for-bob", "bob"),        # current assignee of another member's task
    ("bob-for-admin", "bob"),        # creator of a task assigned to the admin
    ("admin-for-alice", "alice"),    # current assignee of the admin's task
])
def test_member_patches_as_creator_or_current_assignee(client, shape, actor):
    task = create(client, shape)
    assert_applied(client, task["id"], CHANGE, actor)


@pytest.mark.parametrize(("shape", "actor"), [
    ("alice-unassigned", "bob"),
    ("bob-for-admin", "alice"),
    ("admin-for-alice", "bob"),
    ("admin-unassigned", "alice"),
    ("admin-unassigned", "bob"),
])
def test_member_neither_creator_nor_assignee_gets_404(client, shape, actor):
    # SPEC.md section 1: the member cannot read the task, so the refusal is a uniform 404.
    task = create(client, shape)
    assert_refused(client, task["id"], CHANGE, actor, 404)
    assert patch(client, task["id"], {"title": "Still not"}, actor).status_code == 404


# --- missing, unreadable and forbidden ------------------------------------------------


@pytest.mark.parametrize("actor", sorted(HEADERS))
@pytest.mark.parametrize("body", [{"title": "Nothing there"}, {"status": "in_progress"}], ids=["title", "status"])
def test_patch_of_a_missing_task_is_404_for_every_role(client, actor, body):
    existing = create(client, "admin-unassigned")
    response = patch(client, existing["id"] + 1, body, actor)
    assert (response.status_code, response.json()) == (404, NOT_FOUND)
    listed = client.get("/tasks", headers=HEADERS["admin"]).json()
    assert [row["id"] for row in listed["items"]] == [existing["id"]]


# Bodies that the task's own creator would get 200, 409 or 422 for: an unreadable task
# must answer them all with the same 404 as a missing task, and change nothing.
UNREADABLE_BODIES = {
    "title": {"title": "Bob was here"},
    "start": {"status": "in_progress"},
    "skipped-transition": {"status": "done"},
    "observer-assignee": {"assignee_id": 4},
    "unknown-assignee": {"assignee_id": 999},
    "self-assignment": {"assignee_id": 3},
}


@pytest.mark.parametrize("body", sorted(UNREADABLE_BODIES))
def test_unreadable_task_is_404_like_a_missing_task_whatever_the_body(client, body):
    task = create(client, "alice-unassigned")
    missing = patch(client, task["id"] + 1, UNREADABLE_BODIES[body], "bob")
    assert_refused(client, task["id"], UNREADABLE_BODIES[body], "bob", 404)
    assert (missing.status_code, missing.json()) == (404, NOT_FOUND)


@pytest.mark.parametrize("shape", sorted(SHAPES))
@pytest.mark.parametrize("body", [
    {"title": "Observer was here"},
    {"status": "in_progress"},
    {"status": "done"},             # a skipped transition: 403 comes first, not 409
    {"assignee_id": 4},             # the observer's own ID: 403 comes first, not 422
    {"assignee_id": 2},
    CHANGE,
], ids=["title", "start", "skipped-transition", "own-id", "assign-alice", "several-fields"])
def test_observer_patch_of_a_readable_task_is_403(client, shape, body):
    task = create(client, shape)
    assert client.get(f"/tasks/{task['id']}", headers=HEADERS["observer"]).status_code == 200
    assert_refused(client, task["id"], body, "observer", 403)


# --- the stored, pre-update assignment decides ----------------------------------------


@pytest.mark.parametrize("body", [{"assignee_id": 3}, {"assignee_id": 3, **CHANGE}], ids=["alone", "with-changes"])
def test_member_cannot_grant_themselves_access_with_their_own_id(client, body):
    task = create(client, "alice-unassigned")
    assert_refused(client, task["id"], body, "bob", 404)
    assert state(client, task["id"])[0]["assignee_id"] is None
    assert patch(client, task["id"], {"title": "Bob, after trying"}, "bob").status_code == 404
    assert client.get("/tasks", headers=HEADERS["bob"]).json()["total"] == 0


def test_current_assignee_may_hand_the_task_away_and_then_loses_access(client):
    task = create(client, "admin-for-alice")
    response = patch(client, task["id"], {"assignee_id": 3, "status": "in_progress"}, "alice")
    assert response.status_code == 200, response.text
    assert (response.json()["assignee_id"], response.json()["status"]) == (3, "in_progress")
    assert_refused(client, task["id"], {"title": "Alice again"}, "alice", 404)
    assert patch(client, task["id"], {"title": "Bob's now"}, "bob").status_code == 200


def test_former_assignee_cannot_patch(client):
    task = create(client, "admin-for-alice")
    assert patch(client, task["id"], {"assignee_id": 3}, "admin").status_code == 200
    assert_refused(client, task["id"], CHANGE, "alice", 404)
    assert_applied(client, task["id"], CHANGE, "bob")


def test_authorization_is_judged_against_the_stored_assignment(client, monkeypatch):
    # Alice's request first reads the task while she is its assignee; the admin hands it to
    # Bob before her write. The write transaction's stored row decides: a uniform 404.
    store = client.app.state.service.store
    task = create(client, "admin-for-alice")
    earlier_read = store.task(task["id"])
    assert patch(client, task["id"], {"assignee_id": 3}, "admin").status_code == 200
    before = state(client, task["id"])
    monkeypatch.setattr(store, "task", lambda task_id: dict(earlier_read))
    response = patch(client, task["id"], CHANGE, "alice")
    monkeypatch.undo()
    assert (response.status_code, response.json()) == (404, NOT_FOUND)
    assert state(client, task["id"]) == before


# --- rejected patches change nothing --------------------------------------------------


REJECTED = {
    # name: (shape, status the admin moves the task to first, actor, body, expected status code)
    "unrelated-member-fields": ("alice-unassigned", "todo", "bob", {"title": "X", "priority": 1}, 404),
    "unrelated-member-status": ("admin-for-alice", "in_progress", "bob", {"status": "done"}, 404),
    "unrelated-member-reassign": ("admin-for-alice", "todo", "bob", {"assignee_id": 2}, 404),
    "unrelated-member-clear": ("admin-for-alice", "todo", "bob", {"assignee_id": None, "due_at": None}, 404),
    "observer-fields": ("alice-for-bob", "todo", "observer", {"description": "Seen", "due_at": None}, 403),
    "observer-status": ("alice-for-bob", "in_progress", "observer", {"status": "done"}, 403),
    "observer-reopen": ("alice-for-bob", "done", "observer", {"status": "in_progress"}, 403),
}


@pytest.mark.parametrize("case", sorted(REJECTED))
def test_rejected_patch_changes_neither_fields_nor_history(client, case):
    shape, start, actor, body, expected = REJECTED[case]
    task = create(client, shape)
    for step in ("in_progress", "done")[:("todo", "in_progress", "done").index(start)]:
        set_status(client, task["id"], step)
    assert_refused(client, task["id"], body, actor, expected)


# --- reopen and work entries stay as they were ----------------------------------------


@pytest.mark.parametrize(("shape", "actor", "expected"), [
    ("alice-for-bob", "alice", 403),      # creator: may patch, may not reopen
    ("alice-for-bob", "bob", 403),        # current assignee: may patch, may not reopen
    ("admin-for-alice", "bob", 404),      # unrelated member: cannot read the task at all
    ("alice-for-bob", "observer", 403),
])
def test_reopen_restriction_still_applies(client, shape, actor, expected):
    task = create(client, shape)
    set_status(client, task["id"], "in_progress")
    set_status(client, task["id"], "done")
    assert_refused(client, task["id"], {"status": "in_progress"}, actor, expected)
    assert_refused(client, task["id"], {"status": "in_progress", "title": "Reopened?"}, actor, expected)
    reopened = set_status(client, task["id"], "in_progress", "admin")
    assert state(client, task["id"])[1][-1] == {
        "sequence": 4, "actor_id": 1, "from_status": "done", "to_status": "in_progress",
        "changed_at": reopened["updated_at"], "origin": "operation"}


def test_work_entry_permissions_are_unchanged(client):
    # SPEC.md section 3: admin/member with task visibility; observers never write.
    task = create(client, "admin-for-alice")
    path = f"/tasks/{task['id']}/work"
    for actor in ("alice", "admin"):
        response = client.post(path, json={"minutes": 10}, headers=HEADERS[actor])
        assert response.status_code == 200, response.text
    refused = client.post(path, json={"minutes": 10}, headers=HEADERS["bob"])
    assert (refused.status_code, refused.json()) == (404, NOT_FOUND)
    assert client.post(path, json={"minutes": 10}, headers=HEADERS["observer"]).status_code == 403
    logs = client.get(path, headers=HEADERS["admin"]).json()["items"]
    assert [(entry["actor_id"], entry["minutes"]) for entry in logs] == [(2, 10), (1, 10)]
    assert state(client, task["id"])[0]["work_minutes"] == 20
