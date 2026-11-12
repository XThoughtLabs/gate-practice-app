"""Acceptance tests for SPEC.md section 3: the existing endpoints.

Written from SPEC.md, TASK.md, OPEN-ISSUES.md and README.md alone, without the
application's code. Each test runs the documented entry point
workflow.api:create_app(db_path) on its own temporary SQLite file, with the
fixture tokens of README.md and synthetic data only.
"""

import csv
import io
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


def create_task(client, actor="alice", **fields):
    response = client.post("/tasks", json={"title": "Synthetic task", **fields}, headers=auth(actor))
    assert response.status_code == 201, response.text
    return response.json()


def get_task(client, task_id, actor="admin"):
    response = client.get(f"/tasks/{task_id}", headers=auth(actor))
    assert response.status_code == 200, response.text
    return response.json()


def set_status(client, task_id, status, actor="alice"):
    response = client.patch(f"/tasks/{task_id}", json={"status": status}, headers=auth(actor))
    assert response.status_code == 200, response.text
    return response.json()


def list_tasks(client, actor="admin", **params):
    response = client.get("/tasks", params=params, headers=auth(actor))
    assert response.status_code == 200, response.text
    return response.json()


def item_ids(body):
    return [item["id"] for item in body["items"]]


def search(client, q, actor="admin"):
    body = list_tasks(client, actor, q=q, limit=100)
    return item_ids(body), body["total"]


def overdue_ids(client, at, actor="admin"):
    response = client.get("/tasks/overdue", params={"at": at}, headers=auth(actor))
    assert response.status_code == 200, response.text
    body = response.json()
    # SPEC.md fixes the content of the overdue view, not its envelope.
    items = body["items"] if isinstance(body, dict) else body
    return [item["id"] for item in items]


def export_rows(client, actor="admin"):
    response = client.get("/tasks/export", headers=auth(actor))
    assert response.status_code == 200, response.text
    # A UTF-8 byte-order mark is tolerated; SPEC.md says only "UTF-8 CSV".
    return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"), newline="")))


def log_work(client, task_id, minutes, actor="alice"):
    return client.post(f"/tasks/{task_id}/work", json={"minutes": minutes}, headers=auth(actor))


def work_items(client, task_id, actor="admin"):
    response = client.get(f"/tasks/{task_id}/work", headers=auth(actor))
    assert response.status_code == 200, response.text
    return response.json()["items"]


# --- /health and /users ----------------------------------------------------------------


def test_spec_3_health_reports_ok_and_version(client):
    """SPEC.md section 3: GET /health returns 200 with status ok and a version."""
    response = client.get("/health")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body.get("version"), body


def test_spec_3_users_directory_lists_id_name_and_role(client):
    """SPEC.md section 3: GET /users is the ID/name/role directory of the fixture users."""
    response = client.get("/users", headers=auth("admin"))
    assert response.status_code == 200, response.text
    entries = directory_entries(response.json())
    for entry in entries:
        assert {"id", "name", "role"} <= set(entry), entry
        assert type(entry["id"]) is int, entry
    assert sorted(entry["role"] for entry in entries) == ["admin", "member", "member", "observer"]
    assert len({entry["id"] for entry in entries}) == 4


# --- POST /tasks, GET /tasks/{id}, PATCH /tasks/{id} -----------------------------------


@pytest.mark.parametrize("actor", ["admin", "alice"])
def test_spec_3_create_returns_201_with_the_task(client, ids, actor):
    """SPEC.md section 3: an admin or member creates a task from JSON fields; 201 with the task."""
    body = {
        "title": "Prepare report",
        "description": "Quarterly numbers",
        "priority": 4,
        "assignee_id": ids["bob"],
        "due_at": "2026-04-01T09:00:00Z",
    }
    response = client.post("/tasks", json=body, headers=auth(actor))
    assert response.status_code == 201, response.text
    for task in (response.json(), get_task(client, response.json()["id"])):
        for field in ("title", "description", "priority", "assignee_id"):
            assert task[field] == body[field], task
        assert parse_utc(task["due_at"]) == datetime(2026, 4, 1, 9, 0, tzinfo=timezone.utc)
        assert task["status"] == "todo"
        assert task["creator_id"] == ids[actor]


