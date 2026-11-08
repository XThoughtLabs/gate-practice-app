"""GET /tasks/{id}/history (SPEC.md section 6.1): one event per creation and per actual transition."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta
import itertools
import sqlite3
import threading

import pytest
from fastapi.testclient import TestClient

from workflow.api import create_app
from workflow.store import USERS


BOB = {"Authorization": "Bearer demo-bob"}
NOT_FOUND = {"detail": "task not found"}


def event(sequence, actor_id, from_status, to_status, changed_at, origin="operation"):
    return {"sequence": sequence, "actor_id": actor_id, "from_status": from_status,
            "to_status": to_status, "changed_at": changed_at, "origin": origin}


def history(client, task_id, headers):
    response = client.get(f"/tasks/{task_id}/history", headers=headers)
    assert response.status_code == 200, response.text
    assert list(response.json()) == ["items"]
    return response.json()["items"]


def create(client, headers, **fields):
    response = client.post("/tasks", json={"title": "Synthetic task", **fields}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def patch(client, task_id, body, headers):
    return client.patch(f"/tasks/{task_id}", json=body, headers=headers)


def set_status(client, task_id, status, headers):
    response = patch(client, task_id, {"status": status}, headers)
    assert response.status_code == 200, response.text
    return response.json()


def stored(client, task_id, admin):
    response = client.get(f"/tasks/{task_id}", headers=admin)
    assert response.status_code == 200, response.text
    return response.json()


def assert_utc(value):
    assert datetime.fromisoformat(value).utcoffset() == timedelta(0), value


def db_path(client):
    return client.app.state.service.store.path


def execute(path, *statements):
    with closing(sqlite3.connect(path)) as conn:
        for statement in statements:
            conn.execute(statement)
        conn.commit()


# --- events that are written ----------------------------------------------------------


@pytest.mark.parametrize(("token", "creator_id"), [("demo-admin", 1), ("demo-alice", 2), ("demo-bob", 3)])
def test_new_task_has_one_creation_event(client, admin, token, creator_id):
    task = create(client, {"Authorization": f"Bearer {token}"})
    events = history(client, task["id"], admin)
    assert events == [event(1, creator_id, None, "todo", task["created_at"])]
    assert_utc(events[0]["changed_at"])


def test_each_actual_transition_appends_one_event(client, alice, admin, task):
    # The fixture task is Alice's and assigned to her; Bob takes it over first.
    assert patch(client, task["id"], {"assignee_id": 3}, alice).status_code == 200
    moved = set_status(client, task["id"], "in_progress", alice)
    finished = set_status(client, task["id"], "done", BOB)
    reopened = set_status(client, task["id"], "in_progress", admin)
    events = history(client, task["id"], admin)
    assert events == [
        event(1, 2, None, "todo", task["created_at"]),
        event(2, 2, "todo", "in_progress", moved["updated_at"]),
        event(3, 3, "in_progress", "done", finished["updated_at"]),
        event(4, 1, "done", "in_progress", reopened["updated_at"]),
    ]
    for item in events:
        assert_utc(item["changed_at"])


def test_status_change_with_other_fields_appends_one_event(client, alice, admin, task):
    body = {"status": "in_progress", "title": "Renamed", "priority": 1, "assignee_id": 3}
    response = patch(client, task["id"], body, alice)
    assert response.status_code == 200, response.text
    assert history(client, task["id"], admin)[1:] == [
        event(2, 2, "todo", "in_progress", response.json()["updated_at"])]


def test_sequence_is_counted_per_task(client, alice, admin):
    first, second = create(client, alice)["id"], create(client, alice)["id"]
    set_status(client, first, "in_progress", alice)
    set_status(client, second, "in_progress", alice)
    set_status(client, second, "done", alice)
    third = create(client, alice)["id"]
    assert [e["sequence"] for e in history(client, first, admin)] == [1, 2]
    assert [e["sequence"] for e in history(client, second, admin)] == [1, 2, 3]
    assert [e["sequence"] for e in history(client, third, admin)] == [1]


# --- requests that write no event -----------------------------------------------------


@pytest.mark.parametrize("status", ["todo", "in_progress", "done"])
def test_no_event_for_unchanged_status(client, alice, admin, task, status):
    for step in ("in_progress", "done")[:("todo", "in_progress", "done").index(status)]:
        set_status(client, task["id"], step, alice)
    before = history(client, task["id"], admin)
    for body in ({"status": status}, {"status": status, "title": "Renamed, same status"}):
        assert patch(client, task["id"], body, alice).status_code == 200
    assert history(client, task["id"], admin) == before
    assert stored(client, task["id"], admin)["title"] == "Renamed, same status"


def test_no_event_for_non_status_edits(client, alice, admin, task):
    before = history(client, task["id"], admin)
    for body in [{"title": "Edited"}, {"description": "New description"}, {"priority": 5},
                 {"assignee_id": 3}, {"due_at": "2026-09-01T12:00:00Z"},
                 {"assignee_id": None, "due_at": None}]:
        assert patch(client, task["id"], body, alice).status_code == 200, body
    assert client.post(f"/tasks/{task['id']}/work", json={"minutes": 30}, headers=alice).status_code == 200
    assert history(client, task["id"], admin) == before


REJECTED = {
    # name: (status the task is moved to first, actor, body, expected status code)
    "skipped-transition": ("todo", "alice", {"status": "done"}, 409),
    "backwards-transition": ("in_progress", "alice", {"status": "todo"}, 409),
    "member-reopen": ("done", "alice", {"status": "in_progress"}, 403),
    "observer": ("todo", "observer", {"status": "in_progress"}, 403),
    "unknown-status": ("todo", "alice", {"status": "blocked"}, 422),
    "null-status": ("todo", "alice", {"status": None}, 422),
    "invalid-companion-field": ("todo", "alice", {"status": "in_progress", "priority": 9}, 422),
    "unknown-companion-field": ("todo", "alice", {"status": "in_progress", "history": []}, 422),
    "observer-assignee": ("todo", "alice", {"status": "in_progress", "assignee_id": 4}, 422),
}


@pytest.mark.parametrize("case", sorted(REJECTED))
def test_no_event_for_rejected_requests(client, alice, admin, observer, task, case):
    start, actor, body, expected = REJECTED[case]
    for step in ("in_progress", "done")[:("todo", "in_progress", "done").index(start)]:
        set_status(client, task["id"], step, alice)
    before = stored(client, task["id"], admin), history(client, task["id"], admin)
    response = patch(client, task["id"], body, {"alice": alice, "observer": observer}[actor])
    assert response.status_code == expected, response.text
    assert (stored(client, task["id"], admin), history(client, task["id"], admin)) == before


def test_no_event_for_an_idempotent_creation_retry(client, alice, admin):
    headers = {**alice, "Idempotency-Key": "history-retry"}
    first = client.post("/tasks", json={"title": "Retried"}, headers=headers)
    second = client.post("/tasks", json={"title": "Retried"}, headers=headers)
    conflict = client.post("/tasks", json={"title": "Other body"}, headers=headers)
    assert (first.status_code, second.status_code, conflict.status_code) == (201, 201, 409)
    assert second.json() == first.json()
    assert client.get("/tasks", headers=admin).json()["total"] == 1
    assert history(client, first.json()["id"], admin) == [
        event(1, 2, None, "todo", first.json()["created_at"])]


def test_task_missing_at_write_time_is_404(client, alice, task, monkeypatch):
    # The first read finds the task, the write transaction does not: uniform 404, no write.
    store = client.app.state.service.store
    monkeypatch.setattr(store, "task", lambda task_id: dict(task, id=task_id))
    response = patch(client, 9999, {"status": "in_progress"}, alice)
    monkeypatch.undo()
    assert (response.status_code, response.json()) == (404, NOT_FOUND)
    assert rows(store.path, "SELECT COUNT(*) FROM status_history") == [(1,)]


def test_store_refuses_a_status_change_without_actor(client, admin, task):
    store = client.app.state.service.store
    with pytest.raises(sqlite3.IntegrityError):
        store.update(task["id"], {"status": "in_progress"}, "2026-01-01T00:00:00.000000+00:00")
    assert stored(client, task["id"], admin) == task
    assert len(history(client, task["id"], admin)) == 1


# --- atomicity ------------------------------------------------------------------------


PLANT_FAILURE = ("CREATE TRIGGER planted_failure BEFORE INSERT ON status_history "
                 "BEGIN SELECT RAISE(ABORT, 'planted failure'); END")


def test_task_update_and_its_event_commit_atomically(client, alice, admin, task):
    # The event insert fails after the task's UPDATE ran: the update must be rolled back.
    before = stored(client, task["id"], admin), history(client, task["id"], admin)
    execute(db_path(client), PLANT_FAILURE)
    with pytest.raises(sqlite3.IntegrityError, match="planted failure"):
        patch(client, task["id"], {"status": "in_progress", "title": "Half done?"}, alice)
    assert (stored(client, task["id"], admin), history(client, task["id"], admin)) == before
    execute(db_path(client), "DROP TRIGGER planted_failure")
    moved = set_status(client, task["id"], "in_progress", alice)
    assert history(client, task["id"], admin)[1:] == [
        event(2, 2, "todo", "in_progress", moved["updated_at"])]


def test_task_and_its_creation_event_commit_atomically(client, alice, admin):
    execute(db_path(client), PLANT_FAILURE)
    with pytest.raises(sqlite3.IntegrityError, match="planted failure"):
        client.post("/tasks", json={"title": "Without history?"}, headers=alice)
    assert client.get("/tasks", headers=admin).json()["total"] == 0


def test_simultaneous_identical_transitions_append_one_event(client, alice, admin, task, monkeypatch):
    # Both requests read the task as "todo" before either writes. Only the first actual
    # transition may be recorded; the second finds the status already changed (a no-op).
    store = client.app.state.service.store
    read = store.task
    both_read = threading.Barrier(2, timeout=10)
    calls = itertools.count()

    def read_then_wait(task_id):
        row = read(task_id)
        if next(calls) < 2:
            both_read.wait()
        return row

    monkeypatch.setattr(store, "task", read_then_wait)
    path = f"/tasks/{task['id']}"
    with ThreadPoolExecutor(2) as pool:
        responses = list(pool.map(
            lambda headers: client.patch(path, json={"status": "in_progress"}, headers=headers),
            [alice, admin]))
    assert [response.status_code for response in responses] == [200, 200]
    events = history(client, task["id"], admin)
    assert [(e["sequence"], e["from_status"], e["to_status"]) for e in events] == [
        (1, None, "todo"), (2, "todo", "in_progress")]
    assert events[1]["actor_id"] in (1, 2)


def test_transition_is_judged_against_the_stored_status(client, alice, admin, task, monkeypatch):
    # Alice's request first reads the task as "in_progress"; another request has finished
    # it before her write. Her "in_progress" is then a member's reopen: refused, no event.
    store = client.app.state.service.store
    set_status(client, task["id"], "in_progress", alice)
    earlier_read = store.task(task["id"])
    set_status(client, task["id"], "done", alice)
    before = stored(client, task["id"], admin), history(client, task["id"], admin)
    monkeypatch.setattr(store, "task", lambda task_id: dict(earlier_read))
    response = patch(client, task["id"], {"status": "in_progress"}, alice)
    monkeypatch.undo()
    assert response.status_code == 403, response.text
    assert (stored(client, task["id"], admin), history(client, task["id"], admin)) == before


# --- reading --------------------------------------------------------------------------


def test_history_uses_the_task_read_permissions(client, alice, admin, observer):
    task = create(client, admin, assignee_id=2)
    set_status(client, task["id"], "in_progress", alice)
    expected = history(client, task["id"], admin)
    assert len(expected) == 2
    for readers in (admin, observer, alice):
        assert history(client, task["id"], readers) == expected
    own = create(client, BOB)
    assert len(history(client, own["id"], BOB)) == 1
    # Bob neither created nor is assigned the first task; Alice loses it when reassigned.
    hidden = client.get(f"/tasks/{task['id']}/history", headers=BOB)
    assert (hidden.status_code, hidden.json()) == (404, NOT_FOUND)
    assert patch(client, task["id"], {"assignee_id": 3}, admin).status_code == 200
    former = client.get(f"/tasks/{task['id']}/history", headers=alice)
    assert (former.status_code, former.json()) == (404, NOT_FOUND)
    assert len(history(client, task["id"], BOB)) == 2


@pytest.mark.parametrize("token", ["demo-admin", "demo-alice", "demo-observer"])
def test_history_of_a_missing_task_is_404(client, token):
    response = client.get("/tasks/9999/history", headers={"Authorization": f"Bearer {token}"})
    assert (response.status_code, response.json()) == (404, NOT_FOUND)


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer unknown"}])
def test_history_requires_authentication(client, task, headers):
    assert client.get(f"/tasks/{task['id']}/history", headers=headers).status_code == 401


# --- permanence -----------------------------------------------------------------------


def test_history_survives_restart(tmp_path, alice, admin):
    path = tmp_path / "restart.sqlite3"
    with TestClient(create_app(path)) as client:
        task = create(client, alice)
        set_status(client, task["id"], "in_progress", alice)
        set_status(client, task["id"], "done", alice)
        before = history(client, task["id"], admin)
    with TestClient(create_app(path)) as client:
        assert history(client, task["id"], admin) == before
    assert len(before) == 3


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_history_is_not_editable_through_the_api(client, alice, admin, task, method):
    set_status(client, task["id"], "in_progress", alice)
    before = history(client, task["id"], admin)
    forged = {"items": [event(1, 3, None, "done", "2026-01-01T00:00:00+00:00")]}
    for headers in (admin, alice):
        response = client.request(method, f"/tasks/{task['id']}/history",
                                  json=None if method == "DELETE" else forged, headers=headers)
        assert response.status_code == 405, response.text
    assert history(client, task["id"], admin) == before


def test_task_patch_cannot_write_history(client, admin, task):
    before = history(client, task["id"], admin)
    response = patch(client, task["id"], {"history": [], "title": "Renamed"}, admin)
    assert response.status_code == 422
    assert history(client, task["id"], admin) == before


def test_earlier_events_are_not_rewritten_by_later_changes(client, alice, admin, task):
    set_status(client, task["id"], "in_progress", alice)
    earlier = history(client, task["id"], admin)
    for body in ({"title": "Renamed"}, {"assignee_id": 3}, {"status": "done"}, {"priority": 1}):
        assert patch(client, task["id"], body, alice).status_code == 200
    set_status(client, task["id"], "in_progress", admin)
    later = history(client, task["id"], admin)
    assert later[:len(earlier)] == earlier
    assert len(later) == len(earlier) + 2


@pytest.mark.parametrize("statement", [
    "UPDATE status_history SET to_status = 'done'",
    "UPDATE status_history SET actor_id = 3 WHERE sequence = 1",
    "DELETE FROM status_history",
])
def test_stored_events_cannot_be_rewritten(client, admin, task, statement):
    before = history(client, task["id"], admin)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        execute(db_path(client), statement)
    assert history(client, task["id"], admin) == before


# --- upgrade of a pre-upgrade database ------------------------------------------------


# The schema of workflow/store.py before status history (baseline 821330ff), verbatim.
PRE_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'member', 'observer')),
    token TEXT NOT NULL UNIQUE
) STRICT;
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 120),
    description TEXT NOT NULL DEFAULT '',
    creator_id INTEGER NOT NULL REFERENCES users(id),
    assignee_id INTEGER REFERENCES users(id),
    status TEXT NOT NULL CHECK(status IN ('todo', 'in_progress', 'done')),
    priority INTEGER NOT NULL CHECK(priority BETWEEN 1 AND 5),
    due_at TEXT,
    work_minutes INTEGER NOT NULL DEFAULT 0 CHECK(work_minutes >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
) STRICT;
CREATE TABLE IF NOT EXISTS work_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    actor_id INTEGER NOT NULL REFERENCES users(id),
    minutes INTEGER NOT NULL CHECK(minutes BETWEEN 1 AND 480),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS tasks_creator ON tasks(creator_id, id);
CREATE INDEX IF NOT EXISTS tasks_assignee ON tasks(assignee_id, id);
"""

