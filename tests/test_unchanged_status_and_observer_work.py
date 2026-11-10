"""Issue #42: an unchanged status alone writes nothing; an observer's work on a missing task is 404.

SPEC.md section 2: an unchanged status is a no-op. A PATCH whose body holds only the task's
stored status answers 200 with the task exactly as stored and writes nothing: no field,
updated_at included, and no status-history event. The checks before it stay: a missing or
unreadable task is the uniform 404, a readable task the actor may not patch 403. The
unchanged status sent with another field still updates that field and updated_at.

SPEC.md sections 1, 3 and 5: POST /tasks/{id}/work for a missing task is the uniform 404 for
every role, an observer included, whatever the id in the path; an observer's entry for an
existing task stays 403. Neither refusal writes anything.
"""

from contextlib import closing
import sqlite3

import pytest

import workflow.service


HEADERS = {name: {"Authorization": f"Bearer demo-{name}"} for name in ("admin", "alice", "bob", "observer")}
IDS = {"admin": 1, "alice": 2, "bob": 3}
NOT_FOUND = {"detail": "task not found"}
FORBIDDEN = {"detail": "write forbidden"}
STATUSES = ("todo", "in_progress", "done")

# Later than every timestamp the setup writes, so a request that rewrites updated_at shows it.
LATER = "2099-01-01T00:00:00.000000+00:00"

SNAPSHOT = {
    "tasks": "SELECT * FROM tasks ORDER BY id",
    "work_logs": "SELECT * FROM work_logs ORDER BY id",
    "status_history": "SELECT * FROM status_history ORDER BY id",
}

# Ids no task has: the issue's four, inside and outside SQLite's signed 64-bit range, the
# first value below that range, and an unused id inside it.
MISSING_IDS = {
    "max": 2**63 - 1,
    "zero": 0,
    "minus-one": -1,
    "above-max": 2**63,
    "below-min": -2**63 - 1,
    "unused": 9999,
}

# Actors who may patch the tasks of the tasks fixture: the admin, the creator and the assignee.
PATCHERS = ["admin", "alice", "bob"]


def patch(client, task_id, body, actor):
    return client.patch(f"/tasks/{task_id}", json=body, headers=HEADERS[actor])


def log_work(client, task_id, actor, minutes=30):
    return client.post(f"/tasks/{task_id}/work", json={"minutes": minutes}, headers=HEADERS[actor])


def make_task(client, status, creator="alice", assignee="bob"):
    """creator's task for assignee, with one work entry by the creator, moved to status."""
    created = client.post("/tasks", json={"title": f"Task {status}", "assignee_id": IDS[assignee]},
                          headers=HEADERS[creator])
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    assert log_work(client, task_id, creator, 15).status_code == 200
    for step in STATUSES[1:STATUSES.index(status) + 1]:
        moved = patch(client, task_id, {"status": step}, creator)
        assert moved.status_code == 200, moved.text
    return task_id


@pytest.fixture
def tasks(client):
    """{status: id} of Alice's tasks for Bob, one in each status."""
    return {status: make_task(client, status) for status in STATUSES}


def stored(client):
    """Every row of the tasks, work entries and status-history events in the file."""
    with closing(sqlite3.connect(client.app.state.service.store.path)) as conn:
        return {table: conn.execute(query).fetchall() for table, query in SNAPSHOT.items()}


def read(client, task_id):
    response = client.get(f"/tasks/{task_id}", headers=HEADERS["admin"])
    assert response.status_code == 200, response.text
    return response.json()


def move_clock(monkeypatch):
    monkeypatch.setattr(workflow.service, "timestamp", lambda: LATER)


# --- an unchanged status alone ----------------------------------------------------------


@pytest.mark.parametrize("actor", PATCHERS)
@pytest.mark.parametrize("status", STATUSES)
def test_unchanged_status_alone_writes_nothing(client, tasks, monkeypatch, status, actor):
    task_id = tasks[status]
    before, task = stored(client), read(client, task_id)
    assert task["status"] == status and task["updated_at"] != LATER
    move_clock(monkeypatch)
    response = patch(client, task_id, {"status": status}, actor)
    assert (response.status_code, response.json()) == (200, task)
    assert stored(client) == before
    assert read(client, task_id) == task


@pytest.mark.parametrize("actor", PATCHERS)
@pytest.mark.parametrize("status", STATUSES)
def test_unchanged_status_with_another_field_updates_it_and_updated_at(client, tasks, monkeypatch, status, actor):
    task_id = tasks[status]
    before, task = stored(client), read(client, task_id)
    move_clock(monkeypatch)
    response = patch(client, task_id, {"status": status, "title": "Renamed, same status"}, actor)
    assert response.status_code == 200, response.text
    assert response.json() == read(client, task_id) == {
        **task, "title": "Renamed, same status", "updated_at": LATER}
    after = stored(client)
    # That task's row alone changed: no work entry, no status-history event, no other task.
    assert (after["work_logs"], after["status_history"]) == (before["work_logs"], before["status_history"])
    assert [row for row in after["tasks"] if row[0] != task_id] == [
        row for row in before["tasks"] if row[0] != task_id]


@pytest.mark.parametrize("status", STATUSES)
@pytest.mark.parametrize(("actor", "expected"), [("bob", (404, NOT_FOUND)), ("observer", (403, FORBIDDEN))],
                         ids=["unreadable", "readable-not-patchable"])