def test_spec_3_get_task_returns_the_stored_task(client, ids):
    """SPEC.md section 3: GET /tasks/{id} returns a visible task."""
    created = create_task(client, title="Readable", description="Body", priority=2, assignee_id=ids["bob"])
    for actor in ("alice", "bob", "admin", "observer"):
        task = get_task(client, created["id"], actor)
        assert task["id"] == created["id"]
        assert (task["title"], task["description"], task["priority"]) == ("Readable", "Body", 2)


def test_spec_3_patch_updates_only_the_given_field(client, ids):
    """SPEC.md section 3: PATCH updates the given subset of fields and returns 200 with the task."""
    created = create_task(client, title="Before", description="Kept", priority=2, assignee_id=ids["bob"])
    before = get_task(client, created["id"])
    response = client.patch(f"/tasks/{created['id']}", json={"title": "After"}, headers=auth("alice"))
    assert response.status_code == 200, response.text
    assert response.json()["title"] == "After"
    after = get_task(client, created["id"])
    assert after["title"] == "After"
    for field in ("id", "description", "priority", "assignee_id", "status", "due_at", "creator_id", "created_at"):
        assert after[field] == before[field], field


def test_spec_3_patch_accepts_every_documented_field(client, ids):
    """SPEC.md section 3: PATCH accepts title/description/assignee_id/status/priority/due_at together."""
    created = create_task(client, title="Before")
    body = {
        "title": "After",
        "description": "New description",
        "assignee_id": ids["bob"],
        "status": "in_progress",
        "priority": 5,
        "due_at": "2026-07-01T18:00:00+02:00",
    }
    response = client.patch(f"/tasks/{created['id']}", json=body, headers=auth("alice"))
    assert response.status_code == 200, response.text
    for task in (response.json(), get_task(client, created["id"])):
        for field in ("title", "description", "assignee_id", "status", "priority"):
            assert task[field] == body[field], task
        assert parse_utc(task["due_at"]) == datetime(2026, 7, 1, 16, 0, tzinfo=timezone.utc)


def test_spec_3_patch_of_missing_task_returns_404(client):
    """SPEC.md sections 1 and 3: PATCH of a missing task returns 404 with {"detail":"task not found"}."""
    response = client.patch(f"/tasks/{MISSING_TASK_ID}", json={"title": "Nobody"}, headers=auth("admin"))
    assert response.status_code == 404
    assert response.json() == NOT_FOUND


# --- GET /tasks ------------------------------------------------------------------------


def test_spec_3_list_defaults_to_limit_20_and_offset_0(client):
    """SPEC.md section 3: GET /tasks defaults to limit=20 and offset=0."""
    created = sorted(create_task(client, title=f"Task {number:02d}")["id"] for number in range(25))
    body = list_tasks(client)
    assert {"items", "total", "limit", "offset"} <= set(body), body
    assert (body["limit"], body["offset"], body["total"]) == (20, 0, 25)
    assert item_ids(body) == created[:20]


def test_spec_3_list_is_ordered_by_increasing_id(client):
    """SPEC.md section 3: the list is ordered by increasing ID, on every page."""
    created = [
        create_task(client, title=title, priority=priority)["id"]
        for title, priority in [("charlie", 1), ("alpha", 5), ("bravo", 3), ("delta", 2)]
    ]
    # Edit the first task so that an order by update time, title or priority would differ.
    edited = client.patch(f"/tasks/{created[0]}", json={"title": "zulu"}, headers=auth("alice"))
    assert edited.status_code == 200, edited.text
    assert item_ids(list_tasks(client)) == sorted(created)
    pages = item_ids(list_tasks(client, limit=2, offset=0)) + item_ids(list_tasks(client, limit=2, offset=2))
    assert pages == sorted(created)