TASK_COLUMNS = ("id", "title", "description", "creator_id", "assignee_id", "status", "priority",
                "due_at", "work_minutes", "created_at", "updated_at")
# One task in each status, each created by a different user and assigned to another.
PRE_UPGRADE_TASKS = [
    (1, "Waiting", "", 1, 2, "todo", 3, None, 25,
     "2026-01-01T09:00:00.000000+00:00", "2026-01-02T09:00:00.000000+00:00"),
    (2, "Started", "Half way", 2, 3, "in_progress", 2, "2026-05-01T08:00:00.000000+00:00", 60,
     "2026-01-03T09:00:00.000000+00:00", "2026-01-04T09:00:00.000000+00:00"),
    (3, "Finished — 東京", 'Kept, "quoted"', 3, 2, "done", 5, None, 0,
     "2026-01-05T09:00:00.000000+00:00", "2026-01-06T09:00:00.000000+00:00"),
]
PRE_UPGRADE_WORK = [
    (1, 1, 2, 25, "2026-01-02T09:00:00.000000+00:00"),
    (2, 2, 3, 40, "2026-01-04T08:00:00.000000+00:00"),
    (3, 2, 2, 20, "2026-01-04T09:00:00.000000+00:00"),
]


def rows(path, query):
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute(query).fetchall()


