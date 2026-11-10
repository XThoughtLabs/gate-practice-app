"""A title with U+0000 (SPEC.md sections 2 to 5, issue #39): stored and returned exactly.

A title is a nonblank Unicode string of 1 to 120 characters, preserved exactly, and U+0000
(NUL) is one of its characters like any other. The tasks table checked
length(title) BETWEEN 1 AND 120, but SQLite's length() of a text stops at the first NUL,
so a title that begins with one counted 0, and POST and PATCH answered 500. A file made
before this change gets the new table through a rebuild in its PRAGMA user_version
initialization, which keeps every row and either completes or leaves the file as it was;
see docs/nul-title-migration.md.
"""

from contextlib import closing, contextmanager
import csv
import hashlib
import io
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from workflow.api import create_app
from workflow.store import USERS, Store


HEADERS = {name: {"Authorization": f"Bearer demo-{name}"} for name in ("admin", "alice", "bob", "observer")}
IDS = {"admin": 1, "alice": 2, "bob": 3}
EXPORT_COLUMNS = ["id", "title", "status", "assignee_id"]

# Each title, with the text after its first NUL that a search must find it by (None when
# nothing follows the NUL).
NUL_TITLES = {
    "begins-with-nul": ("\x00Quarterly report", "QUARTERLY rep"),
    "contains-nul": ("Draft\x00final copy", "final copy"),
    "only-nul": ("\x00", None),
    "120-nuls": ("\x00" * 120, None),
    "nul-and-119-four-byte-characters": ("\x00" + "\U0001F600" * 119, "\U0001F600" * 3),
}
TOO_LONG = {
    "121-nuls": "\x00" * 121,
    "120-nuls-then-a-letter": "\x00" * 120 + "X",
    "a-letter-then-120-nuls": "X" + "\x00" * 120,
}


@pytest.fixture
def client(tmp_path):
    # A server error comes back as a 500 response for the test to assert against,
    # not as an exception raised inside the test client.
    with TestClient(create_app(tmp_path / "test.sqlite3"), raise_server_exceptions=False) as result:
        yield result


def post(client, actor, body, key=None):
    headers = {**HEADERS[actor], **({"Idempotency-Key": key} if key else {})}
    return client.post("/tasks", json=body, headers=headers)


def create(client, actor, body):
    response = post(client, actor, body)
    assert response.status_code == 201, response.text
    return response.json()


def read(client, url, **params):
    response = client.get(url, params=params, headers=HEADERS["admin"])
    assert response.status_code == 200, response.text
    return response.json()


def listed(client, q=""):
    """{id: title} of every task GET /tasks lists for q."""
    body = read(client, "/tasks", q=q, limit=100)
    assert body["total"] == len(body["items"])
    return {item["id"]: item["title"] for item in body["items"]}


def exported(client):
    response = client.get("/tasks/export", headers=HEADERS["admin"])
    assert response.status_code == 200, response.text
    return list(csv.reader(io.StringIO(response.text, newline="")))


def history(client, task_id):
    return read(client, f"/tasks/{task_id}/history")["items"]


def rows(path, query, params=()):
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute(query, params).fetchall()


def execute(path, statement, params=()):
    with closing(sqlite3.connect(path)) as conn:
        conn.execute(statement, params)
        conn.commit()


def user_version(path):
    return rows(path, "PRAGMA user_version")[0][0]


def schema(path):
    return set(rows(path, "SELECT type, name, tbl_name, sql FROM sqlite_master"))


# --- a new file: every route returns the title as it was sent ---------------------------


@pytest.mark.parametrize(("title", "after_nul"), list(NUL_TITLES.values()), ids=list(NUL_TITLES))
def test_nul_title_is_created_and_returned_exactly_by_every_route(client, title, after_nul):
    decoy = create(client, "alice", {"title": "Plain decoy"})
    task = create(client, "alice", {"title": title, "due_at": "2026-01-01T00:00:00Z"})
    assert task["title"] == title
    path = client.app.state.service.store.path
    assert rows(path, "SELECT title FROM tasks WHERE id = ?", (task["id"],)) == [(title,)]
    assert read(client, f"/tasks/{task['id']}") == task
    assert listed(client) == {decoy["id"]: "Plain decoy", task["id"]: title}
    assert listed(client, "\x00") == {task["id"]: title}
    if after_nul is not None:
        assert listed(client, after_nul) == {task["id"]: title}
    overdue = read(client, "/tasks/overdue", at="2026-06-01T00:00:00Z")["items"]
    assert overdue == [task]
    assert exported(client) == [EXPORT_COLUMNS, [str(decoy["id"]), "Plain decoy", "todo", ""],
                                [str(task["id"]), title, "todo", ""]]
    assert [(event["from_status"], event["to_status"]) for event in history(client, task["id"])] == [(None, "todo")]