def test_spec_3_list_echoes_limit_and_offset(client):
    """SPEC.md section 3: the list reports the limit and offset it used."""
    created = sorted(create_task(client, title=f"Task {number}")["id"] for number in range(12))
    body = list_tasks(client, limit=7, offset=3)
    assert (body["limit"], body["offset"], body["total"]) == (7, 3, 12)
    assert item_ids(body) == created[3:10]


@pytest.mark.parametrize("limit", [1, 100])
def test_spec_3_list_accepts_limits_1_and_100(client, limit):
    """SPEC.md section 3: limit is 1–100; both limits are accepted."""
    created = sorted(create_task(client, title=f"Task {number}")["id"] for number in range(3))
    body = list_tasks(client, limit=limit)
    assert body["limit"] == limit
    assert item_ids(body) == created[:limit]
    assert body["total"] == 3


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"limit": "abc"}, {"limit": "2.5"}, {"offset": "x"}],
    ids=["limit-0", "limit-101", "offset-minus-1", "limit-text", "limit-fraction", "offset-text"],
)
def test_spec_3_list_rejects_paging_outside_limits(client, params):
    """SPEC.md sections 3 and 5: limit outside 1–100 or offset below 0 is invalid input, 422."""
    create_task(client, title="Present")
    response = client.get("/tasks", params=params, headers=auth("admin"))
    assert response.status_code == 422, response.text


def test_spec_3_total_counts_every_match_before_paging(client):
    """SPEC.md section 3: total counts the complete matching collection before paging."""
    titles = ["Weekly report", "Lunch", "Monthly report", "Holiday", "Annual REPORT"]
    created = [create_task(client, title=title)["id"] for title in titles]
    matches = sorted([created[0], created[2], created[4]])
    first = list_tasks(client, q="report", limit=2, offset=0)
    assert (item_ids(first), first["total"]) == (matches[:2], 3)
    last = list_tasks(client, q="report", limit=2, offset=2)
    assert (item_ids(last), last["total"]) == (matches[2:], 3)


@pytest.mark.parametrize("q", ["report", "REPORT", "RePoRt"])
def test_spec_3_search_is_case_insensitive(client, q):
    """SPEC.md section 3: q is a case-insensitive substring of the title."""
    match = create_task(client, title="Quarterly Report")["id"]
    create_task(client, title="Quarterly summary")
    assert search(client, q) == ([match], 1)


def test_spec_3_search_matches_the_description(client):
    """SPEC.md section 3: q is a substring of the title or the description."""
    match = create_task(client, title="Plain title", description="find the NEEDLE here")["id"]
    create_task(client, title="Other title", description="only hay")
    assert search(client, "needle") == ([match], 1)


def test_spec_3_empty_search_returns_all_visible_tasks(client):
    """SPEC.md section 3: an empty q means all visible tasks."""
    created = sorted(create_task(client, title=title)["id"] for title in ["one", "two", "three"])
    assert search(client, "") == (created, 3)


WILDCARD_TITLES = {
    "percent": "100% complete",
    "digits": "1000 complete",
    "underscore": "snake_case name",
    "letter": "snakeXcase name",
    "backslash": "back\\slash path",
}


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("%", ["percent"]),
        ("0%", ["percent"]),
        ("%%", []),
        ("_", ["underscore"]),
        ("e_c", ["underscore"]),
        ("SNAKE_CASE", ["underscore"]),
        ("_x", []),
        ("\\", ["backslash"]),
    ],
    ids=["percent", "digit-percent", "double-percent", "underscore", "letter-underscore-letter",
         "upper-case-underscore", "underscore-x", "backslash"],
)
def test_spec_3_search_treats_like_wildcards_as_literal_characters(client, q, expected):
    """SPEC.md section 3: % and _ in q are literal characters, not search operators."""
    created = {name: create_task(client, title=title)["id"] for name, title in WILDCARD_TITLES.items()}
    wanted = sorted(created[name] for name in expected)
    assert search(client, q) == (wanted, len(wanted))


