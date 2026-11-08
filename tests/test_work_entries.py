"""POST /tasks/{id}/work (SPEC.md sections 3 and 4): each accepted entry is recorded once.

An entry and its addition to the task's work_minutes are written in one transaction from
the stored value, and the entry is judged there against the task's stored visibility and
status. So work_minutes always equals the sum of the task's entries, also for simultaneous
requests and after a restart, and a refused entry writes nothing.
"""

from concurrent.futures import ThreadPoolExecutor
import contextlib
import itertools
import threading

import pytest
from fastapi.testclient import TestClient

from workflow.api import create_app
from workflow.service import visible
import workflow.service


HEADERS = {name: {"Authorization": f"Bearer demo-{name}"} for name in ("admin", "alice", "bob", "observer")}
IDS = {"admin": 1, "alice": 2, "bob": 3}
NOT_FOUND = {"detail": "task not found"}
DONE = {"detail": "completed tasks do not accept work"}

# (actor, minutes) of each simultaneous entry: the creator, the assignee and the admin.
ENTRIES = [(("alice", "bob", "admin")[index % 3], index + 1) for index in range(24)]


def create(client, creator, assignee=None):
    body = {"title": "Synthetic task", "assignee_id": IDS[assignee] if assignee else None}
    response = client.post("/tasks", json=body, headers=HEADERS[creator])
    assert response.status_code == 201, response.text
    return response.json()


def patch(client, task_id, body, actor):
    response = client.patch(f"/tasks/{task_id}", json=body, headers=HEADERS[actor])
    assert response.status_code == 200, response.text
    return response.json()


def log_work(client, task_id, minutes, actor):
    return client.post(f"/tasks/{task_id}/work", json={"minutes": minutes}, headers=HEADERS[actor])


def state(client, task_id):
    """The stored task and its work entries, as the administrator reads them."""
    task = client.get(f"/tasks/{task_id}", headers=HEADERS["admin"])
    work = client.get(f"/tasks/{task_id}/work", headers=HEADERS["admin"])
    assert (task.status_code, work.status_code) == (200, 200), (task.text, work.text)
    return task.json(), work.json()["items"]


def assert_recorded_once(client, task_id, entries):
    """Each (actor, minutes) entry is recorded exactly once and work_minutes is their sum."""
    task, work = state(client, task_id)
    assert sorted((item["actor_id"], item["minutes"]) for item in work) == sorted(
        (IDS[actor], minutes) for actor, minutes in entries)
    assert task["work_minutes"] == sum(minutes for _, minutes in entries)


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


def test_simultaneous_work_entries_are_each_recorded_once(tmp_path, monkeypatch):
    path = tmp_path / "work.sqlite3"
    with TestClient(create_app(path)) as client:
        task = create(client, "alice", "bob")
        # A request that reads the task through Store.task is held there until every
        # request has read it, so a total read in one step and written later from that
        # value would keep only the last writer's entry. Reads that cannot all happen
        # together, such as reads made while holding the write lock, are let through.
        store = client.app.state.service.store
        read = store.task
        all_read = threading.Barrier(len(ENTRIES), timeout=5)
        calls = itertools.count()

        def read_then_wait(task_id):
            row = read(task_id)
            if next(calls) < len(ENTRIES):
                with contextlib.suppress(threading.BrokenBarrierError):
                    all_read.wait()
            return row

        monkeypatch.setattr(store, "task", read_then_wait)
        responses = run_together(len(ENTRIES), lambda index: log_work(
            client, task["id"], ENTRIES[index][1], ENTRIES[index][0]))
        monkeypatch.undo()
        assert [response.status_code for response in responses] == [200] * len(ENTRIES)
        # The entry written last sees every other one in the stored total.
        assert max(response.json()["work_minutes"] for response in responses) == sum(
            minutes for _, minutes in ENTRIES)
        assert_recorded_once(client, task["id"], ENTRIES)
    with TestClient(create_app(path)) as client:
        assert_recorded_once(client, task["id"], ENTRIES)


