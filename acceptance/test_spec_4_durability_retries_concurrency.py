"""Acceptance tests for SPEC.md section 4: durability, retries and concurrency.

Written from SPEC.md, TASK.md, OPEN-ISSUES.md and README.md alone, without the
application's code. Each test runs the documented entry point
workflow.api:create_app(db_path) on its own temporary SQLite file, with the
fixture tokens of README.md and synthetic data only. A restart is closing the
application and creating it again on the same file. Simultaneous requests are
sent from threads released together by a barrier.
"""

import threading
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


def auth(actor):
    return {"Authorization": f"Bearer {TOKENS[actor]}"}


@contextmanager
def running_app(db_path):
    with TestClient(create_app(db_path=db_path), raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "workflow.sqlite3")


@pytest.fixture
def client(db_path):
    with running_app(db_path) as test_client:
        yield test_client


def run_together(count, action):
    """Run action(0) … action(count - 1) on separate threads released at the same moment."""
    barrier = threading.Barrier(count)
    results = [None] * count
    failures = []

    def worker(index):
        try:
            barrier.wait(timeout=30)
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


def member_id(client, name):
    response = client.get("/users", headers=auth("admin"))
    assert response.status_code == 200, response.text
    body = response.json()
    # SPEC.md fixes the directory's fields, not its envelope: a list or an items list.
    entries = body if isinstance(body, list) else body.get("items", body.get("users"))
    return next(e["id"] for e in entries if e["role"] == "member" and name in str(e["name"]).lower())


def create_task(client, actor="alice", **fields):
    response = client.post("/tasks", json={"title": "Synthetic task", **fields}, headers=auth(actor))
    assert response.status_code == 201, response.text
    return response.json()


def post_with_key(client, actor, key, body):
    return client.post("/tasks", json=body, headers={**auth(actor), "Idempotency-Key": key})


def get_task(client, task_id):
    response = client.get(f"/tasks/{task_id}", headers=auth("admin"))
    assert response.status_code == 200, response.text
    return response.json()


def set_status(client, task_id, status, actor="alice"):
    response = client.patch(f"/tasks/{task_id}", json={"status": status}, headers=auth(actor))
    assert response.status_code == 200, response.text
    return response.json()


def all_tasks(client):
    response = client.get("/tasks", params={"limit": 100}, headers=auth("admin"))
    assert response.status_code == 200, response.text
    body = response.json()
    return body["items"], body["total"]


def task_total(client):
    return all_tasks(client)[1]


def log_work(client, task_id, minutes, actor="alice"):
    return client.post(f"/tasks/{task_id}/work", json={"minutes": minutes}, headers=auth(actor))


def work_items(client, task_id):
    response = client.get(f"/tasks/{task_id}/work", headers=auth("admin"))
    assert response.status_code == 200, response.text
    return response.json()["items"]


def assert_work(client, task_id, expected_minutes):
    """Each expected entry is recorded once and work_minutes is their sum."""
    items = work_items(client, task_id)
    assert sorted(item["minutes"] for item in items) == sorted(expected_minutes), items
    assert get_task(client, task_id)["work_minutes"] == sum(expected_minutes)


# --- durability ------------------------------------------------------------------------


def test_spec_4_acknowledged_task_survives_restart(db_path):
    """SPEC.md section 4: an acknowledged task survives closing and recreating the application."""
    with running_app(db_path) as client:
        created = create_task(
            client,
            title="Durable — 東京",
            description="Survives a restart",
            priority=5,
            assignee_id=member_id(client, "bob"),
            due_at="2026-05-01T08:00:00+02:00",
        )
        set_status(client, created["id"], "in_progress")
        before = get_task(client, created["id"])
    with running_app(db_path) as client:
        assert get_task(client, created["id"]) == before
        assert [item["id"] for item in all_tasks(client)[0]] == [created["id"]]


def test_spec_4_acknowledged_work_log_survives_restart(db_path):
    """SPEC.md section 4: acknowledged work logs survive closing and recreating the application."""
    with running_app(db_path) as client:
        task = create_task(client, title="Logged before restart")
        for minutes, actor in [(30, "alice"), (45, "admin")]:
            assert log_work(client, task["id"], minutes, actor).status_code == 200
        before = work_items(client, task["id"])
    with running_app(db_path) as client:
        assert work_items(client, task["id"]) == before
        assert get_task(client, task["id"])["work_minutes"] == 75