@pytest.mark.parametrize(
    ("q", "expected"),
    [("a b", ["spaced"]), (" beta", ["spaced"]), ("alphabeta", ["joined"])],
    ids=["inner-space", "leading-space", "no-space"],
)
def test_spec_3_search_is_a_literal_substring(client, q, expected):
    """SPEC.md section 3: q is a literal substring; its spaces are part of it."""
    created = {
        "spaced": create_task(client, title="alpha beta")["id"],
        "joined": create_task(client, title="alphabeta")["id"],
        "reversed": create_task(client, title="beta alpha")["id"],
    }
    wanted = sorted(created[name] for name in expected)
    assert search(client, q) == (wanted, len(wanted))


@pytest.mark.parametrize(
    "q",
    ["' OR '1'='1", "' OR 1=1 --", "%' OR '%'='", "x'; DROP TABLE tasks; --", '" OR ""="'],
    ids=["or-true", "or-comment", "wildcard-or", "drop-table", "double-quote-or"],
)
def test_spec_3_search_text_is_data_not_sql(client, q):
    """SPEC.md section 3: search text is data, not SQL; it matches nothing here and harms nothing."""
    created = sorted(create_task(client, title=title)["id"] for title in ["alpha", "beta", "gamma"])
    assert search(client, q) == ([], 0)
    assert search(client, "") == (created, 3)


# --- GET /tasks/overdue ----------------------------------------------------------------

AT = "2026-03-01T10:00:00Z"


def test_spec_3_overdue_needs_due_at_strictly_earlier_than_at(client):
    """SPEC.md section 3: overdue means due_at strictly earlier than at; equality is not overdue."""
    create_task(client, title="Due exactly at", due_at="2026-03-01T10:00:00Z")
    earlier = create_task(client, title="Due a second earlier", due_at="2026-03-01T09:59:59Z")["id"]
    create_task(client, title="Due a second later", due_at="2026-03-01T10:00:01Z")
    create_task(client, title="No due date")
    assert overdue_ids(client, AT) == [earlier]


def test_spec_3_overdue_excludes_done_tasks(client):
    """SPEC.md section 3: only unfinished tasks are overdue."""
    todo = create_task(client, title="Late, todo", due_at="2026-02-01T00:00:00Z")["id"]
    started = create_task(client, title="Late, in progress", due_at="2026-02-01T00:00:00Z")["id"]
    finished = create_task(client, title="Late, done", due_at="2026-02-01T00:00:00Z")["id"]
    set_status(client, started, "in_progress")
    set_status(client, finished, "in_progress")
    set_status(client, finished, "done")
    assert overdue_ids(client, AT) == sorted([todo, started])


def test_spec_3_overdue_compares_instants_across_offsets(client):
    """SPEC.md sections 2 and 3: due_at and at are compared as instants, whatever their offsets."""
    half_past = create_task(client, title="Due 10:30 UTC", due_at="2026-03-01T11:30:00+01:00")["id"]
    quarter_past = create_task(client, title="Due 10:15 UTC", due_at="2026-03-01T10:15:00Z")["id"]
    assert overdue_ids(client, "2026-03-01T12:30:00+02:00") == [quarter_past]
    assert overdue_ids(client, "2026-03-01T05:30:01-05:00") == sorted([half_past, quarter_past])


def test_spec_3_overdue_is_ordered_by_increasing_id(client):
    """SPEC.md section 3: overdue tasks are ordered by increasing ID."""
    created = [
        create_task(client, title=f"Late by {hours} h", due_at=f"2026-03-01T{9 - hours:02d}:00:00Z")["id"]
        for hours in range(4)
    ]
    assert overdue_ids(client, AT) == sorted(created)


@pytest.mark.parametrize(
    "at", ["2026-03-01T10:00:00", "2026-03-01", "yesterday"], ids=["naive", "date-only", "text"]
)
def test_spec_3_overdue_rejects_an_at_that_is_not_aware(client, at):
    """SPEC.md sections 2 and 3: at must be an aware timestamp; otherwise 422."""
    response = client.get("/tasks/overdue", params={"at": at}, headers=auth("admin"))
    assert response.status_code == 422, response.text


