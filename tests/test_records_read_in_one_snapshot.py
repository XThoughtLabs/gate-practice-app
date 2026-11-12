"""GET /tasks/{id}/work and /history: the visibility check and the records come from one state (#47).

SPEC.md sections 1, 3 and 6.1: a member reads only the tasks they created or are assigned,
and work logs and history obey the same rule. Both routes check that the actor may read the
task and then read its records. Between the two, an administrator may remove the assignment
of a member who did not create the task, to no one or to another member, and then commit a
new record: a work entry, or a status change and its history event. From the removal on the
task is unreadable to that member, so their answer must never hold that record. The records
are read in one transaction with the task's row and the task is judged again on that row:
in this order of operations the former assignee gets the uniform 404.

The order is fixed with events, not sleeps. workflow.service.visible is wrapped so that the
reader's request stops right after its visibility check passes; the administrator's requests
run and commit; only then does the reader's request go on. The reader holds no connection
while it is stopped, so no request waits for SQLite's busy timeout.
"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import itertools
import sqlite3
import threading

import pytest

from workflow.service import Problem, visible
import workflow.service


HEADERS = {name: {"Authorization": f"Bearer demo-{name}"} for name in ("admin", "alice", "bob", "observer")}
IDS = {"admin": 1, "alice": 2, "bob": 3, "observer": 4}
NOT_FOUND = {"detail": "task not found"}

# The assignee the administrator gives the task in place of Alice.
REMOVALS = {"unassigned": None, "reassigned": IDS["bob"]}

# A safety limit only: every wait ends as soon as the other thread has done its step.
LIMIT = 60


def log_work(client, task_id, minutes, actor):
    response = client.post(f"/tasks/{task_id}/work", json={"minutes": minutes}, headers=HEADERS[actor])
    assert response.status_code == 200, response.text


def patch(client, task_id, body, actor):
    response = client.patch(f"/tasks/{task_id}", json=body, headers=HEADERS[actor])
    assert response.status_code == 200, response.text


# route: (a record Alice commits before any read, the new record the administrator commits)
RECORDS = {
    "work": (lambda client, task_id: log_work(client, task_id, 20, "alice"),
             lambda client, task_id: log_work(client, task_id, 45, "admin")),
    "history": (lambda client, task_id: patch(client, task_id, {"status": "in_progress"}, "alice"),
                lambda client, task_id: patch(client, task_id, {"status": "done"}, "admin")),
}


def assigned_to_alice(client, route):
    """The administrator's task, assigned to Alice, with one record of hers."""
    body = {"title": "Synthetic task", "assignee_id": IDS["alice"]}
    response = client.post("/tasks", json=body, headers=HEADERS["admin"])
    assert response.status_code == 201, response.text
    task_id = response.json()["id"]
    RECORDS[route][0](client, task_id)
    return task_id


def commit_new_record(route, task_id):
    return lambda client: RECORDS[route][1](client, task_id)


def remove_then_commit(route, task_id, removal):
    """The administrator removes Alice's assignment and then commits a new record."""
    def changes(client):
        patch(client, task_id, {"assignee_id": REMOVALS[removal]}, "admin")
        RECORDS[route][1](client, task_id)
    return changes


def read(client, route, task_id, actor):
    return client.get(f"/tasks/{task_id}/{route}", headers=HEADERS[actor])


def stored(client, route, task_id):
    """The task's records, as the administrator reads them."""
    response = read(client, route, task_id, "admin")
    assert response.status_code == 200, response.text
    return response.json()["items"]


def read_with_changes_between(client, route, task_id, reader, changes):
    """The reader's request for the task's records, with changes(client) run and committed
    after the request's visibility check has passed and before the request goes on."""
    checked, release = threading.Event(), threading.Event()
    held = itertools.count()

    def visible_then_hold(user, task):
        result = visible(user, task)
        if result and user["id"] == IDS[reader] and next(held) == 0:
            checked.set()
            release.wait(timeout=LIMIT)
        return result

    with pytest.MonkeyPatch.context() as patched, ThreadPoolExecutor(1) as pool:
        patched.setattr(workflow.service, "visible", visible_then_hold)
        pending = pool.submit(read, client, route, task_id, reader)
        try:
            assert checked.wait(timeout=LIMIT), "the request did not pass its visibility check"
            changes(client)
        finally:
            release.set()
        return pending.result(timeout=LIMIT)


# --- the regression: a removal and a new record between the check and the read ---------


@pytest.mark.parametrize("removal", sorted(REMOVALS))
@pytest.mark.parametrize("route", sorted(RECORDS))
def test_former_assignee_never_gets_a_record_committed_after_the_removal(client, route, removal):
    task_id = assigned_to_alice(client, route)
    before = stored(client, route, task_id)
    response = read_with_changes_between(client, route, task_id, "alice",
                                         remove_then_commit(route, task_id, removal))
    after = stored(client, route, task_id)
    assert after[:-1] == before and after[-1]["actor_id"] == IDS["admin"]
    # On the code before #47 the answer was 200 with every record, this one included.
    assert after[-1] not in response.json().get("items", []), response.json()
    assert (response.status_code, response.json()) == (404, NOT_FOUND)
    # Later requests: the task stays hidden from Alice, and Bob reads it only as its assignee.
    later = read(client, route, task_id, "alice")
    assert (later.status_code, later.json()) == (404, NOT_FOUND)
    bob = read(client, route, task_id, "bob")
    if REMOVALS[removal] == IDS["bob"]:
        assert (bob.status_code, bob.json()) == (200, {"items": after})
    else:
        assert (bob.status_code, bob.json()) == (404, NOT_FOUND)