def test_title_of_120_four_byte_characters_is_stored(client):
    # The most UTF-8 bytes a title can take (480): the table's byte bound admits it.
    title = "\U0001F600" * 120
    task = create(client, "alice", {"title": title})
    assert read(client, f"/tasks/{task['id']}")["title"] == title
    assert exported(client)[1] == [str(task["id"]), title, "todo", ""]


@pytest.mark.parametrize("title", list(TOO_LONG.values()), ids=list(TOO_LONG))
def test_title_of_121_characters_with_nul_is_refused(client, title):
    refused = post(client, "alice", {"title": title})
    assert refused.status_code == 422, refused.text
    task = create(client, "alice", {"title": "Kept as it is"})
    for body in ({"title": title}, {"title": title, "status": "in_progress"}):
        response = client.patch(f"/tasks/{task['id']}", json=body, headers=HEADERS["alice"])
        assert response.status_code == 422, response.text
    assert listed(client) == {task["id"]: "Kept as it is"}
    assert read(client, f"/tasks/{task['id']}") == task
    assert len(history(client, task["id"])) == 1


@pytest.mark.parametrize(("title", "kept"), [
    ("\x00" * 120, True),
    ("\U0001F600" * 120, True),
    ("", False),
    ("x" * 121, False),
    ("\x00" + "x" * 480, False),
], ids=["120-nuls", "480-bytes", "empty", "121-characters-without-nul", "481-bytes"])
def test_tasks_table_refuses_only_what_no_title_can_be(client, title, kept):
    # The table's own check, under the API's: it admits every title of 1 to 120 characters,
    # still counts a title without NUL exactly, and refuses what no such title can be.
    path = client.app.state.service.store.path
    insert = ("INSERT INTO tasks(title, creator_id, status, priority, created_at, updated_at) "
              "VALUES(?, 2, 'todo', 3, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')")
    if kept:
        execute(path, insert, (title,))
        assert rows(path, "SELECT title FROM tasks") == [(title,)]
    else:
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            execute(path, insert, (title,))
        assert rows(path, "SELECT COUNT(*) FROM tasks") == [(0,)]


# --- PATCH ------------------------------------------------------------------------------


@pytest.mark.parametrize(("title", "after_nul"), list(NUL_TITLES.values()), ids=list(NUL_TITLES))
def test_patch_sets_a_nul_title_without_an_event(client, title, after_nul):
    task = create(client, "alice", {"title": "Plain title"})
    response = client.patch(f"/tasks/{task['id']}", json={"title": title}, headers=HEADERS["alice"])
    assert response.status_code == 200, response.text
    assert response.json()["title"] == title
    assert response.json()["status"] == "todo"
    assert read(client, f"/tasks/{task['id']}") == response.json()
    assert listed(client) == {task["id"]: title}
    assert exported(client)[1] == [str(task["id"]), title, "todo", ""]
    assert [(event["from_status"], event["to_status"]) for event in history(client, task["id"])] == [(None, "todo")]


@pytest.mark.parametrize(("title", "after_nul"), list(NUL_TITLES.values()), ids=list(NUL_TITLES))
def test_patch_sets_a_nul_title_with_a_status_change_and_one_event(client, title, after_nul):
    task = create(client, "alice", {"title": "Plain title"})
    body = {"title": title, "status": "in_progress"}
    response = client.patch(f"/tasks/{task['id']}", json=body, headers=HEADERS["alice"])
    assert response.status_code == 200, response.text
    assert (response.json()["title"], response.json()["status"]) == (title, "in_progress")
    assert read(client, f"/tasks/{task['id']}") == response.json()
    assert exported(client)[1] == [str(task["id"]), title, "in_progress", ""]
    events = history(client, task["id"])
    assert [(event["sequence"], event["actor_id"], event["from_status"], event["to_status"], event["origin"])
            for event in events] == [(1, IDS["alice"], None, "todo", "operation"),
                                     (2, IDS["alice"], "todo", "in_progress", "operation")]
    assert events[1]["changed_at"] == response.json()["updated_at"]


# --- a file made before this change -----------------------------------------------------