# --- GET /tasks/export -----------------------------------------------------------------


def test_spec_3_export_of_no_tasks_is_the_header_only(client):
    """SPEC.md section 3: the export has exactly the columns id,title,status,assignee_id."""
    assert export_rows(client) == [HEADER]


def test_spec_3_export_has_exact_columns_for_every_row(client, ids):
    """SPEC.md section 3: exact columns id,title,status,assignee_id, in that order, on every row."""
    create_task(client, title="One")
    create_task(client, title="Two", assignee_id=ids["bob"])
    rows = export_rows(client)
    assert rows[0] == HEADER
    assert len(rows) == 3
    assert all(len(row) == 4 for row in rows), rows


def test_spec_3_export_writes_null_assignee_as_empty_field(client, ids):
    """SPEC.md section 3: a null assignee is an empty field; an assignee is its ID."""
    unassigned = create_task(client, title="Nobody's")["id"]
    assigned = create_task(client, title="Bob's", assignee_id=ids["bob"])["id"]
    rows = {row[0]: row for row in export_rows(client)[1:]}
    assert rows[str(unassigned)] == [str(unassigned), "Nobody's", "todo", ""]
    assert rows[str(assigned)] == [str(assigned), "Bob's", "todo", str(ids["bob"])]


def test_spec_3_export_reports_each_status(client):
    """SPEC.md section 3: the status column holds each task's status."""
    todo = create_task(client, title="Waiting")["id"]
    started = create_task(client, title="Started")["id"]
    finished = create_task(client, title="Finished")["id"]
    set_status(client, started, "in_progress")
    set_status(client, finished, "in_progress")
    set_status(client, finished, "done")
    statuses = {row[0]: row[2] for row in export_rows(client)[1:]}
    assert statuses == {str(todo): "todo", str(started): "in_progress", str(finished): "done"}


def test_spec_3_export_is_not_paginated(client):
    """SPEC.md section 3: the export holds all visible tasks, with no pagination."""
    created = sorted(create_task(client, title=f"Bulk {number:03d}")["id"] for number in range(105))
    assert sorted(int(row[0]) for row in export_rows(client)[1:]) == created


def test_spec_3_export_is_utf8_csv(client):
    """SPEC.md section 3: the export is UTF-8 CSV, served as the CSV media type text/csv
    (the media type is read from "UTF-8 CSV"; SPEC.md names no header)."""
    title = "Überprüfung — 東京 ✓"
    create_task(client, title=title)
    response = client.get("/tasks/export", headers=auth("admin"))
    assert response.status_code == 200, response.text
    content_type = response.headers["content-type"].lower()
    assert content_type.split(";")[0].strip() == "text/csv", content_type
    if "charset=" in content_type:
        assert content_type.split("charset=")[1].split(";")[0].strip() in ("utf-8", "utf8"), content_type
    assert title.encode("utf-8") in response.content
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"), newline="")))
    assert rows[0] == HEADER
    assert rows[1][1] == title


# --- POST /tasks/{id}/work and GET /tasks/{id}/work ------------------------------------


def test_spec_3_work_entry_returns_the_updated_task(client):
    """SPEC.md section 3: POST /tasks/{id}/work returns 200 with the updated task."""
    task = create_task(client, title="Worked on")
    first = log_work(client, task["id"], 30)
    assert first.status_code == 200, first.text
    assert (first.json()["id"], first.json()["work_minutes"]) == (task["id"], 30)
    second = log_work(client, task["id"], 15)
    assert second.status_code == 200, second.text
    assert (second.json()["id"], second.json()["work_minutes"]) == (task["id"], 45)


@pytest.mark.parametrize("minutes", [1, 480])
def test_spec_3_work_minutes_1_and_480_are_accepted(client, minutes):
    """SPEC.md section 3: minutes is an integer 1–480; both limits are accepted."""
    task = create_task(client, title="Worked on")
    response = log_work(client, task["id"], minutes)
    assert response.status_code == 200, response.text
    assert response.json()["work_minutes"] == minutes


