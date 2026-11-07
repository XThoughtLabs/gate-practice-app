"""Acceptance tests for SPEC.md sections 4 and 6.1: upgrading an existing database.

Written from SPEC.md, TASK.md, OPEN-ISSUES.md and README.md alone, without the
application's code. SPEC.md asks that an existing SQLite file keep its tasks and
work logs through the upgrade, and that every pre-upgrade task receive one initial
history event with origin "migration", from_status null, to_status its stored
status and actor_id its creator.

The documents do not describe the schema of the database before the upgrade, so
these tests make a pre-upgrade file out of a current one. They find the table that
holds status history by its behaviour alone (one more row after a task is created
and after its status changes, none after a title edit), drop it with the triggers
and views that use it, and reset PRAGMA user_version to 0, the state of a file that
never had status history. Tasks, work logs and every other table are left as they
are. When no such table exists, the file has no status history to remove and is
left untouched.

Limits of this construction, for whoever adjudicates a failure here: it expects
create_app(db_path) to perform the upgrade when it opens the file (the
"backward-compatible initialization" SPEC.md section 4 allows), and it cannot
reproduce a separate migration command, a migration-tracking table, or columns
and indexes that the upgrade added to other tables.
"""

import gc
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from workflow.api import create_app

TOKENS = {
    "admin": "demo-admin",
    "alice": "demo-alice",
    "bob": "demo-bob",
    "observer": "demo-observer",
}


def auth(actor):
    return {"Authorization": f"Bearer {TOKENS[actor]}"}


@contextmanager
def running_app(db_path):
    with TestClient(create_app(db_path=db_path), raise_server_exceptions=False) as test_client:
        yield test_client


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


def parse_utc(value):
    """Parse an ISO-8601 timestamp and require it to carry the UTC offset."""
    assert isinstance(value, str), value
    parsed = datetime.fromisoformat(value)
    assert parsed.utcoffset() == timedelta(0), value
    return parsed


def create_task(client, actor, **fields):
    response = client.post("/tasks", json={"title": "Synthetic task", **fields}, headers=auth(actor))
    assert response.status_code == 201, response.text
    return response.json()


def get_task(client, task_id):
    response = client.get(f"/tasks/{task_id}", headers=auth("admin"))
    assert response.status_code == 200, response.text
    return response.json()


def set_status(client, actor, task_id, status):
    response = client.patch(f"/tasks/{task_id}", json={"status": status}, headers=auth(actor))
    assert response.status_code == 200, response.text
    return response.json()


def log_work(client, actor, task_id, minutes):
    response = client.post(f"/tasks/{task_id}/work", json={"minutes": minutes}, headers=auth(actor))
    assert response.status_code == 200, response.text


def work_items(client, task_id):
    response = client.get(f"/tasks/{task_id}/work", headers=auth("admin"))
    assert response.status_code == 200, response.text
    return response.json()["items"]


def history(client, task_id):
    response = client.get(f"/tasks/{task_id}/history", headers=auth("admin"))
    assert response.status_code == 200, response.text
    return response.json()["items"]


def listed_ids(client):
    response = client.get("/tasks", params={"limit": 100}, headers=auth("admin"))
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


def assert_event(event, sequence, actor_id, from_status, to_status, origin):
    assert event["sequence"] == sequence, event
    assert event["actor_id"] == actor_id, event
    assert event["from_status"] == from_status, event
    assert event["to_status"] == to_status, event
    assert event["origin"] == origin, event
    parse_utc(event["changed_at"])


# --- making a pre-upgrade file ---------------------------------------------------------


def quoted(name):
    return '"' + name.replace('"', '""') + '"'


def row_counts(db_path):
    connection = sqlite3.connect(db_path)
    try:
        names = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite%'"
            )
        ]
        return {name: connection.execute(f"SELECT COUNT(*) FROM {quoted(name)}").fetchone()[0] for name in names}
    finally:
        connection.close()


def find_history_tables(client, db_path):
    """Create a probe task and return it with the tables that behave as status history."""
    before = row_counts(db_path)
    probe = create_task(client, "alice", title="History probe")
    created = row_counts(db_path)
    edited = client.patch(f"/tasks/{probe['id']}", json={"title": "History probe, edited"}, headers=auth("alice"))
    assert edited.status_code == 200, edited.text
    after_edit = row_counts(db_path)
    set_status(client, "alice", probe["id"], "in_progress")
    after_move = row_counts(db_path)
    tables = [
        name
        for name, count in after_move.items()
        if created.get(name) == before.get(name, 0) + 1
        and after_edit.get(name) == created.get(name)
        and count == after_edit.get(name, -2) + 1
    ]
    return probe, tables


def remove_status_history(db_path, tables):
    """Drop the status-history tables, the triggers and views that use them, and reset user_version."""
    if not tables:
        return
    connection = sqlite3.connect(db_path)
    try:
        dependants = [
            (kind, name)
            for kind, name, sql in connection.execute(
                "SELECT type, name, sql FROM sqlite_master WHERE type IN ('trigger', 'view') AND sql IS NOT NULL"
            )
            if any(table.lower() in sql.lower() for table in tables)
        ]
        for kind, name in dependants:
            connection.execute(f"DROP {kind.upper()} IF EXISTS {quoted(name)}")
        for name in tables:
            connection.execute(f"DROP TABLE {quoted(name)}")
        connection.execute("PRAGMA user_version = 0")
        connection.commit()
    finally:
        connection.close()


