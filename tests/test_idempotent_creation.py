"""POST /tasks with Idempotency-Key (SPEC.md section 4): one task per actor and key.

Each actor/key is kept in the SQLite file with a digest of the normalized body and the
task it created, unique per actor and key, and written in the same transaction as the
task and its creation event. So a repeat with the same body returns the same task ID and
201, a different body returns 409 and creates nothing, and the same key string of another
actor is a separate key, also for simultaneous requests and after a restart. The table is
added to an existing file by a backward-compatible initialization that keeps its data;
see docs/idempotency-keys.md.
"""

from contextlib import closing
import contextlib
import sqlite3
import threading

import pytest
from fastapi.testclient import TestClient

from workflow.api import create_app
from workflow.store import USERS


HEADERS = {name: {"Authorization": f"Bearer demo-{name}"} for name in ("admin", "alice", "bob", "observer")}
IDS = {"admin": 1, "alice": 2, "bob": 3}
CONFLICT = {"detail": "idempotency key reused with a different body"}


def post(client, actor, key, body):
    return client.post("/tasks", json=body, headers={**HEADERS[actor], "Idempotency-Key": key})


def created(response):
    assert response.status_code == 201, response.text
    return response.json()


def tasks(client):
    """Every stored task, as the administrator lists them."""
    response = client.get("/tasks", params={"limit": 100}, headers=HEADERS["admin"])
    assert response.status_code == 200, response.text
    assert response.json()["total"] == len(response.json()["items"])
    return response.json()["items"]


def history(client, task_id):
    response = client.get(f"/tasks/{task_id}/history", headers=HEADERS["admin"])
    assert response.status_code == 200, response.text
    return response.json()["items"]


def rows(path, query):
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute(query).fetchall()


def execute(path, statement, params=()):
    with closing(sqlite3.connect(path)) as conn:
        conn.execute(statement, params)
        conn.commit()


def key_records(path):
    """(actor_id, key, task_id) of every key record in the file."""
    return rows(path, "SELECT actor_id, idempotency_key, task_id FROM idempotency_keys "
                      "ORDER BY actor_id, idempotency_key")


def user_version(path):
    return rows(path, "PRAGMA user_version")[0][0]


def run_together(count, action):
    """Run action(0) … action(count - 1) on separate threads released at the same moment."""
    start = threading.Barrier(count)
    results = [None] * count
    failures = []

    def worker(index):
        try:
            start.wait(timeout=30)
            results[index] = action(index)
        except Exception as error:  # reported by the assertion below
            failures.append(error)

    threads = [threading.Thread(target=worker, args=(index,), daemon=True) for index in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)
    assert not any(thread.is_alive() for thread in threads), "a request did not finish within 120 s"
    assert not failures, failures
    return results


def hold_at_the_store(client, monkeypatch, count):
    """Hold each request on its way into Store.create until `count` requests are there.

    Every request has then passed whatever the service checks before the store's write
    transaction, so a key looked up before that transaction and recorded after it lets
    each of them create a task every time, not only when the threads happen to
    interleave. A request that cannot get there with the others is let through after 5 s.
    """
    store = client.app.state.service.store
    create = store.create
    all_in = threading.Barrier(count, timeout=5)

    def wait_then_create(*args, **kwargs):
        with contextlib.suppress(threading.BrokenBarrierError):
            all_in.wait()
        return create(*args, **kwargs)

    monkeypatch.setattr(store, "create", wait_then_create)


# --- simultaneous requests ------------------------------------------------------------


def test_simultaneous_retries_create_one_task(tmp_path, monkeypatch):
    path = tmp_path / "retries.sqlite3"
    body = {"title": "Simultaneous retry", "priority": 2}
    with TestClient(create_app(path)) as client:
        hold_at_the_store(client, monkeypatch, 8)
        responses = run_together(8, lambda index: post(client, "alice", "retry-key", body))
        monkeypatch.undo()
        assert [response.status_code for response in responses] == [201] * 8
        assert len({response.json()["id"] for response in responses}) == 1
        task = responses[0].json()
        assert [item["id"] for item in tasks(client)] == [task["id"]]
        assert len(history(client, task["id"])) == 1
    assert key_records(path) == [(IDS["alice"], "retry-key", task["id"])]
    with TestClient(create_app(path)) as client:
        assert created(post(client, "alice", "retry-key", body))["id"] == task["id"]
        assert len(tasks(client)) == 1