def test_unchanged_status_alone_keeps_the_checks_before_it(client, monkeypatch, status, actor, expected):
    # Alice's own task: Bob can neither read nor patch it, the observer reads it only.
    task_id = make_task(client, status, "alice", "alice")
    before = stored(client)
    move_clock(monkeypatch)
    response = patch(client, task_id, {"status": status}, actor)
    assert (response.status_code, response.json()) == expected
    assert stored(client) == before


@pytest.mark.parametrize("status", STATUSES)
@pytest.mark.parametrize("actor", sorted(HEADERS))
def test_unchanged_status_alone_for_a_missing_task_is_404(client, tasks, monkeypatch, actor, status):
    before = stored(client)
    move_clock(monkeypatch)
    response = patch(client, max(tasks.values()) + 1, {"status": status}, actor)
    assert (response.status_code, response.json()) == (404, NOT_FOUND)
    assert stored(client) == before


@pytest.mark.parametrize("status", STATUSES)
def test_unchanged_status_alone_is_judged_against_the_stored_assignment(client, tasks, monkeypatch, status):
    # Bob's request first reads the task while he is its assignee; Alice takes it back before
    # his write. The write transaction's stored row decides: Bob can no longer read the task,
    # so his unchanged status is the uniform 404, not 200 with the task.
    store = client.app.state.service.store
    task_id = tasks[status]
    earlier_read = store.task(task_id)
    assert patch(client, task_id, {"assignee_id": IDS["alice"]}, "alice").status_code == 200
    before = stored(client)
    move_clock(monkeypatch)
    monkeypatch.setattr(store, "task", lambda task_id: dict(earlier_read))
    response = patch(client, task_id, {"status": status}, "bob")
    monkeypatch.undo()
    assert (response.status_code, response.json()) == (404, NOT_FOUND)
    assert stored(client) == before


def test_status_reached_by_another_request_before_the_write_is_a_no_op(client, tasks, monkeypatch):
    # Alice's request first reads the task as todo; Bob starts it before her write. Her
    # in_progress is then the stored status, judged in the write transaction: nothing written.
    store = client.app.state.service.store
    task_id = make_task(client, "todo")
    earlier_read = store.task(task_id)
    assert patch(client, task_id, {"status": "in_progress"}, "bob").status_code == 200
    before, task = stored(client), read(client, task_id)
    move_clock(monkeypatch)
    monkeypatch.setattr(store, "task", lambda task_id: dict(earlier_read))
    response = patch(client, task_id, {"status": "in_progress"}, "alice")
    monkeypatch.undo()
    assert (response.status_code, response.json()) == (200, task)
    assert stored(client) == before


def test_status_left_by_another_request_before_the_write_is_a_transition(client, tasks, monkeypatch):
    # The admin's request first reads the task in progress, as its body says; Alice finishes
    # it before the admin's write. The stored status decides: the admin's in_progress is a
    # reopen, written with its event, not a no-op.
    store = client.app.state.service.store
    task_id = make_task(client, "in_progress")
    earlier_read = store.task(task_id)
    assert patch(client, task_id, {"status": "done"}, "alice").status_code == 200
    events = len(client.get(f"/tasks/{task_id}/history", headers=HEADERS["admin"]).json()["items"])
    move_clock(monkeypatch)
    monkeypatch.setattr(store, "task", lambda task_id: dict(earlier_read))
    response = patch(client, task_id, {"status": "in_progress"}, "admin")
    monkeypatch.undo()
    assert response.status_code == 200, response.text
    assert (response.json()["status"], response.json()["updated_at"]) == ("in_progress", LATER)
    history = client.get(f"/tasks/{task_id}/history", headers=HEADERS["admin"]).json()["items"]
    assert [(e["actor_id"], e["from_status"], e["to_status"], e["changed_at"]) for e in history[events:]] == [
        (IDS["admin"], "done", "in_progress", LATER)]


def test_store_update_with_the_stored_status_alone_writes_nothing(client, tasks):
    store = client.app.state.service.store
    for status, task_id in tasks.items():
        before, task = stored(client), store.task(task_id)
        assert store.update(task_id, {"status": status}, LATER, IDS["alice"]) == task
        assert stored(client) == before
        updated = store.update(task_id, {"status": status, "priority": 1}, LATER, IDS["alice"])
        assert updated == {**task, "priority": 1, "updated_at": LATER}


# --- work entries: a missing task is 404 for every role ---------------------------------


@pytest.mark.parametrize("task_id", list(MISSING_IDS.values()), ids=list(MISSING_IDS))
@pytest.mark.parametrize("actor", ["observer", "admin", "alice", "bob"])
def test_work_on_a_missing_task_is_404_for_every_role(client, tasks, actor, task_id):
    before = stored(client)
    response = log_work(client, task_id, actor)
    assert (response.status_code, response.json()) == (404, NOT_FOUND)
    assert stored(client) == before


@pytest.mark.parametrize("status", STATUSES)
def test_observer_work_on_an_existing_task_is_still_403(client, tasks, status):
    task_id = tasks[status]
    assert read(client, task_id) == client.get(f"/tasks/{task_id}", headers=HEADERS["observer"]).json()
    before = stored(client)
    response = log_work(client, task_id, "observer")
    assert (response.status_code, response.json()) == (403, FORBIDDEN)
    assert stored(client) == before