# --- controls: the same answers before and after #47 -----------------------------------


@pytest.mark.parametrize("route", sorted(RECORDS))
def test_member_reads_a_record_committed_before_the_request(client, route):
    # With no removal, the administrator's record committed before Alice's request is in it.
    task_id = assigned_to_alice(client, route)
    before = stored(client, route, task_id)
    RECORDS[route][1](client, task_id)
    after = stored(client, route, task_id)
    assert after[:-1] == before and after[-1]["actor_id"] == IDS["admin"]
    response = read(client, route, task_id, "alice")
    assert (response.status_code, response.json()) == (200, {"items": after})


@pytest.mark.parametrize("route", sorted(RECORDS))
def test_member_reads_a_record_committed_after_the_check_without_removal(client, route):
    # The regression's order without the removal: Alice may still read the task, so the
    # record committed after her check is in her answer. It is not frozen at the check.
    task_id = assigned_to_alice(client, route)
    before = stored(client, route, task_id)
    response = read_with_changes_between(client, route, task_id, "alice",
                                         commit_new_record(route, task_id))
    after = stored(client, route, task_id)
    assert after[:-1] == before and after[-1]["actor_id"] == IDS["admin"]
    assert (response.status_code, response.json()) == (200, {"items": after})


@pytest.mark.parametrize("removal", sorted(REMOVALS))
@pytest.mark.parametrize("reader", ["admin", "observer"])
@pytest.mark.parametrize("route", sorted(RECORDS))
def test_admin_and_observer_answers_are_unchanged(client, route, reader, removal):
    # The regression's order: an administrator or observer still reads the task, so their
    # answer holds every record, the one committed after the removal included.
    task_id = assigned_to_alice(client, route)
    before = stored(client, route, task_id)
    response = read_with_changes_between(client, route, task_id, reader,
                                         remove_then_commit(route, task_id, removal))
    after = stored(client, route, task_id)
    assert after[:-1] == before and after[-1]["actor_id"] == IDS["admin"]
    assert (response.status_code, response.json()) == (200, {"items": after})
    later = read(client, route, task_id, reader)
    assert (later.status_code, later.json()) == (200, {"items": after})


# --- the store: the row and the records in one read transaction ------------------------


STORE_READS = {"work": "work_logs", "history": "history"}

# The new record of each route, written straight into the file.
RAW_RECORDS = {
    "work": "INSERT INTO work_logs(task_id, actor_id, minutes, created_at) VALUES(?, 1, 45, ?)",
    "history": "INSERT INTO status_history(task_id, sequence, actor_id, from_status, to_status, "
               "changed_at, origin) VALUES(?, 3, 1, 'in_progress', 'done', ?, 'operation')",
}


@pytest.mark.parametrize("route", sorted(RECORDS))
def test_store_reads_the_judged_row_and_the_records_in_one_transaction(client, route):
    # check runs between the task's row and its records. A write that tries to commit there
    # with no busy timeout is refused at once: the read's shared lock is held (rollback
    # journal). Read in two transactions, the write would commit and its record be returned.
    store = client.app.state.service.store
    task_id = assigned_to_alice(client, route)
    before = stored(client, route, task_id)
    judged = []

    def check(task):
        judged.append(task)
        with closing(sqlite3.connect(store.path, timeout=0)) as conn:
            conn.execute("UPDATE tasks SET assignee_id = NULL WHERE id = ?", (task_id,))
            conn.execute(RAW_RECORDS[route], (task_id, "2026-01-01T00:00:00.000000+00:00"))
            with pytest.raises(sqlite3.OperationalError, match="database is locked"):
                conn.commit()
            conn.rollback()

    assert getattr(store, STORE_READS[route])(task_id, check) == before
    assert [task["assignee_id"] for task in judged] == [IDS["alice"]]
    assert stored(client, route, task_id) == before


@pytest.mark.parametrize("route", sorted(RECORDS))
def test_store_judges_a_missing_task_as_none(client, route):
    # A task missing in the records' transaction, or an id SQLite cannot hold: check gets
    # None, and the service's check answers it with the uniform 404 for every role.
    store = client.app.state.service.store
    task_id = assigned_to_alice(client, route)
    records = getattr(store, STORE_READS[route])
    for missing in (task_id + 1, 2**63):
        judged = []
        assert records(missing, judged.append) == []
        assert judged == [None]
        with pytest.raises(Problem) as refused:
            records(missing, lambda task: workflow.service.authorize_read(store.user("demo-admin"), task))
        assert (refused.value.status, refused.value.detail) == (404, "task not found")