def test_simultaneous_different_bodies_give_one_201_and_the_rest_409(tmp_path, monkeypatch):
    path = tmp_path / "conflicts.sqlite3"
    bodies = [{"title": f"Variant {index}"} for index in range(8)]
    with TestClient(create_app(path)) as client:
        hold_at_the_store(client, monkeypatch, 8)
        responses = run_together(8, lambda index: post(client, "alice", "contested-key", bodies[index]))
        monkeypatch.undo()
        assert sorted(response.status_code for response in responses) == [201] + [409] * 7
        winner = next(index for index, response in enumerate(responses) if response.status_code == 201)
        task = responses[winner].json()
        assert task["title"] == bodies[winner]["title"]
        assert all(response.json() == CONFLICT for response in responses if response.status_code == 409)
        assert [(item["id"], item["title"]) for item in tasks(client)] == [(task["id"], task["title"])]
        assert len(history(client, task["id"])) == 1
    with TestClient(create_app(path)) as client:
        assert created(post(client, "alice", "contested-key", bodies[winner]))["id"] == task["id"]
        refused = post(client, "alice", "contested-key", bodies[(winner + 1) % 8])
        assert (refused.status_code, refused.json()) == (409, CONFLICT)
        assert len(tasks(client)) == 1
    assert key_records(path) == [(IDS["alice"], "contested-key", task["id"])]


# --- restarts and actors --------------------------------------------------------------


def test_retry_after_a_restart_returns_the_same_task(tmp_path):
    path = tmp_path / "restart.sqlite3"
    body = {"title": "Order synthetic paper", "description": "Two boxes",
            "due_at": "2026-05-01T10:00:00+02:00"}
    with TestClient(create_app(path)) as client:
        first = created(post(client, "alice", "paper-order", body))
        moved = client.patch(f"/tasks/{first['id']}", json={"status": "in_progress"}, headers=HEADERS["alice"])
        assert moved.status_code == 200, moved.text
        events = history(client, first["id"])
    with TestClient(create_app(path)) as client:
        # The same task, as it is stored now; the retry writes no event.
        assert created(post(client, "alice", "paper-order", body)) == moved.json()
        # The same normalized body: other key order, the same due instant written in UTC.
        same = {"due_at": "2026-05-01T08:00:00Z", "description": "Two boxes", "title": "Order synthetic paper"}
        assert created(post(client, "alice", "paper-order", same))["id"] == first["id"]
        refused = post(client, "alice", "paper-order", {**body, "title": "Order other paper"})
        assert (refused.status_code, refused.json()) == (409, CONFLICT)
        assert [item["id"] for item in tasks(client)] == [first["id"]]
        assert history(client, first["id"]) == events
    with TestClient(create_app(path)) as client:
        assert created(post(client, "alice", "paper-order", body))["id"] == first["id"]
        assert len(tasks(client)) == 1


def test_another_actors_same_key_creates_its_own_task(tmp_path, monkeypatch):
    path = tmp_path / "actors.sqlite3"
    body = {"title": "Shared key string"}
    actors = ["alice", "bob"] * 4
    with TestClient(create_app(path)) as client:
        hold_at_the_store(client, monkeypatch, len(actors))
        responses = run_together(len(actors), lambda index: post(client, actors[index], "shared-key", body))
        monkeypatch.undo()
        assert [response.status_code for response in responses] == [201] * len(actors)
        ids = {name: {response.json()["id"] for response, actor in zip(responses, actors) if actor == name}
               for name in ("alice", "bob")}
        assert [len(found) for found in ids.values()] == [1, 1], ids
        alice_id, bob_id = min(ids["alice"]), min(ids["bob"])
        assert alice_id != bob_id
        assert {item["id"]: item["creator_id"] for item in tasks(client)} == {
            alice_id: IDS["alice"], bob_id: IDS["bob"]}
    with TestClient(create_app(path)) as client:
        assert created(post(client, "alice", "shared-key", body))["id"] == alice_id
        assert created(post(client, "bob", "shared-key", body))["id"] == bob_id
        refused = post(client, "bob", "shared-key", {"title": "Another request"})
        assert (refused.status_code, refused.json()) == (409, CONFLICT)
        admin = created(post(client, "admin", "shared-key", {"title": "Another request"}))
        assert admin["id"] not in (alice_id, bob_id)
        assert admin["creator_id"] == IDS["admin"]
        assert len(tasks(client)) == 3
    assert key_records(path) == [(IDS["admin"], "shared-key", admin["id"]),
                                 (IDS["alice"], "shared-key", alice_id),
                                 (IDS["bob"], "shared-key", bob_id)]


# --- what is recorded, and when -------------------------------------------------------


