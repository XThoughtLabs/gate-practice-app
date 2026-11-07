"""Acceptance tests for SPEC.md section 6.2: changes to someone else's task.

Written from SPEC.md, TASK.md, OPEN-ISSUES.md and README.md alone, without the
application's code. Each test runs the documented entry point
workflow.api:create_app(db_path) on its own temporary SQLite file, with the
fixture tokens of README.md and synthetic data only.
"""

from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from workflow.api import create_app

TOKENS = {
    "admin": "demo-admin",
    "alice": "demo-alice",
    "bob": "demo-bob",
    "observer": "demo-observer",
}
NOT_FOUND = {"detail": "task not found"}
MISSING_TASK_ID = 999_999


def auth(actor):
    return {"Authorization": f"Bearer {TOKENS[actor]}"}


@contextmanager
def running_app(db_path):
    with TestClient(create_app(db_path=db_path), raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def client(tmp_path):
    with running_app(str(tmp_path / "workflow.sqlite3")) as test_client:
        yield test_client


@pytest.fixture
def ids(client):
    return user_ids(client)


def directory_entries(body):
    # SPEC.md fixes the directory's fields, not its envelope: a list or an items list.
    if isinstance(body, dict):
        body = body.get("items", body.get("users"))
    assert isinstance(body, list), body
    return body


def user_ids(client):
    response = client.get("/users", headers=auth("admin"))
    assert response.status_code == 200, response.text
    found = {}
    for entry in directory_entries(response.json()):
        role, name = entry["role"], str(entry["name"]).lower()
        if role in ("admin", "observer"):
            found[role] = entry["id"]
        elif role == "member" and "alice" in name:
            found["alice"] = entry["id"]
        elif role == "member" and "bob" in name:
            found["bob"] = entry["id"]
    assert set(found) == set(TOKENS), response.text
    return found


def create_task(client, actor, **fields):
    response = client.post("/tasks", json={"title": "Synthetic task", **fields}, headers=auth(actor))
    assert response.status_code == 201, response.text
    return response.json()


def get_task(client, task_id, actor="admin"):
    response = client.get(f"/tasks/{task_id}", headers=auth(actor))
    assert response.status_code == 200, response.text
    return response.json()


def patch_task(client, task_id, body, actor):
    return client.patch(f"/tasks/{task_id}", json=body, headers=auth(actor))


def set_status(client, task_id, status, actor):
    response = patch_task(client, task_id, {"status": status}, actor)
    assert response.status_code == 200, response.text
    return response.json()


def history(client, task_id):
    response = client.get(f"/tasks/{task_id}/history", headers=auth("admin"))
    assert response.status_code == 200, response.text
    return response.json()["items"]


def stored(client, task_id):
    """The task's fields and its status history, as an administrator reads them."""
    return get_task(client, task_id), history(client, task_id)


# --- who may patch ---------------------------------------------------------------------


def test_spec_6_2_admin_may_patch_any_task(client, ids):
    """SPEC.md section 6.2: an admin may patch any task, including one created and assigned by others."""
    task = create_task(client, "alice", title="Alice's, for Bob", assignee_id=ids["bob"])
    response = patch_task(client, task["id"], {"title": "Edited by the admin", "priority": 1}, "admin")
    assert response.status_code == 200, response.text
    after = get_task(client, task["id"])
    assert (after["title"], after["priority"]) == ("Edited by the admin", 1)


def test_spec_6_2_creator_may_patch_a_task_assigned_to_another(client, ids):
    """SPEC.md section 6.2: a member may patch a task they created, even when another is its assignee."""
    task = create_task(client, "alice", title="Alice's, for Bob", assignee_id=ids["bob"])
    response = patch_task(client, task["id"], {"title": "Edited by the creator"}, "alice")
    assert response.status_code == 200, response.text
    assert get_task(client, task["id"])["title"] == "Edited by the creator"


def test_spec_6_2_current_assignee_may_patch_the_task(client, ids):
    """SPEC.md section 6.2: a member may patch a task they are currently assigned."""
    task = create_task(client, "admin", title="Admin's, for Bob", assignee_id=ids["bob"])
    response = patch_task(client, task["id"], {"title": "Edited by the assignee", "status": "in_progress"}, "bob")
    assert response.status_code == 200, response.text
    after = get_task(client, task["id"])
    assert (after["title"], after["status"]) == ("Edited by the assignee", "in_progress")


# --- who may not -----------------------------------------------------------------------


UNRELATED_BODIES = {
    "title": lambda ids: {"title": "Bob was here"},
    "status": lambda ids: {"status": "in_progress"},
    "priority": lambda ids: {"priority": 5},
}


@pytest.mark.parametrize("change", sorted(UNRELATED_BODIES))
def test_spec_6_2_member_cannot_patch_unrelated_task(client, ids, change):
    """SPEC.md section 6.2: a member neither creator nor assignee cannot read the task, so PATCH is a
    uniform 404 that changes neither the task nor its history."""
    task = create_task(client, "alice", title="Alice's own")
    before = stored(client, task["id"])
    response = patch_task(client, task["id"], UNRELATED_BODIES[change](ids), "bob")
    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert stored(client, task["id"]) == before


def test_spec_6_2_member_cannot_patch_task_assigned_to_someone_else(client, ids):
    """SPEC.md section 6.2: a member who did not create a task and is not its assignee cannot patch it."""
    task = create_task(client, "admin", title="Admin's, for Alice", assignee_id=ids["alice"])
    before = stored(client, task["id"])
    response = patch_task(client, task["id"], {"title": "Bob was here"}, "bob")
    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert stored(client, task["id"]) == before


def test_spec_6_2_member_cannot_grant_self_access_by_assigning_self(client, ids):
    """SPEC.md section 6.2: authorization uses the stored pre-update assignment; sending one's own ID
    in an unauthorized patch grants nothing."""
    task = create_task(client, "alice", title="Alice's own")
    before = stored(client, task["id"])
    response = patch_task(client, task["id"], {"assignee_id": ids["bob"]}, "bob")
    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert stored(client, task["id"]) == before
    hidden = client.get(f"/tasks/{task['id']}", headers=auth("bob"))
    assert hidden.status_code == 404
    assert hidden.json() == NOT_FOUND


def test_spec_6_2_assignee_may_reassign_the_task_away(client, ids):
    """SPEC.md section 6.2: authorization uses the stored pre-update assignment, so the current assignee
    may hand the task to another; afterwards they no longer have access."""
    task = create_task(client, "admin", title="Admin's, for Bob", assignee_id=ids["bob"])
    response = patch_task(client, task["id"], {"assignee_id": ids["alice"]}, "bob")
    assert response.status_code == 200, response.text
    assert get_task(client, task["id"])["assignee_id"] == ids["alice"]
    again = patch_task(client, task["id"], {"title": "Bob again"}, "bob")
    assert again.status_code == 404
    assert again.json() == NOT_FOUND
    assert patch_task(client, task["id"], {"title": "Alice's now"}, "alice").status_code == 200


def test_spec_6_2_former_assignee_cannot_patch(client, ids):
    """SPEC.md section 6.2: only the current assignee may patch; a former assignee gets a uniform 404."""
    task = create_task(client, "admin", title="Moves from Bob to Alice", assignee_id=ids["bob"])
    assert patch_task(client, task["id"], {"assignee_id": ids["alice"]}, "admin").status_code == 200
    before = stored(client, task["id"])
    response = patch_task(client, task["id"], {"status": "in_progress"}, "bob")
    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert stored(client, task["id"]) == before


OBSERVER_BODIES = {
    "title": lambda ids: {"title": "Observer was here"},
    "status": lambda ids: {"status": "in_progress"},
    "assignee": lambda ids: {"assignee_id": ids["alice"]},
    "everything": lambda ids: {"title": "Observer", "status": "in_progress", "priority": 5},
}


@pytest.mark.parametrize("change", sorted(OBSERVER_BODIES))
def test_spec_6_2_observer_patch_returns_403(client, ids, change):
    """SPEC.md section 6.2: a readable task patched by an observer returns 403 and changes neither
    the task nor its history."""
    task = create_task(client, "alice", title="Watched", assignee_id=ids["bob"])
    before = stored(client, task["id"])
    response = patch_task(client, task["id"], OBSERVER_BODIES[change](ids), "observer")
    assert response.status_code == 403, response.text
    assert stored(client, task["id"]) == before


def test_spec_6_2_observer_patch_of_missing_task_returns_404(client):
    """SPEC.md sections 1 and 6.2: a missing task is unreadable, so even an observer's PATCH is a uniform 404."""
    response = patch_task(client, MISSING_TASK_ID, {"title": "Nothing there"}, "observer")
    assert response.status_code == 404
    assert response.json() == NOT_FOUND


# --- reopen and work stay as they were -------------------------------------------------


@pytest.mark.parametrize("actor", ["alice", "bob"], ids=["creator", "assignee"])
def test_spec_6_2_reopen_restriction_still_applies(client, ids, actor):
    """SPEC.md sections 2 and 6.2: a member allowed to patch still cannot reopen done → in_progress.
    Its status code is checked in test_spec_2_member_cannot_reopen_done_task; here the refusal,
    the unchanged task and history, and the administrator's reopen."""
    task = create_task(client, "alice", title="Closed", assignee_id=ids["bob"])
    set_status(client, task["id"], "in_progress", "alice")
    set_status(client, task["id"], "done", "bob")
    before = stored(client, task["id"])
    response = patch_task(client, task["id"], {"status": "in_progress"}, actor)
    assert response.status_code in (403, 409), response.text
    assert stored(client, task["id"]) == before
    assert set_status(client, task["id"], "in_progress", "admin")["status"] == "in_progress"


def test_spec_6_2_work_permissions_are_unchanged(client, ids):
    """SPEC.md section 6.2: the PATCH rule does not change work-entry permissions."""
    task = create_task(client, "admin", title="Admin's, for Bob", assignee_id=ids["bob"])
    for actor in ("bob", "admin"):
        response = client.post(f"/tasks/{task['id']}/work", json={"minutes": 10}, headers=auth(actor))
        assert response.status_code == 200, response.text
    refused = client.post(f"/tasks/{task['id']}/work", json={"minutes": 10}, headers=auth("alice"))
    assert refused.status_code == 404
    assert refused.json() == NOT_FOUND
    assert get_task(client, task["id"])["work_minutes"] == 20
