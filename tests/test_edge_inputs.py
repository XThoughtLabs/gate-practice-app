"""Edge inputs (SPEC.md sections 1, 2, 3 and 5): a 404 or a 422, never a 500, and nothing written.

A task ID that SQLite cannot hold, outside the signed 64-bit range, names no task: every
task route answers it with the uniform 404. q has no length limit, so a substring as long
as a 2,000-character description finds its task. An aware timestamp whose UTC value falls
outside the years 1 to 9999 is invalid input, 422. A refused request writes no task, work
entry or status-history event.
"""

from contextlib import closing
import sqlite3

import pytest
from fastapi.testclient import TestClient

from workflow.api import create_app
from workflow.store import Store


HEADERS = {name: {"Authorization": f"Bearer demo-{name}"} for name in ("admin", "alice", "bob", "observer")}
NOT_FOUND = {"detail": "task not found"}

# The ends of SQLite's signed 64-bit integers and the first values past them.
IDS = {"max": 2**63 - 1, "above-max": 2**63, "min": -2**63, "below-min": -2**63 - 1}
OUT_OF_RANGE_IDS = {name: IDS[name] for name in ("above-max", "below-min")}

# Aware timestamps whose UTC value falls just outside the years 1 to 9999.
OUT_OF_RANGE_TIMES = {"above-9999": "9999-12-31T23:59:59-01:00", "below-0001": "0001-01-01T00:00:00+01:00"}

ROUTES = {
    "get-task": ("GET", "/tasks/{}", None),
    "patch-task": ("PATCH", "/tasks/{}", {"title": "Renamed", "status": "in_progress"}),
    "get-history": ("GET", "/tasks/{}/history", None),
    "get-work": ("GET", "/tasks/{}/work", None),
    "post-work": ("POST", "/tasks/{}/work", {"minutes": 30}),
}

SNAPSHOT = {
    "tasks": "SELECT * FROM tasks ORDER BY id",
    "work_logs": "SELECT * FROM work_logs ORDER BY id",
    "status_history": "SELECT * FROM status_history ORDER BY id",
}

# 2,000 characters in which every substring of 201 or more characters occurs once.
DESCRIPTION = " ".join(f"Word{n}" for n in range(400))[:2000]


@pytest.fixture
def path(tmp_path):
    return tmp_path / "edge.sqlite3"


@pytest.fixture
def client(path):
    # A server error comes back as a 500 response for the test to assert against,
    # not as an exception raised inside the test client.
    with TestClient(create_app(path), raise_server_exceptions=False) as result:
        yield result


@pytest.fixture
def task(client):
    """Alice's todo task, assigned to her, with a due date and one work entry."""
    body = {"title": "Edge inputs", "assignee_id": 2, "due_at": "2026-03-01T10:00:00Z"}
    response = client.post("/tasks", json=body, headers=HEADERS["alice"])
    assert response.status_code == 201, response.text
    logged = client.post(f"/tasks/{response.json()['id']}/work", json={"minutes": 30}, headers=HEADERS["alice"])
    assert logged.status_code == 200, logged.text
    return logged.json()


def stored(path):
    """Every row of the tasks, work entries and status-history events in the file."""
    with closing(sqlite3.connect(path)) as conn:
        return {table: conn.execute(query).fetchall() for table, query in SNAPSHOT.items()}


def search(client, actor, q):
    response = client.get("/tasks", params={"q": q, "limit": 100}, headers=HEADERS[actor])
    assert response.status_code == 200, response.text
    body = response.json()
    return [row["id"] for row in body["items"]], body["total"]


# --- task IDs SQLite cannot hold --------------------------------------------------------

@pytest.mark.parametrize("task_id", list(IDS.values()), ids=list(IDS))
@pytest.mark.parametrize("route", list(ROUTES.values()), ids=list(ROUTES))
@pytest.mark.parametrize("actor", ["admin", "alice"])
def test_task_id_at_or_beyond_64_bits_is_not_found(client, path, task, actor, route, task_id):
    method, template, body = route
    before = stored(path)
    response = client.request(method, template.format(task_id), json=body, headers=HEADERS[actor])
    assert response.status_code == 404, response.text
    assert response.json() == NOT_FOUND
    assert stored(path) == before


