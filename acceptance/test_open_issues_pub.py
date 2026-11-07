"""Acceptance tests for the disclosed defects PUB-01, PUB-02 and PUB-03 of OPEN-ISSUES.md.

Written from SPEC.md, TASK.md, OPEN-ISSUES.md and README.md alone, without the
application's code. Each test runs the documented entry point
workflow.api:create_app(db_path) on its own temporary SQLite file, with the
fixture tokens of README.md and synthetic data only.
"""

import csv
import io
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
HEADER = ["id", "title", "status", "assignee_id"]


def auth(actor):
    return {"Authorization": f"Bearer {TOKENS[actor]}"}


@contextmanager
def running_app(db_path):
    with TestClient(create_app(db_path=db_path), raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def client(tmp_path):
    with running_app(str(tmp_path / "workflow.sqlite3")) as test_client:
        yield test_client


def create_task(client, actor="alice", **fields):
    response = client.post("/tasks", json={"title": "Synthetic task", **fields}, headers=auth(actor))
    assert response.status_code == 201, response.text
    return response.json()


def page(client, actor="alice", **params):
    response = client.get("/tasks", params=params, headers=auth(actor))
    assert response.status_code == 200, response.text
    body = response.json()
    return [item["id"] for item in body["items"]], body["total"]


def export_rows(client, actor="admin"):
    response = client.get("/tasks/export", headers=auth(actor))
    assert response.status_code == 200, response.text
    # A UTF-8 byte-order mark is tolerated; SPEC.md says only "UTF-8 CSV".
    return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"), newline="")))


def users(client):
    response = client.get("/users", headers=auth("admin"))
    assert response.status_code == 200, response.text
    body = response.json()
    # SPEC.md fixes the directory's fields, not its envelope: a list or an items list.
    return body if isinstance(body, list) else body.get("items", body.get("users"))


def admin_view(client):
    response = client.get("/tasks", params={"limit": 100}, headers=auth("admin"))
    assert response.status_code == 200, response.text
    return response.json()


# --- PUB-01: the last page can lose a task ---------------------------------------------


def test_pub_01_last_page_keeps_the_remaining_task(client):
    """PUB-01 (SPEC.md section 3): with three tasks, limit=2&offset=2 returns the third; total stays 3."""
    created = sorted(create_task(client, "alice", title=f"Alice task {number}")["id"] for number in (1, 2, 3))
    assert page(client, "alice", limit=2, offset=2) == ([created[2]], 3)


PAGING_BOUNDARIES = [
    # (tasks, limit, offset, positions of the expected tasks)
    (0, 2, 0, []),
    (0, 2, 2, []),
    (1, 2, 0, [0]),
    (1, 1, 0, [0]),
    (1, 1, 1, []),
    (2, 2, 0, [0, 1]),
    (3, 3, 0, [0, 1, 2]),
    (3, 2, 0, [0, 1]),
    (3, 2, 1, [1, 2]),
    (3, 1, 2, [2]),
    (3, 2, 3, []),
    (3, 2, 10, []),
    (4, 2, 2, [2, 3]),
    (4, 2, 4, []),
    (5, 2, 4, [4]),
]


@pytest.mark.parametrize(
    ("count", "limit", "offset", "positions"),
    PAGING_BOUNDARIES,
    ids=[f"tasks-{count}-limit-{limit}-offset-{offset}" for count, limit, offset, _ in PAGING_BOUNDARIES],
)
def test_pub_01_paging_boundaries_keep_every_remaining_task(client, count, limit, offset, positions):
    """PUB-01 (SPEC.md section 3): empty, one-item, exact-page and partial last pages hold every
    remaining task, and total is the whole collection."""
    created = sorted(create_task(client, "alice", title=f"Paged task {number}")["id"] for number in range(count))
    assert page(client, "alice", limit=limit, offset=offset) == ([created[p] for p in positions], count)


def test_pub_01_last_page_of_a_search_keeps_the_remaining_match(client):
    """PUB-01 (SPEC.md section 3): a partial final page of a search retains every remaining match."""
    titles = ["Match one", "Other", "Match two", "Match three", "Other again"]
    created = [create_task(client, "alice", title=title)["id"] for title in titles]
    matches = sorted([created[0], created[2], created[3]])
    assert page(client, "alice", q="match", limit=2, offset=2) == ([matches[2]], 3)


# --- PUB-02: CSV export corrupts structured titles -------------------------------------


def test_pub_02_export_recovers_a_title_with_comma_and_quotes(client):
    """PUB-02 (SPEC.md section 3): a standard CSV parser recovers 'Review, phase "B"' in one title
    field, with exactly the documented columns."""
    title = 'Review, phase "B"'
    task = create_task(client, "alice", title=title)
    assert export_rows(client) == [HEADER, [str(task["id"]), title, "todo", ""]]


STRUCTURED_TITLES = [
    "Überprüfung, „Phase B“ — 東京 ✓ 🚀",
    "first line\nsecond line",
    'first line\r\nsecond, "quoted" line',
    '"Fully quoted"',
    "Trailing comma,",
    'Mixed: "a", b; c\td',
]


@pytest.mark.parametrize(
    "title", STRUCTURED_TITLES, ids=["unicode", "line-feed", "crlf-comma-quotes", "quoted", "comma", "mixed"]
)
def test_pub_02_export_recovers_unicode_and_line_breaks(client, title):
    """PUB-02 (SPEC.md section 3): Unicode, embedded line breaks, commas and quotes survive the export
    unchanged in one field; content is not stripped."""
    task = create_task(client, "alice", title=title)
    assert export_rows(client) == [HEADER, [str(task["id"]), title, "todo", ""]]


def test_pub_02_export_keeps_exact_columns_for_many_structured_titles(client):
    """PUB-02 (SPEC.md section 3): with many structured titles at once, every row has exactly the
    documented columns and its own title."""
    bob = next(
        entry["id"]
        for entry in users(client)
        if entry["role"] == "member" and "bob" in str(entry["name"]).lower()
    )
    expected = {}
    for number, title in enumerate(STRUCTURED_TITLES + ['Review, phase "B"']):
        assignee = bob if number % 2 else None
        task = create_task(client, "alice", title=title, assignee_id=assignee)
        expected[str(task["id"])] = [str(task["id"]), title, "todo", "" if assignee is None else str(bob)]
    rows = export_rows(client)
    assert rows[0] == HEADER
    assert all(len(row) == 4 for row in rows), rows
    assert {row[0]: row for row in rows[1:]} == expected
    assert len(rows) == len(expected) + 1


# --- PUB-03: a negative test may accept success ----------------------------------------


@pytest.mark.parametrize("key", [None, "observer-key"], ids=["without-key", "with-idempotency-key"])
def test_pub_03_observer_create_task_returns_403(client, key):
    """PUB-03 (SPEC.md sections 1, 3 and 5): an observer creating a task gets exactly 403; nothing else passes."""
    headers = auth("observer") if key is None else {**auth("observer"), "Idempotency-Key": key}
    response = client.post("/tasks", json={"title": "Observer's task"}, headers=headers)
    assert response.status_code == 403, response.text


def test_pub_03_observer_create_task_creates_nothing(client):
    """PUB-03 (SPEC.md section 1): observers never write; a refused creation leaves no task behind."""
    body = {"title": "Observer's task", "description": "Should not exist", "priority": 5}
    response = client.post("/tasks", json=body, headers=auth("observer"))
    assert response.status_code == 403, response.text
    view = admin_view(client)
    assert (view["items"], view["total"]) == ([], 0)
