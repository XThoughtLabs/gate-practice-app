"""Acceptance tests for SPEC.md section 1: identity and visibility.

Written from SPEC.md, TASK.md, OPEN-ISSUES.md and README.md alone, without the
application's code. Each test runs the documented entry point
workflow.api:create_app(db_path) on its own temporary SQLite file, with the
fixture tokens of README.md and synthetic data only.
"""

import csv
import io
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
INVALID_TOKEN = {"Authorization": "Bearer not-a-fixture-token"}


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


def listed(client, actor, **params):
    """The IDs on one page of GET /tasks and the reported total."""
    response = client.get("/tasks", params={"limit": 100, **params}, headers=auth(actor))
    assert response.status_code == 200, response.text
    body = response.json()
    return [item["id"] for item in body["items"]], body["total"]


def overdue_ids(client, actor, at):
    response = client.get("/tasks/overdue", params={"at": at}, headers=auth(actor))
    assert response.status_code == 200, response.text
    body = response.json()
    # SPEC.md fixes the content of the overdue view, not its envelope.
    items = body["items"] if isinstance(body, dict) else body
    return [item["id"] for item in items]


def export_ids(client, actor):
    response = client.get("/tasks/export", headers=auth(actor))
    assert response.status_code == 200, response.text
    # A UTF-8 byte-order mark is tolerated; SPEC.md says only "UTF-8 CSV".
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"), newline="")))
    return sorted(int(row[0]) for row in rows[1:])


def stored_state(client, task_id):
    """What an administrator can read about one task and about the task collection."""
    task = client.get(f"/tasks/{task_id}", headers=auth("admin"))
    work = client.get(f"/tasks/{task_id}/work", headers=auth("admin"))
    assert task.status_code == 200, task.text
    assert work.status_code == 200, work.text
    return task.json(), work.json(), listed(client, "admin")


@pytest.fixture
def mixed(client, ids):
    """Six tasks of different creators and assignees, and who may read which."""
    alice_one = create_task(client, "alice", title="Alice one")["id"]
    alice_two = create_task(client, "alice", title="Alice two")["id"]
    bob_one = create_task(client, "bob", title="Bob one")["id"]
    admin_for_bob = create_task(client, "admin", title="Admin for Bob", assignee_id=ids["bob"])["id"]
    admin_alone = create_task(client, "admin", title="Admin unassigned")["id"]
    alice_for_bob = create_task(client, "alice", title="Alice for Bob", assignee_id=ids["bob"])["id"]
    return {
        "alice": sorted([alice_one, alice_two, alice_for_bob]),
        "bob": sorted([bob_one, admin_for_bob, alice_for_bob]),
        "all": sorted([alice_one, alice_two, bob_one, admin_for_bob, admin_alone, alice_for_bob]),
    }


def test_spec_1_health_is_public(client):
    """SPEC.md section 1: /health is public and needs no token."""
    response = client.get("/health")
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("path", ["/openapi.json", "/docs"])
def test_spec_1_openapi_documentation_is_public(client, path):
    """SPEC.md section 1: the OpenAPI documentation is public and needs no token."""
    response = client.get(path)
    assert response.status_code == 200, response.text


PROTECTED = [
    ("GET", "/users", None),
    ("POST", "/tasks", {"title": "Unauthenticated task"}),
    ("GET", "/tasks", None),
    ("GET", "/tasks/overdue?at=2026-03-01T10:00:00Z", None),
    ("GET", "/tasks/export", None),
    ("GET", "/tasks/{task_id}", None),
    ("PATCH", "/tasks/{task_id}", {"title": "Unauthenticated change"}),
    ("POST", "/tasks/{task_id}/work", {"minutes": 5}),
    ("GET", "/tasks/{task_id}/work", None),
    ("GET", "/tasks/{task_id}/history", None),
]
CREDENTIALS = {"missing": {}, "invalid": INVALID_TOKEN}


@pytest.mark.parametrize("credential", sorted(CREDENTIALS))
@pytest.mark.parametrize(
    ("method", "path", "body"), PROTECTED, ids=[f"{method} {path}" for method, path, _ in PROTECTED]
)
def test_spec_1_business_endpoints_require_a_valid_token(client, method, path, body, credential):
    """SPEC.md section 1: every business endpoint returns 401 for a missing or invalid token."""
    task = create_task(client, "alice", title="Protected task")
    response = client.request(
        method, path.format(task_id=task["id"]), json=body, headers=CREDENTIALS[credential]
    )
    assert response.status_code == 401, response.text