def user_version(path):
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute("PRAGMA user_version").fetchone()[0]


@pytest.fixture
def pre_upgrade(tmp_path):
    """A database file as the version before status history left it."""
    path = tmp_path / "pre-upgrade.sqlite3"
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript(PRE_HISTORY_SCHEMA)
        conn.executemany("INSERT INTO users(id,name,role,token) VALUES(?,?,?,?)", USERS)
        conn.executemany("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?)", PRE_UPGRADE_TASKS)
        conn.executemany("INSERT INTO work_logs VALUES(?,?,?,?,?)", PRE_UPGRADE_WORK)
        conn.commit()
    assert user_version(path) == 0
    return path


def test_upgrade_gives_each_existing_task_one_migration_event(pre_upgrade, admin):
    with TestClient(create_app(pre_upgrade)) as client:
        for row in PRE_UPGRADE_TASKS:
            task = dict(zip(TASK_COLUMNS, row))
            events = history(client, task["id"], admin)
            assert len(events) == 1, events
            changed_at = events[0].pop("changed_at")
            assert events[0] == {"sequence": 1, "actor_id": task["creator_id"], "from_status": None,
                                 "to_status": task["status"], "origin": "migration"}
            assert_utc(changed_at)
    assert user_version(pre_upgrade) == 1