PLANTED_FAILURES = {
    table: f"CREATE TRIGGER planted_failure BEFORE INSERT ON {table} "
           "BEGIN SELECT RAISE(ABORT, 'planted failure'); END"
    for table in ("status_history", "idempotency_keys")
}


@pytest.mark.parametrize("table", sorted(PLANTED_FAILURES))
def test_task_event_and_key_record_commit_together(client, table):
    # One of the three inserts fails: none of them is kept, and the key stays unused.
    path = client.app.state.service.store.path
    body = {"title": "All or nothing"}
    execute(path, PLANTED_FAILURES[table])
    with pytest.raises(sqlite3.IntegrityError, match="planted failure"):
        post(client, "alice", "atomic-key", body)
    assert tasks(client) == []
    assert rows(path, "SELECT COUNT(*) FROM status_history") == [(0,)]
    assert key_records(path) == []
    execute(path, "DROP TRIGGER planted_failure")
    task = created(post(client, "alice", "atomic-key", body))
    assert [item["id"] for item in tasks(client)] == [task["id"]]
    assert len(history(client, task["id"])) == 1
    assert key_records(path) == [(IDS["alice"], "atomic-key", task["id"])]


def test_only_an_accepted_keyed_request_records_its_key(client):
    path = client.app.state.service.store.path
    for _ in range(2):
        created(client.post("/tasks", json={"title": "Unkeyed"}, headers=HEADERS["alice"]))
    rejected = post(client, "alice", "late-key", {"title": "Observer assigned", "assignee_id": 4})
    assert rejected.status_code == 422, rejected.text
    assert post(client, "observer", "late-key", {"title": "Observer's"}).status_code == 403
    assert key_records(path) == []
    task = created(post(client, "alice", "late-key", {"title": "Valid at last"}))
    assert key_records(path) == [(IDS["alice"], "late-key", task["id"])]
    assert len(tasks(client)) == 3


def test_the_file_holds_one_record_per_actor_and_key(client):
    path = client.app.state.service.store.path
    task = created(post(client, "alice", "unique-key", {"title": "Recorded once"}))
    insert = ("INSERT INTO idempotency_keys(actor_id, idempotency_key, body_digest, task_id, created_at) "
              "VALUES(?, ?, ?, ?, ?)")
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        execute(path, insert, (IDS["alice"], "unique-key", "0" * 64, task["id"], task["created_at"]))
    execute(path, insert, (IDS["bob"], "unique-key", "0" * 64, task["id"], task["created_at"]))
    assert key_records(path) == [(IDS["alice"], "unique-key", task["id"]), (IDS["bob"], "unique-key", task["id"])]


# --- an existing database -------------------------------------------------------------


# The schema of workflow/store.py before status history (baseline 821330ff), verbatim.
BEFORE_HISTORY_SCHEMA = """
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

# The status-history additions of workflow/store.py before idempotency keys were stored
# (c220363), verbatim; that version's file had both parts and PRAGMA user_version 1.
HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    sequence INTEGER NOT NULL CHECK(sequence >= 1),
    actor_id INTEGER NOT NULL REFERENCES users(id),
    from_status TEXT CHECK(from_status IN ('todo', 'in_progress', 'done')),
    to_status TEXT NOT NULL CHECK(to_status IN ('todo', 'in_progress', 'done')),
    changed_at TEXT NOT NULL,
    origin TEXT NOT NULL CHECK(origin IN ('operation', 'migration')),
    UNIQUE(task_id, sequence)
) STRICT;
CREATE TRIGGER IF NOT EXISTS status_history_no_update BEFORE UPDATE ON status_history
BEGIN SELECT RAISE(ABORT, 'status history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS status_history_no_delete BEFORE DELETE ON status_history
BEGIN SELECT RAISE(ABORT, 'status history is append-only'); END;
"""

TASK_COLUMNS = ("id", "title", "description", "creator_id", "assignee_id", "status", "priority",
                "due_at", "work_minutes", "created_at", "updated_at")