def test_spec_1_unauthenticated_writes_change_nothing(client):
    """SPEC.md sections 1 and 2: writes refused with 401 create, change and log nothing."""
    task = create_task(client, "alice", title="Original title")
    before = stored_state(client, task["id"])
    path = f"/tasks/{task['id']}"
    assert client.post("/tasks", json={"title": "Sneaked in"}, headers=INVALID_TOKEN).status_code == 401
    assert client.patch(path, json={"title": "Sneaked change"}, headers=INVALID_TOKEN).status_code == 401
    assert client.post(f"{path}/work", json={"minutes": 30}, headers=INVALID_TOKEN).status_code == 401
    assert stored_state(client, task["id"]) == before


@pytest.mark.parametrize("actor", sorted(TOKENS))
def test_spec_1_user_listing_never_returns_tokens(client, actor):
    """SPEC.md section 1: user listings never return bearer tokens, whoever asks."""
    response = client.get("/users", headers=auth(actor))
    for token in TOKENS.values():
        assert token not in response.text
    if response.status_code == 200:
        for entry in directory_entries(response.json()):
            assert not [key for key in entry if "token" in key.lower()], entry


@pytest.mark.parametrize("actor", ["admin", "observer"])
def test_spec_1_admin_and_observer_read_any_task(client, actor):
    """SPEC.md section 1: an administrator or observer may read all tasks."""
    task = create_task(client, "alice", title="Alice's unassigned task")
    response = client.get(f"/tasks/{task['id']}", headers=auth(actor))
    assert response.status_code == 200, response.text
    assert response.json()["id"] == task["id"]


def test_spec_1_member_reads_task_they_created(client, ids):
    """SPEC.md section 1: a member may read a task they created, even when it is assigned to another."""
    task = create_task(client, "alice", title="Created by Alice for Bob", assignee_id=ids["bob"])
    response = client.get(f"/tasks/{task['id']}", headers=auth("alice"))
    assert response.status_code == 200, response.text
    assert response.json()["id"] == task["id"]


def test_spec_1_member_reads_task_assigned_to_them(client, ids):
    """SPEC.md section 1: a member may read a task they are assigned."""
    task = create_task(client, "admin", title="Assigned to Bob", assignee_id=ids["bob"])
    response = client.get(f"/tasks/{task['id']}", headers=auth("bob"))
    assert response.status_code == 200, response.text
    assert response.json()["id"] == task["id"]


def test_spec_1_member_cannot_read_unrelated_task(client):
    """SPEC.md section 1: an unreadable task returns 404 with {"detail":"task not found"}."""
    task = create_task(client, "alice", title="Alice's private task")
    response = client.get(f"/tasks/{task['id']}", headers=auth("bob"))
    assert response.status_code == 404
    assert response.json() == NOT_FOUND


@pytest.mark.parametrize("actor", ["admin", "alice", "observer"])
def test_spec_1_missing_task_returns_task_not_found(client, actor):
    """SPEC.md section 1: a missing task returns 404 with {"detail":"task not found"}."""
    response = client.get(f"/tasks/{MISSING_TASK_ID}", headers=auth(actor))
    assert response.status_code == 404
    assert response.json() == NOT_FOUND


def test_spec_1_member_loses_read_access_when_no_longer_assigned(client, ids):
    """SPEC.md section 1: a member reads only tasks they created or are currently assigned."""
    task = create_task(client, "admin", title="Moves from Bob to Alice", assignee_id=ids["bob"])
    assert client.get(f"/tasks/{task['id']}", headers=auth("bob")).status_code == 200
    moved = client.patch(f"/tasks/{task['id']}", json={"assignee_id": ids["alice"]}, headers=auth("admin"))
    assert moved.status_code == 200, moved.text
    response = client.get(f"/tasks/{task['id']}", headers=auth("bob"))
    assert response.status_code == 404
    assert response.json() == NOT_FOUND


@pytest.mark.parametrize("actor", ["alice", "bob"])
def test_spec_1_member_list_contains_only_visible_tasks(client, mixed, actor):
    """SPEC.md section 1: a member's task list holds only tasks they created or are assigned."""
    assert listed(client, actor) == (mixed[actor], 3)