# The schema of workflow/store.py before this change (a9b3d88), verbatim. Its file is at
# PRAGMA user_version 1.
BEFORE_SCHEMA = """
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
CREATE TABLE IF NOT EXISTS idempotency_keys (
    actor_id INTEGER NOT NULL REFERENCES users(id),
    idempotency_key TEXT NOT NULL,
    body_digest TEXT NOT NULL,
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    created_at TEXT NOT NULL,
    PRIMARY KEY(actor_id, idempotency_key)
) STRICT;
"""


def digest(body):
    """The digest the service stores with a key: SHA-256 of the validated body (docs/idempotency-keys.md)."""
    values = {"description": "", "assignee_id": None, "priority": 3, "due_at": None, **body}
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def at(day):
    return f"2026-01-{day:02d}T09:00:00.000000+00:00"


TASK_COLUMNS = ("id", "title", "description", "creator_id", "assignee_id", "status", "priority",
                "due_at", "work_minutes", "created_at", "updated_at")
# Task 4 is missing, and task 2's title holds a NUL that the earlier check let through
# because a character comes before it.
EXISTING_TASKS = [
    (1, "Waiting", "", 1, 2, "todo", 3, None, 25, at(1), at(2)),
    (2, "Kept\x00after a NUL", "Half way", 2, 3, "in_progress", 2, "2026-05-01T08:00:00.000000+00:00", 60,
     at(3), at(4)),
    (3, "Finished — 東京", 'Kept, "quoted"', 3, 2, "done", 5, None, 0, at(5), at(6)),
    (5, "Keyed", "", 2, None, "todo", 3, None, 0, at(9), at(9)),
]
EXISTING_WORK = [
    (1, 1, 2, 25, at(2)),
    (2, 2, 3, 40, at(4)),
    (3, 2, 2, 20, at(4)),
]
EXISTING_HISTORY = [
    (1, 1, 1, 1, None, "todo", at(8), "migration"),
    (2, 2, 1, 2, None, "in_progress", at(8), "migration"),
    (3, 3, 1, 3, None, "done", at(8), "migration"),
    (4, 5, 1, 2, None, "todo", at(9), "operation"),
]
EXISTING_KEYS = [(IDS["alice"], "keyed-create", digest({"title": "Keyed"}), 5, at(9))]
# Above the highest task id, as in a file whose last tasks were removed by hand: new tasks
# continue from the stored sequence, so a rebuild that recomputed it would give id 6, not 8.
TASK_SEQUENCE = 7

CONTENTS = {
    "users": "SELECT * FROM users ORDER BY id",
    "tasks": "SELECT * FROM tasks ORDER BY id",
    "work_logs": "SELECT * FROM work_logs ORDER BY id",
    "status_history": "SELECT * FROM status_history ORDER BY id",
    "idempotency_keys": "SELECT * FROM idempotency_keys ORDER BY actor_id, idempotency_key",
    "sqlite_sequence": "SELECT * FROM sqlite_sequence ORDER BY name",
}


def make_existing_file(path):
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript(BEFORE_SCHEMA)
        conn.executemany("INSERT INTO users(id,name,role,token) VALUES(?,?,?,?)", USERS)
        conn.executemany("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?)", EXISTING_TASKS)
        conn.executemany("INSERT INTO work_logs VALUES(?,?,?,?,?)", EXISTING_WORK)
        conn.executemany("INSERT INTO status_history VALUES(?,?,?,?,?,?,?,?)", EXISTING_HISTORY)
        conn.executemany("INSERT INTO idempotency_keys VALUES(?,?,?,?,?)", EXISTING_KEYS)
        conn.execute("UPDATE sqlite_sequence SET seq = ? WHERE name = 'tasks'", (TASK_SEQUENCE,))
        conn.execute("PRAGMA user_version = 1")
        conn.commit()
    return path


def contents(path):
    """Every row of every table the file holds data in, sqlite_sequence included."""
    return {table: rows(path, query) for table, query in CONTENTS.items()}


def new_file_schema(tmp_path):
    path = tmp_path / "new.sqlite3"
    create_app(path)
    return schema(path)


def assert_upgraded(path, kept, new_schema):
    """Every row and sequence kept, the schema of a new file, and the file at user_version 2."""
    assert contents(path) == kept
    assert schema(path) == new_schema
    assert user_version(path) == 2
    assert rows(path, "PRAGMA integrity_check") == [("ok",)]
    assert rows(path, "PRAGMA foreign_key_check") == []