@pytest.mark.parametrize("task_id", list(OUT_OF_RANGE_IDS.values()), ids=list(OUT_OF_RANGE_IDS))
def test_store_answers_an_id_beyond_64_bits_as_missing(path, client, task, task_id):
    store = Store(path)
    before = stored(path)
    assert store.task(task_id) is None
    assert store.update(task_id, {"title": "Renamed", "status": "in_progress"}, "2026-01-01T00:00:00+00:00", 2) is None
    assert store.append_work(task_id, store.user("demo-alice"), 30, "2026-01-01T00:00:00+00:00") is None
    assert store.history(task_id) == []
    assert store.work_logs(task_id) == []
    assert stored(path) == before


# --- q longer than 200 characters ------------------------------------------------------

@pytest.mark.parametrize("length", [201, 2000])
@pytest.mark.parametrize("actor", ["admin", "alice"])
def test_long_q_finds_the_task_whose_description_holds_it(client, actor, length):
    assert len(DESCRIPTION) == 2000
    created = client.post("/tasks", json={"title": "Long description", "description": DESCRIPTION},
                          headers=HEADERS["alice"])
    assert created.status_code == 201, created.text
    # Differs from DESCRIPTION in its last character only, so neither q is in it.
    decoy = client.post("/tasks", json={"title": "Decoy", "description": DESCRIPTION[:-1] + "#"},
                        headers=HEADERS["alice"])
    assert decoy.status_code == 201, decoy.text
    q = DESCRIPTION[-length:]
    assert search(client, actor, q) == ([created.json()["id"]], 1)
    assert search(client, actor, q.upper()) == ([created.json()["id"]], 1)


def test_q_longer_than_every_description_finds_nothing(client, task):
    assert search(client, "admin", DESCRIPTION + "!") == ([], 0)


# --- timestamps whose UTC value is outside the years 1 to 9999 --------------------------

@pytest.mark.parametrize("due_at", list(OUT_OF_RANGE_TIMES.values()), ids=list(OUT_OF_RANGE_TIMES))
def test_create_with_due_at_outside_utc_years_is_refused(client, path, task, due_at):
    before = stored(path)
    response = client.post("/tasks", json={"title": "Out of range", "due_at": due_at}, headers=HEADERS["alice"])
    assert response.status_code == 422, response.text
    assert stored(path) == before


@pytest.mark.parametrize("due_at", list(OUT_OF_RANGE_TIMES.values()), ids=list(OUT_OF_RANGE_TIMES))
@pytest.mark.parametrize("body", [{}, {"title": "Renamed", "status": "in_progress"}], ids=["alone", "with-status"])
def test_patch_with_due_at_outside_utc_years_is_refused(client, path, task, body, due_at):
    before = stored(path)
    response = client.patch(f"/tasks/{task['id']}", json={**body, "due_at": due_at}, headers=HEADERS["alice"])
    assert response.status_code == 422, response.text
    assert stored(path) == before


@pytest.mark.parametrize("at", list(OUT_OF_RANGE_TIMES.values()), ids=list(OUT_OF_RANGE_TIMES))
@pytest.mark.parametrize("actor", ["admin", "alice", "observer"])
def test_overdue_at_outside_utc_years_is_refused(client, path, task, actor, at):
    before = stored(path)
    response = client.get("/tasks/overdue", params={"at": at}, headers=HEADERS[actor])
    assert response.status_code == 422, response.text
    assert stored(path) == before


@pytest.mark.parametrize(("value", "utc"), [
    ("9999-12-31T23:59:59Z", "9999-12-31T23:59:59.000000+00:00"),
    ("9999-12-31T22:59:59-01:00", "9999-12-31T23:59:59.000000+00:00"),
    ("0001-01-01T00:00:00Z", "0001-01-01T00:00:00.000000+00:00"),
    ("0001-01-01T01:00:00+01:00", "0001-01-01T00:00:00.000000+00:00"),
], ids=["last-second-z", "last-second-minus-0100", "first-second-z", "first-second-plus-0100"])
def test_timestamps_at_the_ends_of_utc_years_are_accepted(client, task, value, utc):
    created = client.post("/tasks", json={"title": "Edge due", "due_at": value}, headers=HEADERS["alice"])
    assert (created.status_code, created.json()["due_at"]) == (201, utc), created.text
    patched = client.patch(f"/tasks/{task['id']}", json={"due_at": value}, headers=HEADERS["alice"])
    assert (patched.status_code, patched.json()["due_at"]) == (200, utc), patched.text
    response = client.get("/tasks/overdue", params={"at": value}, headers=HEADERS["alice"])
    assert response.status_code == 200, response.text
    # At the last second both tasks are due exactly then, at the first one: neither is earlier.
    assert response.json()["items"] == []