def test_upgrade_keeps_tasks_and_work_logs(pre_upgrade, admin):
    with TestClient(create_app(pre_upgrade)) as client:
        for row in PRE_UPGRADE_TASKS:
            assert stored(client, row[0], admin) == dict(zip(TASK_COLUMNS, row))
        work = client.get("/tasks/2/work", headers=admin).json()["items"]
        assert [(w["actor_id"], w["minutes"]) for w in work] == [(3, 40), (2, 20)]
    assert rows(pre_upgrade, "SELECT * FROM tasks ORDER BY id") == PRE_UPGRADE_TASKS
    assert rows(pre_upgrade, "SELECT * FROM work_logs ORDER BY id") == PRE_UPGRADE_WORK


def test_migration_is_not_repeated_on_restart(pre_upgrade, alice, admin):
    with TestClient(create_app(pre_upgrade)) as client:
        first = {row[0]: history(client, row[0], admin) for row in PRE_UPGRADE_TASKS}
        created = create(client, alice)
    for _ in range(2):
        with TestClient(create_app(pre_upgrade)) as client:
            assert {row[0]: history(client, row[0], admin) for row in PRE_UPGRADE_TASKS} == first
            assert history(client, created["id"], admin) == [
                event(1, 2, None, "todo", created["created_at"])]