def test_existing_file_keeps_everything_and_then_takes_nul_titles(tmp_path):
    path = make_existing_file(tmp_path / "existing.sqlite3")
    before, before_schema = contents(path), schema(path)
    assert [len(table) for table in before.values()] == [4, 4, 3, 4, 1, 3]
    with TestClient(create_app(path)):
        pass
    assert_upgraded(path, before, new_file_schema(tmp_path))
    # Only the tasks table's own definition changed; its indexes, the triggers and every
    # other table are as they were.
    assert {entry[:2] for entry in before_schema ^ schema(path)} == {("table", "tasks")}
    assert len(before_schema ^ schema(path)) == 2
    # A file already upgraded is not touched again.
    upgraded = path.read_bytes()
    with TestClient(create_app(path)):
        pass
    assert path.read_bytes() == upgraded

    with TestClient(create_app(path), raise_server_exceptions=False) as client:
        for row in EXISTING_TASKS:
            assert read(client, f"/tasks/{row[0]}") == dict(zip(TASK_COLUMNS, row))
        assert [(item["actor_id"], item["minutes"]) for item in read(client, "/tasks/2/work")["items"]] == [
            (3, 40), (2, 20)]
        assert [(event["sequence"], event["to_status"], event["origin"]) for event in history(client, 2)] == [
            (1, "in_progress", "migration")]
        assert listed(client, "AFTER A nul") == {2: "Kept\x00after a NUL"}
        # The key stored before the upgrade still names its task.
        retry = post(client, "alice", {"title": "Keyed"}, key="keyed-create")
        assert (retry.status_code, retry.json()["id"]) == (201, 5)
        task = create(client, "alice", {"title": "\x00Created after the upgrade"})
        assert task["id"] == TASK_SEQUENCE + 1
        assert read(client, f"/tasks/{task['id']}")["title"] == "\x00Created after the upgrade"
        patched = client.patch("/tasks/1", json={"title": "\x00Waiting no more", "status": "in_progress"},
                               headers=HEADERS["admin"])
        assert patched.status_code == 200, patched.text
        assert [(event["from_status"], event["to_status"], event["origin"]) for event in history(client, 1)] == [
            (None, "todo", "migration"), ("todo", "in_progress", "operation")]
        assert exported(client) == [EXPORT_COLUMNS,
                                    ["1", "\x00Waiting no more", "in_progress", "2"],
                                    ["2", "Kept\x00after a NUL", "in_progress", "3"],
                                    ["3", "Finished — 東京", "done", "2"],
                                    ["5", "Keyed", "todo", ""],
                                    [str(task["id"]), "\x00Created after the upgrade", "todo", ""]]
    assert contents(path)["work_logs"] == before["work_logs"]
    assert contents(path)["idempotency_keys"] == before["idempotency_keys"]


def test_rebuild_keeps_an_index_and_a_trigger_the_file_has_on_tasks(tmp_path):
    # Dropping the old table drops every index and trigger on it; the rebuild creates them
    # again from the file's own definitions, after the tasks are back, so no trigger fires
    # for the copy.
    path = make_existing_file(tmp_path / "existing.sqlite3")
    execute(path, "CREATE INDEX tasks_due ON tasks(due_at) WHERE due_at IS NOT NULL")
    execute(path, "CREATE TRIGGER tasks_kept BEFORE DELETE ON tasks BEGIN SELECT RAISE(ABORT, 'tasks are kept'); END")
    # A new task's id is not yet assigned in a BEFORE trigger (it reads -1); a copied task's is.
    execute(path, "CREATE TRIGGER tasks_no_copy BEFORE INSERT ON tasks WHEN NEW.id BETWEEN 1 AND 5 "
                  "BEGIN SELECT RAISE(ABORT, 'a stored id is inserted again'); END")
    before = contents(path)
    added = {entry for entry in schema(path) if entry[1] in ("tasks_due", "tasks_kept", "tasks_no_copy")}
    assert len(added) == 3
    with TestClient(create_app(path)) as client:
        assert create(client, "alice", {"title": "\x00Kept"})["id"] == TASK_SEQUENCE + 1
    assert added <= schema(path)
    assert schema(path) - added == new_file_schema(tmp_path)
    assert contents(path)["tasks"][:len(before["tasks"])] == before["tasks"]
    with pytest.raises(sqlite3.IntegrityError, match="tasks are kept"):
        execute(path, "DELETE FROM tasks WHERE id = 1")