@pytest.mark.parametrize(
    "body",
    [
        {"minutes": 0},
        {"minutes": 481},
        {"minutes": -5},
        {"minutes": True},
        {"minutes": 30.0},
        {"minutes": 30.5},
        {"minutes": "30"},
        {"minutes": None},
        {},
    ],
    ids=["0", "481", "-5", "true", "30.0", "30.5", "string-30", "null", "missing"],
)
def test_spec_3_work_minutes_must_be_a_strict_integer_from_1_to_480(client, body):
    """SPEC.md section 3: minutes is a strict integer 1–480; anything else returns 422."""
    task = create_task(client, title="Worked on")
    response = client.post(f"/tasks/{task['id']}/work", json=body, headers=auth("alice"))
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("status", ["todo", "in_progress"])
def test_spec_3_work_is_accepted_on_unfinished_tasks(client, status):
    """SPEC.md section 3: work is accepted on a task that is not done."""
    task = create_task(client, title="Unfinished")
    if status == "in_progress":
        set_status(client, task["id"], "in_progress")
    response = log_work(client, task["id"], 20)
    assert response.status_code == 200, response.text
    assert response.json()["work_minutes"] == 20


def test_spec_3_work_on_done_task_returns_409(client):
    """SPEC.md section 3: work on a done task returns 409."""
    task = create_task(client, title="Finished")
    set_status(client, task["id"], "in_progress")
    set_status(client, task["id"], "done")
    response = log_work(client, task["id"], 20)
    assert response.status_code == 409, response.text


@pytest.mark.parametrize("actor", ["admin", "alice", "bob"], ids=["admin", "creator", "assignee"])
def test_spec_3_work_is_open_to_admin_and_members_who_see_the_task(client, ids, actor):
    """SPEC.md section 3: an admin, or a member with visibility of the task, may log work."""
    task = create_task(client, "alice", title="Shared", assignee_id=ids["bob"])
    response = log_work(client, task["id"], 20, actor)
    assert response.status_code == 200, response.text
    assert response.json()["work_minutes"] == 20


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_spec_3_work_of_missing_task_returns_404(client, method):
    """SPEC.md sections 1 and 3: the work endpoints of a missing task return a uniform 404."""
    body = {"minutes": 10} if method == "POST" else None
    response = client.request(method, f"/tasks/{MISSING_TASK_ID}/work", json=body, headers=auth("admin"))
    assert response.status_code == 404
    assert response.json() == NOT_FOUND


def test_spec_3_work_log_lists_entries_in_order(client, ids):
    """SPEC.md section 3: GET /tasks/{id}/work returns ordered items with actor_id, minutes, created_at."""
    task = create_task(client, "alice", title="Logged", assignee_id=ids["bob"])
    for actor, minutes in [("alice", 30), ("admin", 45), ("bob", 5)]:
        response = log_work(client, task["id"], minutes, actor)
        assert response.status_code == 200, response.text
    items = work_items(client, task["id"])
    assert [(item["actor_id"], item["minutes"]) for item in items] == [
        (ids["alice"], 30),
        (ids["admin"], 45),
        (ids["bob"], 5),
    ]
    stamps = [parse_utc(item["created_at"]) for item in items]
    assert stamps == sorted(stamps)


@pytest.mark.parametrize("actor", ["observer", "admin", "alice", "bob"])
def test_spec_3_work_log_is_readable_by_task_readers(client, ids, actor):
    """SPEC.md sections 1 and 3: the work log of a task is readable by everyone who may read the task."""
    task = create_task(client, "alice", title="Logged", assignee_id=ids["bob"])
    assert log_work(client, task["id"], 25).status_code == 200
    items = work_items(client, task["id"], actor)
    assert [(item["actor_id"], item["minutes"]) for item in items] == [(ids["alice"], 25)]