def test_spec_4_work_minutes_equals_sum_of_work_entries(client):
    """SPEC.md section 4: the task's work_minutes equals the sum of its work entries."""
    task = create_task(client, title="Summed")
    assert get_task(client, task["id"])["work_minutes"] == 0
    entries = [30, 1, 480, 17]
    for minutes in entries:
        assert log_work(client, task["id"], minutes).status_code == 200
    assert_work(client, task["id"], entries)


def test_spec_4_simultaneous_work_entries_are_each_recorded_once(db_path):
    """SPEC.md section 4: simultaneous accepted work entries are each recorded once and summed."""
    minutes = list(range(1, 17))
    with running_app(db_path) as client:
        task = create_task(client, title="Busy task")
        responses = run_together(
            len(minutes),
            lambda index: log_work(client, task["id"], minutes[index], "admin" if index % 2 else "alice"),
        )
        assert [response.status_code for response in responses] == [200] * len(minutes)
        assert_work(client, task["id"], minutes)
    with running_app(db_path) as client:
        assert_work(client, task["id"], minutes)


REJECTED_WORK = {
    "minutes-0": ("alice", {"minutes": 0}, 422),
    "minutes-481": ("alice", {"minutes": 481}, 422),
    "minutes-as-string": ("alice", {"minutes": "15"}, 422),
    "minutes-as-float": ("alice", {"minutes": 15.0}, 422),
    "done-task": ("alice", {"minutes": 15}, 409),
    "observer": ("observer", {"minutes": 15}, 403),
    "unrelated-member": ("bob", {"minutes": 15}, 404),
}


@pytest.mark.parametrize("case", sorted(REJECTED_WORK))
def test_spec_4_rejected_work_request_has_no_work_effect(client, case):
    """SPEC.md section 4: a rejected work request records nothing and leaves work_minutes unchanged."""
    actor, body, expected = REJECTED_WORK[case]
    task = create_task(client, "alice", title="Already logged")
    assert log_work(client, task["id"], 10).status_code == 200
    if case == "done-task":
        set_status(client, task["id"], "in_progress")
        set_status(client, task["id"], "done")
    before = work_items(client, task["id"])
    response = client.post(f"/tasks/{task['id']}/work", json=body, headers=auth(actor))
    assert response.status_code == expected, response.text
    assert work_items(client, task["id"]) == before
    assert get_task(client, task["id"])["work_minutes"] == 10


# --- idempotent creation ---------------------------------------------------------------


def test_spec_4_idempotent_retry_returns_the_same_task(client):
    """SPEC.md section 4: the same body with the same actor/key returns 201 and the same task ID."""
    body = {"title": "Pay the synthetic invoice", "priority": 4}
    first = post_with_key(client, "alice", "invoice-1", body)
    second = post_with_key(client, "alice", "invoice-1", body)
    assert (first.status_code, second.status_code) == (201, 201), (first.text, second.text)
    assert second.json()["id"] == first.json()["id"]
    assert task_total(client) == 1


def test_spec_4_idempotent_retry_after_restart_returns_the_same_task(db_path):
    """SPEC.md section 4: an idempotent retry after an application restart returns the same task."""
    body = {"title": "Order synthetic paper", "description": "Two boxes"}
    with running_app(db_path) as client:
        first = post_with_key(client, "alice", "paper-order", body)
        assert first.status_code == 201, first.text
    with running_app(db_path) as client:
        second = post_with_key(client, "alice", "paper-order", body)
        assert second.status_code == 201, second.text
        assert second.json()["id"] == first.json()["id"]
        assert task_total(client) == 1


def test_spec_4_idempotent_retry_compares_the_normalized_body(client):
    """SPEC.md section 4: the same normalized body, reordered and reformatted, is the same request."""
    headers = {**auth("alice"), "Idempotency-Key": "format-key", "Content-Type": "application/json"}
    first = client.post("/tasks", content='{"title":"Reformatted","priority":4}', headers=headers)
    second = client.post("/tasks", content='{\n  "priority": 4,\n  "title": "Reformatted"\n}', headers=headers)
    assert (first.status_code, second.status_code) == (201, 201), (first.text, second.text)
    assert second.json()["id"] == first.json()["id"]
    assert task_total(client) == 1