def test_new_file_starts_upgraded_and_a_restart_does_not_touch_it(tmp_path):
    path = tmp_path / "new.sqlite3"
    with TestClient(create_app(path)) as client:
        create(client, "alice", {"title": "\x00First"})
    assert user_version(path) == 2
    after = path.read_bytes()
    with TestClient(create_app(path)):
        pass
    assert path.read_bytes() == after


# --- an upgrade that fails part-way -----------------------------------------------------


class FailingConnection:
    """A store connection that fails at the first statement beginning with `failing` once a
    write transaction has begun: part-way through the upgrade, after the steps before it."""

    def __init__(self, conn, failing):
        self.conn, self.failing, self.begun = conn, failing, False

    def execute(self, sql, *args):
        if sql == "BEGIN IMMEDIATE":
            self.begun = True
        elif self.begun and sql.lstrip().startswith(self.failing):
            raise sqlite3.OperationalError(f"injected failure at {self.failing}")
        return self.conn.execute(sql, *args)

    def __getattr__(self, name):
        return getattr(self.conn, name)


def fail_upgrade_at(monkeypatch, failing):
    connect = Store.connect

    @contextmanager
    def failing_connect(self):
        with connect(self) as conn:
            yield FailingConnection(conn, failing)

    monkeypatch.setattr(Store, "connect", failing_connect)


# Each step of the upgrade in its order, by the beginning of its statement.
FAILURE_POINTS = {
    "copying-the-tasks-out": "CREATE TEMP TABLE",
    "dropping-the-old-table": "DROP TABLE tasks",
    "creating-the-new-table": "CREATE TABLE IF NOT EXISTS tasks",
    "copying-the-tasks-back": "INSERT INTO tasks",
    "dropping-the-copy": "DROP TABLE task_rows",
    "creating-an-index-again": "CREATE INDEX",
    "restoring-the-sequence": "INSERT INTO sqlite_sequence",
    "checking-foreign-keys": "PRAGMA foreign_key_check",
    "setting-user-version": "PRAGMA user_version =",
}


@pytest.mark.parametrize("failing", list(FAILURE_POINTS.values()), ids=list(FAILURE_POINTS))
def test_upgrade_failing_part_way_leaves_the_file_unchanged_and_the_next_start_completes_it(
        tmp_path, monkeypatch, failing):
    path = make_existing_file(tmp_path / "existing.sqlite3")
    before, untouched = contents(path), path.read_bytes()
    fail_upgrade_at(monkeypatch, failing)
    with pytest.raises(sqlite3.OperationalError, match="injected failure"):
        create_app(path)
    monkeypatch.undo()
    assert path.read_bytes() == untouched
    with TestClient(create_app(path)):
        pass
    assert_upgraded(path, before, new_file_schema(tmp_path))
    with TestClient(create_app(path)) as client:
        task = create(client, "alice", {"title": "\x00After the retry"})
    assert task["id"] == TASK_SEQUENCE + 1


# Rows a file can hold that stop the upgrade, each with the statement that removes it again.
PLANTED_FAILURES = {
    # The earlier check counted this title as 1 character; the new table counts its 502 bytes.
    "title-the-new-table-refuses": (
        ("INSERT INTO tasks VALUES(6, ?, '', 2, NULL, 'todo', 3, NULL, 0, ?, ?)", ("A\x00" + "B" * 500, at(10), at(10))),
        "DELETE FROM tasks WHERE id = 6",
        "CHECK constraint failed",
    ),
    "work-log-of-a-missing-task": (
        ("INSERT INTO work_logs VALUES(4, 99, 2, 10, ?)", (at(10),)),
        "DELETE FROM work_logs WHERE id = 4",
        "FOREIGN KEY constraint failed",
    ),
}


@pytest.mark.parametrize("planted", list(PLANTED_FAILURES.values()), ids=list(PLANTED_FAILURES))
def test_upgrade_stopped_by_a_stored_row_leaves_the_file_unchanged(tmp_path, planted):
    (plant, params), remove, error = planted
    path = make_existing_file(tmp_path / "existing.sqlite3")
    execute(path, plant, params)
    untouched = path.read_bytes()
    with pytest.raises(sqlite3.IntegrityError, match=error):
        create_app(path)
    assert path.read_bytes() == untouched
    assert user_version(path) == 1
    execute(path, remove)
    kept = contents(path)
    with TestClient(create_app(path)):
        pass
    assert_upgraded(path, kept, new_file_schema(tmp_path))
