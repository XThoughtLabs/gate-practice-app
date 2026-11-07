"""Acceptance tests for SPEC.md section 6.1: status history.

Written from SPEC.md, TASK.md, OPEN-ISSUES.md and README.md alone, without the
application's code. Each test runs the documented entry point
workflow.api:create_app(db_path) on its own temporary SQLite file, with the
fixture tokens of README.md and synthetic data only. The upgrade of a
pre-upgrade database is tested in test_spec_4_6_1_upgrade_of_existing_database.py.
"""

import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

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
EVENT_FIELDS = {"sequence", "actor_id", "from_status", "to_status", "changed_at", "origin"}


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


def parse_utc(value):
    """Parse an ISO-8601 timestamp and require it to carry the UTC offset."""
    assert isinstance(value, str), value
    parsed = datetime.fromisoformat(value)
    assert parsed.utcoffset() == timedelta(0), value
    return parsed


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


def create_task(client, actor="alice", **fields):
    response = client.post("/tasks", json={"title": "Synthetic task", **fields}, headers=auth(actor))
    assert response.status_code == 201, response.text
    return response.json()


def get_task(client, task_id):
    response = client.get(f"/tasks/{task_id}", headers=auth("admin"))
    assert response.status_code == 200, response.text
    return response.json()


def patch_task(client, task_id, body, actor="alice"):
    return client.patch(f"/tasks/{task_id}", json=body, headers=auth(actor))


def set_status(client, task_id, status, actor="alice"):
    response = patch_task(client, task_id, {"status": status}, actor)
    assert response.status_code == 200, response.text
    return response.json()


def history(client, task_id, actor="admin"):
    response = client.get(f"/tasks/{task_id}/history", headers=auth(actor))
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, dict) and isinstance(body.get("items"), list), body
    return body["items"]


def assert_event(event, sequence, actor_id, from_status, to_status, origin="operation"):
    assert EVENT_FIELDS <= set(event), event
    assert event["sequence"] == sequence, event
    assert event["actor_id"] == actor_id, event
    assert event["from_status"] == from_status, event
    assert event["to_status"] == to_status, event
    assert event["origin"] == origin, event
    parse_utc(event["changed_at"])


# --- the history of a new task ---------------------------------------------------------


def test_spec_6_1_history_starts_with_creation_event(client, ids):
    """SPEC.md section 6.1: each new task has a creation event, sequence 1, from null to todo."""
    task = create_task(client, "alice", title="New task")
    events = history(client, task["id"])
    assert len(events) == 1, events
    assert_event(events[0], 1, ids["alice"], None, "todo")
    changed_at = parse_utc(events[0]["changed_at"])
    assert abs(datetime.now(timezone.utc) - changed_at) < timedelta(minutes=10), events