EXISTING_TASKS = [
    (1, "Waiting", "", 1, 2, "todo", 3, None, 25,
     "2026-01-01T09:00:00.000000+00:00", "2026-01-02T09:00:00.000000+00:00"),
    (2, "Started", "Half way", 2, 3, "in_progress", 2, "2026-05-01T08:00:00.000000+00:00", 60,
     "2026-01-03T09:00:00.000000+00:00", "2026-01-04T09:00:00.000000+00:00"),
    (3, "Finished — 東京", 'Kept, "quoted"', 3, 2, "done", 5, None, 0,
     "2026-01-05T09:00:00.000000+00:00", "2026-01-06T09:00:00.000000+00:00"),
    (4, "Created after status history", "", 2, None, "in_progress", 1, None, 0,
     "2026-01-09T09:00:00.000000+00:00", "2026-01-10T09:00:00.000000+00:00"),
]
EXISTING_WORK = [
    (1, 1, 2, 25, "2026-01-02T09:00:00.000000+00:00"),
    (2, 2, 3, 40, "2026-01-04T08:00:00.000000+00:00"),
    (3, 2, 2, 20, "2026-01-04T09:00:00.000000+00:00"),
]
# Only in the file with status history: a migration event for each task that existed then,
# and the creation and transition events of a task created after it.
EXISTING_HISTORY = [
    (1, 1, 1, 1, None, "todo", "2026-01-08T09:00:00.000000+00:00", "migration"),
    (2, 2, 1, 2, None, "in_progress", "2026-01-08T09:00:00.000000+00:00", "migration"),
    (3, 3, 1, 3, None, "done", "2026-01-08T09:00:00.000000+00:00", "migration"),
    (4, 4, 1, 2, None, "todo", "2026-01-09T09:00:00.000000+00:00", "operation"),
    (5, 4, 2, 2, "todo", "in_progress", "2026-01-10T09:00:00.000000+00:00", "operation"),
]
TABLE_ROWS = {
    "users": "SELECT * FROM users ORDER BY id",
    "tasks": "SELECT * FROM tasks ORDER BY id",
    "work_logs": "SELECT * FROM work_logs ORDER BY id",
    "status_history": "SELECT * FROM status_history ORDER BY id",
}


def make_existing_file(path, with_history):
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript(BEFORE_HISTORY_SCHEMA + (HISTORY_SCHEMA if with_history else ""))
        conn.executemany("INSERT INTO users(id,name,role,token) VALUES(?,?,?,?)", USERS)
        conn.executemany("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?)", EXISTING_TASKS)
        conn.executemany("INSERT INTO work_logs VALUES(?,?,?,?,?)", EXISTING_WORK)
        if with_history:
            conn.executemany("INSERT INTO status_history VALUES(?,?,?,?,?,?,?,?)", EXISTING_HISTORY)
            conn.execute("PRAGMA user_version = 1")
        conn.commit()


def stored_rows(path):
    """Every row of each data table the file has, by table."""
    names = {name for (name,) in rows(path, "SELECT name FROM sqlite_master WHERE type = 'table'")}
    return {table: rows(path, query) for table, query in TABLE_ROWS.items() if table in names}


def schema(path):
    return set(rows(path, "SELECT type, name, tbl_name, sql FROM sqlite_master"))


@pytest.mark.parametrize("with_history", [False, True], ids=["before-status-history", "before-idempotency-keys"])
def test_existing_database_keeps_all_its_data(tmp_path, with_history):
    path = tmp_path / "existing.sqlite3"
    make_existing_file(path, with_history)
    before, before_schema = stored_rows(path), schema(path)
    assert set(before) == {"users", "tasks", "work_logs"} | ({"status_history"} if with_history else set())
    body = {"title": "Created after the upgrade"}
    with TestClient(create_app(path)) as client:
        opened = stored_rows(path)
        first = created(post(client, "alice", "after-upgrade", body))
    # Every table, row, index and trigger the file had is kept as it was; the upgrade adds
    # the key table (and status history to a file without it) and nothing else.
    assert {table: opened[table] for table in before} == before
    assert before_schema <= schema(path)
    assert {name for kind, name, _, _ in schema(path) - before_schema if kind == "table"} == (
        {"idempotency_keys"} | (set() if with_history else {"status_history"}))
    assert user_version(path) == 1
    with TestClient(create_app(path)) as client:
        assert created(post(client, "alice", "after-upgrade", body))["id"] == first["id"]
        refused = post(client, "alice", "after-upgrade", {"title": "Another body"})
        assert (refused.status_code, refused.json()) == (409, CONFLICT)
        assert [item["id"] for item in tasks(client)] == [row[0] for row in EXISTING_TASKS] + [first["id"]]
        for row in EXISTING_TASKS:
            stored = client.get(f"/tasks/{row[0]}", headers=HEADERS["admin"])
            assert stored.json() == dict(zip(TASK_COLUMNS, row))
    after = stored_rows(path)
    assert {table: after[table][:len(kept)] for table, kept in before.items()} == before
    assert key_records(path) == [(IDS["alice"], "after-upgrade", first["id"])]