def test_failed_migration_writes_nothing(pre_upgrade, admin):
    # A planted failure: a task whose creator does not exist cannot get its migration event.
    execute(pre_upgrade, "INSERT INTO tasks VALUES(4, 'Orphan', '', 99, NULL, 'todo', 3, NULL, 0, "
                         "'2026-01-07T09:00:00.000000+00:00', '2026-01-07T09:00:00.000000+00:00')")
    with pytest.raises(sqlite3.IntegrityError):
        create_app(pre_upgrade)
    assert user_version(pre_upgrade) == 0
    assert rows(pre_upgrade, "SELECT COUNT(*) FROM status_history") == [(0,)]
    execute(pre_upgrade, "DELETE FROM tasks WHERE id = 4")
    with TestClient(create_app(pre_upgrade)) as client:
        assert [len(history(client, row[0], admin)) for row in PRE_UPGRADE_TASKS] == [1, 1, 1]
    assert user_version(pre_upgrade) == 1


def test_after_upgrade_events_use_origin_operation(pre_upgrade, alice, admin):
    with TestClient(create_app(pre_upgrade)) as client:
        migrated = history(client, 1, admin)
        moved = set_status(client, 1, "in_progress", alice)
        assert history(client, 1, admin) == migrated + [
            event(2, 2, "todo", "in_progress", moved["updated_at"])]
        created = create(client, BOB)
        assert history(client, created["id"], admin) == [
            event(1, 3, None, "todo", created["created_at"])]