def test_spec_4_idempotency_key_with_a_different_body_returns_409(client):
    """SPEC.md section 4: a different body with the same actor/key returns 409 and creates nothing."""
    first = post_with_key(client, "alice", "contested", {"title": "Original request"})
    assert first.status_code == 201, first.text
    before = get_task(client, first.json()["id"])
    second = post_with_key(client, "alice", "contested", {"title": "Different request"})
    assert second.status_code == 409, second.text
    assert task_total(client) == 1
    assert get_task(client, first.json()["id"]) == before


def test_spec_4_retry_after_a_conflict_still_returns_the_original_task(client):
    """SPEC.md section 4: after a 409 conflict the original body with that key still returns its task."""
    body = {"title": "Original request"}
    first = post_with_key(client, "alice", "retried", body)
    assert post_with_key(client, "alice", "retried", {"title": "Different"}).status_code == 409
    again = post_with_key(client, "alice", "retried", body)
    assert again.status_code == 201, again.text
    assert again.json()["id"] == first.json()["id"]
    assert task_total(client) == 1


@pytest.mark.parametrize("bob_body", ["same", "different"])
def test_spec_4_idempotency_key_is_scoped_to_the_actor(client, bob_body):
    """SPEC.md section 4: the same key string used by a different actor is a separate key."""
    alice_body = {"title": "Alice's request"}
    body = alice_body if bob_body == "same" else {"title": "Bob's request"}
    alice = post_with_key(client, "alice", "shared-key", alice_body)
    bob = post_with_key(client, "bob", "shared-key", body)
    assert (alice.status_code, bob.status_code) == (201, 201), (alice.text, bob.text)
    assert bob.json()["id"] != alice.json()["id"]
    assert bob.json()["creator_id"] != alice.json()["creator_id"]
    assert task_total(client) == 2


@pytest.mark.parametrize("key", ["k", "k" * 128], ids=["1-char", "128-chars"])
def test_spec_4_idempotency_key_of_1_to_128_characters_is_accepted(client, key):
    """SPEC.md section 4: Idempotency-Key is 1–128 characters; both limits are accepted."""
    body = {"title": "Keyed request"}
    first = post_with_key(client, "alice", key, body)
    second = post_with_key(client, "alice", key, body)
    assert (first.status_code, second.status_code) == (201, 201), (first.text, second.text)
    assert second.json()["id"] == first.json()["id"]
    assert task_total(client) == 1


@pytest.mark.parametrize("key", ["", "   ", "k" * 129], ids=["empty", "blank", "129-chars"])
def test_spec_4_invalid_idempotency_key_is_rejected(client, key):
    """SPEC.md sections 4 and 5: a blank or over-long Idempotency-Key is invalid input, 422, and creates nothing."""
    response = post_with_key(client, "alice", key, {"title": "Badly keyed"})
    assert response.status_code == 422, response.text
    assert task_total(client) == 0


def test_spec_4_concurrent_idempotent_retries_create_one_task(client):
    """SPEC.md section 4: concurrent retries with the same actor/key/body create one task."""
    body = {"title": "Concurrent request", "priority": 2}
    responses = run_together(8, lambda index: post_with_key(client, "alice", "concurrent-key", body))
    assert [response.status_code for response in responses] == [201] * 8
    assert len({response.json()["id"] for response in responses}) == 1
    assert task_total(client) == 1


def test_spec_4_concurrent_conflicting_bodies_create_one_task(client):
    """SPEC.md section 4: concurrent different bodies with one actor/key: one 201, every other 409."""
    responses = run_together(
        8, lambda index: post_with_key(client, "alice", "contested-key", {"title": f"Variant {index}"})
    )
    assert sorted(response.status_code for response in responses) == [201] + [409] * 7
    winner = next(response for response in responses if response.status_code == 201).json()
    items, total = all_tasks(client)
    assert total == 1
    assert (items[0]["id"], items[0]["title"]) == (winner["id"], winner["title"])