@pytest.mark.parametrize("actor", ["admin", "observer"])
def test_spec_1_admin_and_observer_list_all_tasks(client, mixed, actor):
    """SPEC.md section 1: an administrator or observer lists all tasks."""
    assert listed(client, actor) == (mixed["all"], 6)


@pytest.mark.parametrize(("limit", "offset", "positions"), [(1, 0, [0]), (2, 2, [2]), (2, 3, [])])
def test_spec_1_member_list_total_leaks_no_global_count(client, mixed, limit, offset, positions):
    """SPEC.md section 1: no global task count leaks through a member's paged list."""
    expected = [mixed["bob"][position] for position in positions]
    assert listed(client, "bob", limit=limit, offset=offset) == (expected, 3)


def test_spec_1_member_search_returns_only_visible_matches(client):
    """SPEC.md section 1: search obeys the visibility rule, in its items and its total."""
    alice_task = create_task(client, "alice", title="Budget review")["id"]
    bob_task = create_task(client, "bob", title="Budget plan")["id"]
    create_task(client, "admin", title="Budget nobody else sees")
    assert listed(client, "bob", q="budget") == ([bob_task], 1)
    assert listed(client, "alice", q="budget") == ([alice_task], 1)


def test_spec_1_member_overdue_view_shows_only_visible_tasks(client):
    """SPEC.md section 1: the overdue view obeys the visibility rule."""
    past = "2026-01-01T09:00:00Z"
    create_task(client, "alice", title="Alice overdue", due_at=past)
    bob_task = create_task(client, "bob", title="Bob overdue", due_at=past)["id"]
    create_task(client, "admin", title="Admin overdue", due_at=past)
    assert overdue_ids(client, "bob", "2026-02-01T00:00:00Z") == [bob_task]


def test_spec_1_member_export_contains_only_visible_tasks(client, mixed):
    """SPEC.md section 1: the CSV export obeys the visibility rule."""
    assert export_ids(client, "bob") == mixed["bob"]
    assert export_ids(client, "admin") == mixed["all"]


def test_spec_1_member_cannot_read_work_log_of_unrelated_task(client):
    """SPEC.md section 1: work logs obey the visibility rule; unreadable is a uniform 404."""
    task = create_task(client, "alice", title="Alice's logged task")
    logged = client.post(f"/tasks/{task['id']}/work", json={"minutes": 30}, headers=auth("alice"))
    assert logged.status_code == 200, logged.text
    response = client.get(f"/tasks/{task['id']}/work", headers=auth("bob"))
    assert response.status_code == 404
    assert response.json() == NOT_FOUND


def test_spec_1_member_cannot_log_work_on_unrelated_task(client):
    """SPEC.md sections 1 and 3: work needs task visibility; unreadable is a uniform 404 with no effect."""
    task = create_task(client, "alice", title="Alice's task")
    before = stored_state(client, task["id"])
    response = client.post(f"/tasks/{task['id']}/work", json={"minutes": 30}, headers=auth("bob"))
    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert stored_state(client, task["id"]) == before


def test_spec_1_member_cannot_read_history_of_unrelated_task(client):
    """SPEC.md sections 1 and 6.1: history obeys the visibility rule; unreadable is a uniform 404."""
    task = create_task(client, "alice", title="Alice's task with history")
    response = client.get(f"/tasks/{task['id']}/history", headers=auth("bob"))
    assert response.status_code == 404
    assert response.json() == NOT_FOUND


@pytest.mark.parametrize("attempt", ["create", "patch_title", "patch_status", "log_work"])
def test_spec_1_observers_never_write(client, attempt):
    """SPEC.md sections 1, 3, 5 and 6.2: an observer's write is refused with 403 and changes nothing."""
    task = create_task(client, "alice", title="Observed task")
    before = stored_state(client, task["id"])
    observer = auth("observer")
    if attempt == "create":
        response = client.post("/tasks", json={"title": "Observer's task"}, headers=observer)
    elif attempt == "patch_title":
        response = client.patch(f"/tasks/{task['id']}", json={"title": "Observer's edit"}, headers=observer)
    elif attempt == "patch_status":
        response = client.patch(f"/tasks/{task['id']}", json={"status": "in_progress"}, headers=observer)
    else:
        response = client.post(f"/tasks/{task['id']}/work", json={"minutes": 30}, headers=observer)
    assert response.status_code == 403, response.text
    assert stored_state(client, task["id"]) == before