@pytest.fixture
def pre_upgrade(tmp_path):
    """A database file holding tasks and work logs but no status history, and what it held."""
    db_path = str(tmp_path / "workflow.sqlite3")
    with running_app(db_path) as client:
        ids = user_ids(client)
        probe, history_tables = find_history_tables(client, db_path)

        waiting = create_task(client, "admin", title="Assigned to Alice", assignee_id=ids["alice"])
        log_work(client, "alice", waiting["id"], 25)

        finished = create_task(client, "alice", title="Finished by Bob", assignee_id=ids["bob"])
        set_status(client, "bob", finished["id"], "in_progress")
        log_work(client, "bob", finished["id"], 40)
        log_work(client, "alice", finished["id"], 20)
        set_status(client, "bob", finished["id"], "done")

        reopened = create_task(client, "bob", title="Reopened by the admin")
        set_status(client, "bob", reopened["id"], "in_progress")
        set_status(client, "bob", reopened["id"], "done")
        set_status(client, "admin", reopened["id"], "in_progress")
        log_work(client, "admin", reopened["id"], 15)

        dated = create_task(
            client,
            "admin",
            title="Dated, described — 東京",
            description="Kept through the upgrade",
            priority=5,
            due_at="2026-05-01T08:00:00Z",
        )

        task_ids = sorted([probe["id"], waiting["id"], finished["id"], reopened["id"], dated["id"]])
        tasks = {task_id: get_task(client, task_id) for task_id in task_ids}
        work = {task_id: work_items(client, task_id) for task_id in task_ids}
    # Release the closed application, and with it any connection it still holds.
    del client
    gc.collect()
    remove_status_history(db_path, history_tables)
    return {
        "db_path": db_path,
        "ids": ids,
        "tasks": tasks,
        "work": work,
        "waiting": waiting["id"],
        "history_tables": history_tables,
    }


# --- tests -----------------------------------------------------------------------------


def test_spec_4_upgrade_preserves_tasks_and_work_logs(pre_upgrade):
    """SPEC.md section 4: schema/data changes preserve the tasks and work logs of an existing database."""
    with running_app(pre_upgrade["db_path"]) as client:
        assert listed_ids(client) == sorted(pre_upgrade["tasks"])
        for task_id, expected in pre_upgrade["tasks"].items():
            assert get_task(client, task_id) == expected
            assert work_items(client, task_id) == pre_upgrade["work"][task_id]


def test_spec_6_1_pre_upgrade_task_gets_one_migration_event(pre_upgrade):
    """SPEC.md section 6.1: each pre-upgrade task gets one initial event, origin migration, from null to its
    stored status, by its creator; no past transitions are invented."""
    with running_app(pre_upgrade["db_path"]) as client:
        for task_id, task in pre_upgrade["tasks"].items():
            events = history(client, task_id)
            assert len(events) == 1, {
                "task": task,
                "events": events,
                "history tables dropped to make the pre-upgrade file": pre_upgrade["history_tables"],
            }
            assert_event(events[0], 1, task["creator_id"], None, task["status"], "migration")


def test_spec_6_1_migration_event_is_not_repeated_or_rewritten_on_later_restarts(pre_upgrade):
    """SPEC.md section 6.1: the one migration event survives later restarts unchanged and is not added again."""
    with running_app(pre_upgrade["db_path"]) as client:
        first = {task_id: history(client, task_id) for task_id in pre_upgrade["tasks"]}
    for _ in range(2):
        with running_app(pre_upgrade["db_path"]) as client:
            assert {task_id: history(client, task_id) for task_id in pre_upgrade["tasks"]} == first
    assert all(len(events) == 1 for events in first.values()), first


def test_spec_6_1_transition_after_upgrade_appends_an_operation_event(pre_upgrade):
    """SPEC.md section 6.1: after the migration event, a new transition is sequence 2 with origin operation."""
    task_id = pre_upgrade["waiting"]
    task = pre_upgrade["tasks"][task_id]
    with running_app(pre_upgrade["db_path"]) as client:
        set_status(client, "alice", task_id, "in_progress")
        events = history(client, task_id)
    assert len(events) == 2, events
    assert_event(events[0], 1, task["creator_id"], None, "todo", "migration")
    assert_event(events[1], 2, pre_upgrade["ids"]["alice"], "todo", "in_progress", "operation")


def test_spec_6_1_task_created_after_upgrade_gets_an_operation_creation_event(pre_upgrade):
    """SPEC.md section 6.1: tasks created after the upgrade get a creation event with origin operation."""
    with running_app(pre_upgrade["db_path"]) as client:
        created = create_task(client, "bob", title="Created after the upgrade")
        events = history(client, created["id"])
    assert len(events) == 1, events
    assert_event(events[0], 1, pre_upgrade["ids"]["bob"], None, "todo", "operation")


def test_spec_6_1_restart_adds_no_migration_event_to_current_tasks(tmp_path):
    """SPEC.md sections 4 and 6.1: restarting on an already upgraded file keeps each history as it was;
    tasks created after the upgrade never receive a migration event."""
    db_path = str(tmp_path / "workflow.sqlite3")
    with running_app(db_path) as client:
        task = create_task(client, "alice", title="Current task")
        set_status(client, "alice", task["id"], "in_progress")
        before = history(client, task["id"])
    for _ in range(2):
        with running_app(db_path) as client:
            assert history(client, task["id"]) == before
    assert [event["origin"] for event in before] == ["operation", "operation"], before