def test_work_on_a_done_task_is_refused_and_changes_nothing(client, monkeypatch):
    task = create(client, "alice", "alice")
    assert log_work(client, task["id"], 10, "alice").status_code == 200
    patch(client, task["id"], {"status": "in_progress"}, "alice")
    store = client.app.state.service.store
    earlier_read = store.task(task["id"])
    patch(client, task["id"], {"status": "done"}, "alice")
    before = state(client, task["id"])
    refused = log_work(client, task["id"], 30, "alice")
    assert (refused.status_code, refused.json()) == (409, DONE)
    assert state(client, task["id"]) == before
    # The request's earlier read still shows the task in progress: another request
    # finished it before this entry's write. The refusal is judged at the write.
    monkeypatch.setattr(store, "task", lambda task_id: dict(earlier_read))
    refused = log_work(client, task["id"], 30, "alice")
    monkeypatch.undo()
    assert (refused.status_code, refused.json()) == (409, DONE)
    assert state(client, task["id"]) == before
    assert_recorded_once(client, task["id"], [("alice", 10)])


def test_a_task_is_not_finished_between_an_entrys_check_and_its_write(client, monkeypatch):
    # Alice's entry is held in its check while she finishes the task from another request.
    # The finish must wait for the entry's write; otherwise the entry, judged on a task in
    # progress, would be written to a task that is already done.
    task = create(client, "alice", "alice")
    patch(client, task["id"], {"status": "in_progress"}, "alice")
    checking, finished = threading.Event(), threading.Event()
    calls = itertools.count()

    def visible_then_hold(user, row):
        if next(calls) == 0:
            checking.set()
            finished.wait(timeout=1)
        return visible(user, row)

    monkeypatch.setattr(workflow.service, "visible", visible_then_hold)
    with ThreadPoolExecutor(1) as pool:
        entry = pool.submit(log_work, client, task["id"], 30, "alice")
        assert checking.wait(timeout=10)
        finish = client.patch(f"/tasks/{task['id']}", json={"status": "done"}, headers=HEADERS["alice"])
        finished.set()
        logged = entry.result(timeout=30)
    monkeypatch.undo()
    assert (finish.status_code, finish.json()["status"]) == (200, "done"), finish.text
    if logged.status_code == 200:
        # Accepted: written before the finish, so the finished task already counts it.
        assert finish.json()["work_minutes"] == 30
        assert_recorded_once(client, task["id"], [("alice", 30)])
    else:
        # Refused: judged after the finish, and nothing written.
        assert (logged.status_code, logged.json()) == (409, DONE)
        assert_recorded_once(client, task["id"], [])


def test_work_is_judged_against_the_stored_assignment(client, monkeypatch):
    # Alice's request first reads the admin's task as assigned to her; the admin hands it
    # to Bob before her entry's write. She no longer sees the task: uniform 404, no entry.
    task = create(client, "admin", "alice")
    store = client.app.state.service.store
    earlier_read = store.task(task["id"])
    patch(client, task["id"], {"assignee_id": IDS["bob"]}, "admin")
    before = state(client, task["id"])
    monkeypatch.setattr(store, "task", lambda task_id: dict(earlier_read))
    refused = log_work(client, task["id"], 30, "alice")
    monkeypatch.undo()
    assert (refused.status_code, refused.json()) == (404, NOT_FOUND)
    assert state(client, task["id"]) == before
    assert log_work(client, task["id"], 30, "bob").status_code == 200
    assert_recorded_once(client, task["id"], [("bob", 30)])


@pytest.mark.parametrize("actor", ["admin", "alice"])
def test_work_on_a_missing_task_is_404_and_writes_nothing(client, actor):
    task = create(client, "alice")
    before = state(client, task["id"])
    response = log_work(client, task["id"] + 1, 30, actor)
    assert (response.status_code, response.json()) == (404, NOT_FOUND)
    assert state(client, task["id"]) == before