def test_spec_6_1_history_body_is_an_items_object(client):
    """SPEC.md section 6.1: GET /tasks/{id}/history returns {"items":[...]}."""
    task = create_task(client, title="Shaped")
    response = client.get(f"/tasks/{task['id']}/history", headers=auth("alice"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, dict) and "items" in body, body
    assert isinstance(body["items"], list), body


@pytest.mark.parametrize("actor", ["admin", "bob"])
def test_spec_6_1_creation_event_actor_is_the_creator(client, ids, actor):
    """SPEC.md section 6.1: the creation event's actor is the task's creator."""
    task = create_task(client, actor, title=f"Created by {actor}")
    events = history(client, task["id"])
    assert len(events) == 1, events
    assert_event(events[0], 1, ids[actor], None, "todo")


# --- transitions -----------------------------------------------------------------------


def test_spec_6_1_each_transition_appends_one_event(client, ids):
    """SPEC.md section 6.1: each successful transition appends exactly one event with its actor."""
    task = create_task(client, "alice", title="Travelling task", assignee_id=ids["bob"])
    set_status(client, task["id"], "in_progress", "alice")
    set_status(client, task["id"], "done", "bob")
    set_status(client, task["id"], "in_progress", "admin")
    events = history(client, task["id"])
    assert len(events) == 4, events
    assert_event(events[0], 1, ids["alice"], None, "todo")
    assert_event(events[1], 2, ids["alice"], "todo", "in_progress")
    assert_event(events[2], 3, ids["bob"], "in_progress", "done")
    assert_event(events[3], 4, ids["admin"], "done", "in_progress")


def test_spec_6_1_changed_at_is_aware_utc_and_follows_the_sequence(client):
    """SPEC.md section 6.1: changed_at is an aware UTC timestamp; events are ordered by sequence."""
    task = create_task(client, title="Timed")
    set_status(client, task["id"], "in_progress")
    set_status(client, task["id"], "done")
    events = history(client, task["id"])
    assert [event["sequence"] for event in events] == [1, 2, 3], events
    stamps = [parse_utc(event["changed_at"]) for event in events]
    assert stamps == sorted(stamps), events


def test_spec_6_1_sequence_is_counted_per_task(client):
    """SPEC.md section 6.1: sequence is per task and starts at 1, whatever other tasks do."""
    first = create_task(client, title="First")["id"]
    second = create_task(client, title="Second")["id"]
    set_status(client, first, "in_progress")
    set_status(client, second, "in_progress")
    set_status(client, second, "done")
    set_status(client, first, "done")
    third = create_task(client, title="Third")["id"]
    assert [event["sequence"] for event in history(client, first)] == [1, 2, 3]
    assert [event["sequence"] for event in history(client, second)] == [1, 2, 3]
    assert [event["sequence"] for event in history(client, third)] == [1]


def test_spec_6_1_status_change_with_other_fields_appends_one_event(client, ids):
    """SPEC.md section 6.1: a PATCH that changes the status and other fields appends one event."""
    task = create_task(client, title="Combined edit")
    response = patch_task(client, task["id"], {"status": "in_progress", "title": "Renamed", "priority": 1})
    assert response.status_code == 200, response.text
    events = history(client, task["id"])
    assert len(events) == 2, events
    assert_event(events[1], 2, ids["alice"], "todo", "in_progress")


# --- what does not create events -------------------------------------------------------


@pytest.mark.parametrize("status", ["todo", "in_progress"])
def test_spec_6_1_no_event_for_unchanged_status(client, status):
    """SPEC.md section 6.1: no event is created for an unchanged status."""
    task = create_task(client, title="Steady")
    if status == "in_progress":
        set_status(client, task["id"], "in_progress")
    before = history(client, task["id"])
    for body in ({"status": status}, {"status": status, "title": "Renamed while steady"}):
        response = patch_task(client, task["id"], body)
        assert response.status_code == 200, response.text
    assert history(client, task["id"]) == before


def test_spec_6_1_no_event_for_non_status_edits(client, ids):
    """SPEC.md section 6.1: no event is created for edits that do not change the status."""
    task = create_task(client, title="Edited")
    before = history(client, task["id"])
    for body in [
        {"title": "Edited again"},
        {"description": "New description"},
        {"priority": 5},
        {"assignee_id": ids["bob"]},
        {"due_at": "2026-09-01T12:00:00Z"},
        {"assignee_id": None, "due_at": None},
    ]:
        response = patch_task(client, task["id"], body)
        assert response.status_code == 200, (body, response.text)
    logged = client.post(f"/tasks/{task['id']}/work", json={"minutes": 30}, headers=auth("alice"))
    assert logged.status_code == 200, logged.text
    assert history(client, task["id"]) == before


REJECTED_PATCHES = {
    "skipped-transition": ("alice", {"status": "done"}, 409),
    "unknown-status": ("alice", {"status": "blocked"}, 422),
    "invalid-companion-field": ("alice", {"status": "in_progress", "priority": 9}, 422),
    "unknown-companion-field": ("alice", {"status": "in_progress", "colour": "red"}, 422),
    "observer": ("observer", {"status": "in_progress"}, 403),
    "unrelated-member": ("bob", {"status": "in_progress"}, 404),
}


@pytest.mark.parametrize("case", sorted(REJECTED_PATCHES))
def test_spec_6_1_no_event_for_rejected_requests(client, case):
    """SPEC.md section 6.1: a rejected request creates no event and leaves the status unchanged."""
    actor, body, expected = REJECTED_PATCHES[case]
    task = create_task(client, "alice", title="Guarded")
    before = history(client, task["id"])
    response = patch_task(client, task["id"], body, actor)
    assert response.status_code == expected, response.text
    assert history(client, task["id"]) == before
    assert get_task(client, task["id"])["status"] == "todo"


def test_spec_6_1_no_event_for_a_rejected_reopen(client):
    """SPEC.md sections 2 and 6.1: a member's refused reopen of a done task creates no event.
    Its status code is checked in test_spec_2_member_cannot_reopen_done_task; here only the refusal."""
    task = create_task(client, "alice", title="Closed")
    set_status(client, task["id"], "in_progress")
    set_status(client, task["id"], "done")
    before = history(client, task["id"])
    response = patch_task(client, task["id"], {"status": "in_progress"}, "alice")
    assert response.status_code in (403, 409), response.text
    assert history(client, task["id"]) == before
    assert len(before) == 3, before


def test_spec_6_1_no_event_for_an_idempotent_creation_retry(client, ids):
    """SPEC.md section 6.1: an idempotent creation retry creates no event."""
    headers = {**auth("alice"), "Idempotency-Key": "history-retry"}
    first = client.post("/tasks", json={"title": "Retried"}, headers=headers)
    second = client.post("/tasks", json={"title": "Retried"}, headers=headers)
    assert (first.status_code, second.status_code) == (201, 201), (first.text, second.text)
    assert second.json()["id"] == first.json()["id"]
    events = history(client, first.json()["id"])
    assert len(events) == 1, events
    assert_event(events[0], 1, ids["alice"], None, "todo")


# --- reading -------------------------------------------------------------------------


@pytest.mark.parametrize("actor", ["admin", "observer", "alice", "bob"], ids=["admin", "observer", "creator", "assignee"])
def test_spec_6_1_history_is_readable_by_task_readers(client, ids, actor):
    """SPEC.md section 6.1: history uses the same read permissions as the task."""
    task = create_task(client, "alice", title="Readable history", assignee_id=ids["bob"])
    set_status(client, task["id"], "in_progress")
    assert history(client, task["id"], actor) == history(client, task["id"], "admin")
    assert len(history(client, task["id"], actor)) == 2


def test_spec_6_1_history_of_former_assignee_is_hidden(client, ids):
    """SPEC.md sections 1 and 6.1: a member no longer assigned cannot read the history; uniform 404."""
    task = create_task(client, "admin", title="Moved on", assignee_id=ids["bob"])
    assert patch_task(client, task["id"], {"assignee_id": ids["alice"]}, "admin").status_code == 200
    response = client.get(f"/tasks/{task['id']}/history", headers=auth("bob"))
    assert response.status_code == 404
    assert response.json() == NOT_FOUND


@pytest.mark.parametrize("actor", ["admin", "alice", "observer"])
def test_spec_6_1_history_of_missing_task_returns_404(client, actor):
    """SPEC.md sections 1 and 6.1: the history of a missing task returns 404 with {"detail":"task not found"}."""
    response = client.get(f"/tasks/{MISSING_TASK_ID}/history", headers=auth(actor))
    assert response.status_code == 404
    assert response.json() == NOT_FOUND


# --- permanence ----------------------------------------------------------------------


def test_spec_6_1_history_survives_restart(db_path):
    """SPEC.md section 6.1: history survives closing and recreating the application."""
    with running_app(db_path) as client:
        task = create_task(client, title="Remembered")
        set_status(client, task["id"], "in_progress")
        set_status(client, task["id"], "done")
        before = history(client, task["id"])
    with running_app(db_path) as client:
        assert history(client, task["id"]) == before
    assert len(before) == 3, before


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_spec_6_1_history_is_not_editable_through_the_api(client, ids, method):
    """SPEC.md section 6.1: history is not editable through the API; the attempt is refused and changes nothing."""
    task = create_task(client, title="Fixed history")
    set_status(client, task["id"], "in_progress")
    before = history(client, task["id"])
    forged = {
        "sequence": 1,
        "actor_id": ids["bob"],
        "from_status": None,
        "to_status": "done",
        "changed_at": "2026-01-01T00:00:00Z",
        "origin": "operation",
    }
    body = None if method == "DELETE" else {"items": [forged]}
    for actor in ("admin", "alice"):
        response = client.request(method, f"/tasks/{task['id']}/history", json=body, headers=auth(actor))
        assert 400 <= response.status_code < 500, (actor, response.status_code, response.text)
    assert history(client, task["id"]) == before


def test_spec_6_1_task_patch_cannot_write_history(client):
    """SPEC.md sections 2 and 6.1: history is not a patchable field; the attempt returns 422."""
    task = create_task(client, title="No back door")
    before = history(client, task["id"])
    response = patch_task(client, task["id"], {"history": []}, "admin")
    assert response.status_code == 422, response.text
    assert history(client, task["id"]) == before


def test_spec_6_1_earlier_events_are_not_rewritten_by_later_changes(client, ids):
    """SPEC.md section 6.1: later changes append; they never rewrite earlier events."""
    task = create_task(client, "alice", title="Long life", assignee_id=ids["bob"])
    set_status(client, task["id"], "in_progress", "alice")
    earlier = history(client, task["id"])
    assert patch_task(client, task["id"], {"title": "Long life, renamed"}).status_code == 200
    assert patch_task(client, task["id"], {"assignee_id": ids["admin"]}).status_code == 200
    set_status(client, task["id"], "done", "admin")
    set_status(client, task["id"], "in_progress", "admin")
    later = history(client, task["id"])
    assert later[: len(earlier)] == earlier
    assert len(later) == len(earlier) + 2, later


def test_spec_6_1_concurrent_identical_transitions_append_one_event(client, ids):
    """SPEC.md section 6.1: the update and its event commit atomically; of simultaneous identical
    transitions only one is an actual transition, so exactly one event is appended."""
    task = create_task(client, "alice", title="Raced", assignee_id=ids["bob"])
    actors = ["alice", "bob", "admin", "alice", "bob", "admin", "alice", "bob"]
    responses = run_together(
        len(actors), lambda index: patch_task(client, task["id"], {"status": "in_progress"}, actors[index])
    )
    assert [response.status_code for response in responses] == [200] * len(actors)
    events = history(client, task["id"])
    assert [(event["from_status"], event["to_status"]) for event in events] == [
        (None, "todo"),
        ("todo", "in_progress"),
    ]
    assert get_task(client, task["id"])["status"] == "in_progress"
