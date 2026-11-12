"""Acceptance tests for SPEC.md section 2: task fields, validation and status transitions.

Written from SPEC.md, TASK.md, OPEN-ISSUES.md and README.md alone, without the
application's code. Each test runs the documented entry point
workflow.api:create_app(db_path) on its own temporary SQLite file, with the
fixture tokens of README.md and synthetic data only.
"""

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
MISSING_USER_ID = 999_999


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


def post_task(client, body, actor="alice"):
    return client.post("/tasks", json=body, headers=auth(actor))


def create_task(client, actor="alice", **fields):
    response = post_task(client, {"title": "Synthetic task", **fields}, actor)
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


def task_total(client):
    response = client.get("/tasks", headers=auth("admin"))
    assert response.status_code == 200, response.text
    return response.json()["total"]


@pytest.fixture
def task(client):
    """A todo task created by Alice, unassigned and without a due date."""
    return create_task(client, "alice", title="Original title", description="Original text", priority=2)


# --- identity and defaults -------------------------------------------------------------


def test_spec_2_id_is_a_generated_positive_integer(client):
    """SPEC.md section 2: id is a database-generated positive integer."""
    task_ids = [create_task(client, title=f"Task {number}")["id"] for number in range(3)]
    assert all(type(task_id) is int and task_id > 0 for task_id in task_ids), task_ids
    assert len(set(task_ids)) == 3, task_ids


def test_spec_2_new_task_has_documented_defaults(client):
    """SPEC.md section 2: description defaults to empty, priority to 3, status begins todo."""
    created = create_task(client, title="Defaults")
    for task in (created, get_task(client, created["id"])):
        assert task["description"] == ""
        assert task["priority"] == 3
        assert task["status"] == "todo"
        assert task["assignee_id"] is None
        assert task["due_at"] is None


def test_spec_2_status_begins_todo_whatever_else_is_given(client, ids):
    """SPEC.md section 2: status begins todo."""
    created = create_task(
        client, "admin", title="Fully specified", priority=5, assignee_id=ids["bob"], due_at="2026-06-01T00:00:00Z"
    )
    assert created["status"] == "todo"
    assert get_task(client, created["id"])["status"] == "todo"


@pytest.mark.parametrize("actor", ["admin", "alice", "bob"])
def test_spec_2_creator_is_the_authenticated_actor(client, ids, actor):
    """SPEC.md section 2: creator_id is the authenticated creator."""
    created = create_task(client, actor, title=f"Created by {actor}")
    assert created["creator_id"] == ids[actor]
    assert get_task(client, created["id"])["creator_id"] == ids[actor]


# --- title -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title",
    ["x", "x" * 120, "é" * 120, "東" * 120, "🚀" * 120],
    ids=["1-char", "120-ascii", "120-latin", "120-cjk", "120-emoji"],
)
def test_spec_2_title_of_1_to_120_characters_is_accepted(client, title):
    """SPEC.md section 2: title is 1–120 Unicode characters; both limits are accepted."""
    created = create_task(client, title=title)
    assert created["title"] == title
    assert get_task(client, created["id"])["title"] == title


@pytest.mark.parametrize("title", ["", "x" * 121, "é" * 121], ids=["empty", "121-ascii", "121-latin"])
def test_spec_2_title_outside_1_to_120_characters_is_rejected(client, title):
    """SPEC.md section 2: a title shorter than 1 or longer than 120 characters returns 422 and creates nothing."""
    response = post_task(client, {"title": title})
    assert response.status_code == 422, response.text
    assert task_total(client) == 0


@pytest.mark.parametrize("title", [" ", "   ", "\t\n "], ids=["space", "spaces", "mixed-whitespace"])
def test_spec_2_blank_title_is_rejected(client, title):
    """SPEC.md section 2: title is nonblank; a whitespace-only title returns 422 and creates nothing."""
    response = post_task(client, {"title": title})
    assert response.status_code == 422, response.text
    assert task_total(client) == 0


@pytest.mark.parametrize(
    "title",
    [
        "Überprüfung — 東京 ✓ 🚀",
        "  padded on both sides  ",
        "Tags <b>&amp;</b> and 'quotes'",
        "first line\nsecond line",
    ],
    ids=["unicode", "padded", "markup", "line-break"],
)
def test_spec_2_title_is_preserved_exactly(client, title):
    """SPEC.md section 2: title is a Unicode string preserved exactly."""
    created = create_task(client, title=title)
    assert created["title"] == title
    assert get_task(client, created["id"])["title"] == title


@pytest.mark.parametrize(
    "body",
    [{"title": 123}, {"title": ["a list"]}, {"title": True}, {}],
    ids=["number", "list", "boolean", "missing"],
)
def test_spec_2_title_must_be_a_given_string(client, body):
    """SPEC.md section 2: title is a required string; anything else returns 422 and creates nothing."""
    response = post_task(client, body)
    assert response.status_code == 422, response.text
    assert task_total(client) == 0


# --- description -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "description", ["", "d" * 2000, "Ünïcødé\nsecond line"], ids=["empty", "2000-chars", "unicode"]
)
def test_spec_2_description_up_to_2000_characters_is_accepted(client, description):
    """SPEC.md section 2: description is a string of up to 2,000 characters."""
    created = create_task(client, title="Described", description=description)
    assert created["description"] == description
    assert get_task(client, created["id"])["description"] == description


def test_spec_2_description_over_2000_characters_is_rejected(client):
    """SPEC.md section 2: a description of 2,001 characters returns 422 and creates nothing."""
    response = post_task(client, {"title": "Too long", "description": "d" * 2001})
    assert response.status_code == 422, response.text
    assert task_total(client) == 0


# --- priority --------------------------------------------------------------------------


@pytest.mark.parametrize("priority", [1, 5])
def test_spec_2_priority_limits_1_and_5_are_accepted(client, priority):
    """SPEC.md section 2: priority is an integer 1–5."""
    created = create_task(client, title="Prioritised", priority=priority)
    assert created["priority"] == priority
    assert get_task(client, created["id"])["priority"] == priority


@pytest.mark.parametrize(
    "priority", [0, 6, -1, True, 3.0, 2.5, "3"], ids=["0", "6", "-1", "true", "3.0", "2.5", "string-3"]
)
def test_spec_2_priority_must_be_an_integer_from_1_to_5(client, priority):
    """SPEC.md section 2: priority outside 1–5, a boolean or a float returns 422 and creates nothing."""
    response = post_task(client, {"title": "Bad priority", "priority": priority})
    assert response.status_code == 422, response.text
    assert task_total(client) == 0


@pytest.mark.parametrize("field", ["title", "description", "priority"])
def test_spec_2_null_for_non_nullable_field_on_create_is_rejected(client, field):
    """SPEC.md section 2: null for a non-nullable field returns 422 and creates nothing."""
    response = post_task(client, {"title": "Valid title", field: None})
    assert response.status_code == 422, response.text
    assert task_total(client) == 0


# --- assignee --------------------------------------------------------------------------


@pytest.mark.parametrize("assignee", ["admin", "alice", "bob"])
def test_spec_2_assignee_may_be_an_admin_or_member(client, ids, assignee):
    """SPEC.md section 2: assignee_id may be an existing admin or member ID."""
    created = create_task(client, title=f"For {assignee}", assignee_id=ids[assignee])
    assert created["assignee_id"] == ids[assignee]
    assert get_task(client, created["id"])["assignee_id"] == ids[assignee]


@pytest.mark.parametrize("assignee", ["observer", "unknown"])
def test_spec_2_assignee_must_be_an_existing_admin_or_member(client, ids, assignee):
    """SPEC.md section 2: an observer or unknown user as assignee returns 422 and creates nothing."""
    assignee_id = ids[assignee] if assignee in ids else MISSING_USER_ID
    response = post_task(client, {"title": "Badly assigned", "assignee_id": assignee_id})
    assert response.status_code == 422, response.text
    assert task_total(client) == 0


@pytest.mark.parametrize("kind", ["boolean", "float"])
def test_spec_2_assignee_id_rejects_booleans_and_floats(client, ids, kind):
    """SPEC.md section 2: booleans and floats are not integers for input validation."""
    assignee_id = True if kind == "boolean" else float(ids["bob"])
    response = post_task(client, {"title": "Oddly assigned", "assignee_id": assignee_id})
    assert response.status_code == 422, response.text
    assert task_total(client) == 0


def test_spec_2_assignee_may_be_cleared_to_null(client, ids):
    """SPEC.md section 2: assignee_id is null or an existing admin/member ID."""
    created = create_task(client, title="Assigned, then not", assignee_id=ids["bob"])
    response = patch_task(client, created["id"], {"assignee_id": None})
    assert response.status_code == 200, response.text
    assert response.json()["assignee_id"] is None
    assert get_task(client, created["id"])["assignee_id"] is None


# --- due_at ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("given", "instant"),
    [
        ("2026-03-01T12:00:00+02:00", datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)),
        ("2026-03-01T10:00:00Z", datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)),
        ("2026-02-28T23:30:00-05:00", datetime(2026, 3, 1, 4, 30, tzinfo=timezone.utc)),
    ],
    ids=["plus-two", "zulu", "minus-five-next-day"],
)
def test_spec_2_due_at_is_normalized_to_utc(client, given, instant):
    """SPEC.md section 2: due_at is a timezone-aware ISO-8601 timestamp normalized to UTC."""
    created = create_task(client, title="Dated", due_at=given)
    assert parse_utc(created["due_at"]) == instant
    assert parse_utc(get_task(client, created["id"])["due_at"]) == instant


@pytest.mark.parametrize(
    "due_at",
    ["2026-03-01T12:00:00", "2026-03-01", "not a timestamp", "2026-13-01T10:00:00Z"],
    ids=["naive", "date-only", "text", "month-13"],
)
def test_spec_2_naive_or_invalid_due_at_is_rejected(client, due_at):
    """SPEC.md section 2: a naive or invalid timestamp returns 422 and creates nothing."""
    response = post_task(client, {"title": "Badly dated", "due_at": due_at})
    assert response.status_code == 422, response.text
    assert task_total(client) == 0


def test_spec_2_due_at_may_be_null(client):
    """SPEC.md section 2: due_at is null or an aware timestamp; null is accepted and clears it."""
    undated = create_task(client, title="Undated", due_at=None)
    assert undated["due_at"] is None
    dated = create_task(client, title="Dated, then not", due_at="2026-03-01T10:00:00Z")
    response = patch_task(client, dated["id"], {"due_at": None})
    assert response.status_code == 200, response.text
    assert get_task(client, dated["id"])["due_at"] is None


# --- unknown fields --------------------------------------------------------------------


def unknown_value(field, ids):
    return {
        "colour": "red",
        "id": 777,
        "creator_id": ids["bob"],
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "work_minutes": 60,
    }[field]


@pytest.mark.parametrize("field", ["colour", "id", "creator_id", "work_minutes"])
def test_spec_2_unknown_input_field_on_create_is_rejected(client, ids, field):
    """SPEC.md section 2: unknown input fields return 422 and create nothing."""
    response = post_task(client, {"title": "With extra field", field: unknown_value(field, ids)})
    assert response.status_code == 422, response.text
    assert task_total(client) == 0


@pytest.mark.parametrize("field", ["colour", "id", "creator_id", "created_at", "updated_at", "work_minutes"])
def test_spec_2_patch_with_unknown_or_read_only_field_is_rejected(client, ids, task, field):
    """SPEC.md sections 2 and 3: PATCH accepts only title/description/assignee_id/status/priority/due_at;
    creator_id cannot be patched; anything else returns 422 and changes nothing."""
    before = get_task(client, task["id"])
    response = patch_task(client, task["id"], {field: unknown_value(field, ids)})
    assert response.status_code == 422, response.text
    assert get_task(client, task["id"]) == before


# --- status transitions ----------------------------------------------------------------


def test_spec_2_forward_transitions_are_allowed(client, task):
    """SPEC.md section 2: todo → in_progress → done is allowed."""
    assert set_status(client, task["id"], "in_progress")["status"] == "in_progress"
    assert get_task(client, task["id"])["status"] == "in_progress"
    assert set_status(client, task["id"], "done")["status"] == "done"
    assert get_task(client, task["id"])["status"] == "done"


@pytest.mark.parametrize("status", ["todo", "in_progress", "done"])
def test_spec_2_unchanged_status_is_a_no_op(client, task, status):
    """SPEC.md section 2: sending the current status is a no-op that succeeds."""
    path = ["todo", "in_progress", "done"]
    for step in path[1 : path.index(status) + 1]:
        set_status(client, task["id"], step)
    before = get_task(client, task["id"])
    response = patch_task(client, task["id"], {"status": status})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == status
    assert get_task(client, task["id"])["status"] == before["status"] == status


@pytest.mark.parametrize("actor", ["alice", "admin"])
def test_spec_2_skipping_todo_to_done_returns_409(client, task, actor):
    """SPEC.md section 2: skipping todo → done returns 409 and leaves the task unchanged."""
    before = get_task(client, task["id"])
    response = patch_task(client, task["id"], {"status": "done"}, actor)
    assert response.status_code == 409, response.text
    assert get_task(client, task["id"]) == before


@pytest.mark.parametrize(
    ("reached", "target", "actor"),
    [("in_progress", "todo", "alice"), ("in_progress", "todo", "admin"), ("done", "todo", "admin")],
    ids=["in_progress-to-todo-member", "in_progress-to-todo-admin", "done-to-todo-admin"],
)
def test_spec_2_backward_transitions_other_than_reopen_return_409(client, task, reached, target, actor):
    """SPEC.md sections 2 and 5: a transition outside the allowed ones is an invalid state, 409."""
    set_status(client, task["id"], "in_progress")
    if reached == "done":
        set_status(client, task["id"], "done")
    before = get_task(client, task["id"])
    response = patch_task(client, task["id"], {"status": target}, actor)
    assert response.status_code == 409, response.text
    assert get_task(client, task["id"]) == before


def test_spec_2_admin_can_reopen_done_task(client, task):
    """SPEC.md section 2: an administrator can reopen done → in_progress."""
    set_status(client, task["id"], "in_progress")
    set_status(client, task["id"], "done")
    response = patch_task(client, task["id"], {"status": "in_progress"}, "admin")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "in_progress"
    assert get_task(client, task["id"])["status"] == "in_progress"


def test_spec_2_member_cannot_reopen_done_task(client, task):
    """SPEC.md sections 2 and 5: only an administrator can reopen; the creator is forbidden, 403.
    SPEC.md names no code for this refusal; 403 is read from section 5 ("authenticated but forbidden
    where visibility is not hidden"), since the transition itself is valid for an administrator."""
    set_status(client, task["id"], "in_progress")
    set_status(client, task["id"], "done")
    before = get_task(client, task["id"])
    response = patch_task(client, task["id"], {"status": "in_progress"}, "alice")
    assert response.status_code == 403, response.text
    assert get_task(client, task["id"]) == before


@pytest.mark.parametrize("status", ["blocked", "DONE", "", 1], ids=["blocked", "upper-case", "empty", "number"])
def test_spec_2_unknown_status_value_is_rejected(client, task, status):
    """SPEC.md sections 2 and 5: a status that is not todo/in_progress/done is invalid input, 422."""
    before = get_task(client, task["id"])
    response = patch_task(client, task["id"], {"status": status})
    assert response.status_code == 422, response.text
    assert get_task(client, task["id"]) == before


# --- timestamps ------------------------------------------------------------------------


def test_spec_2_created_at_and_updated_at_are_utc_timestamps(client, task):
    """SPEC.md section 2: created_at and updated_at are UTC timestamps."""
    stored = get_task(client, task["id"])
    created_at = parse_utc(stored["created_at"])
    updated_at = parse_utc(stored["updated_at"])
    assert abs(datetime.now(timezone.utc) - created_at) < timedelta(minutes=10), stored
    assert updated_at >= created_at, stored
    response = patch_task(client, task["id"], {"title": "Changed title"})
    assert response.status_code == 200, response.text
    later = get_task(client, task["id"])
    assert parse_utc(later["created_at"]) == created_at, later
    assert parse_utc(later["updated_at"]) >= updated_at, later


# --- PATCH bodies ----------------------------------------------------------------------


def test_spec_2_empty_patch_body_is_rejected(client, task):
    """SPEC.md section 2: an empty PATCH body returns 422 and changes nothing."""
    before = get_task(client, task["id"])
    response = patch_task(client, task["id"], {})
    assert response.status_code == 422, response.text
    assert get_task(client, task["id"]) == before


@pytest.mark.parametrize("field", ["title", "description", "priority", "status"])
def test_spec_2_null_for_non_nullable_field_on_patch_is_rejected(client, task, field):
    """SPEC.md section 2: null for a non-nullable field returns 422 and changes nothing."""
    before = get_task(client, task["id"])
    response = patch_task(client, task["id"], {field: None})
    assert response.status_code == 422, response.text
    assert get_task(client, task["id"]) == before


@pytest.mark.parametrize("title", ["", "   ", "x" * 121], ids=["empty", "blank", "121-chars"])
def test_spec_2_patch_title_outside_limits_is_rejected(client, task, title):
    """SPEC.md section 2: a patched title must still be nonblank and 1–120 characters."""
    before = get_task(client, task["id"])
    response = patch_task(client, task["id"], {"title": title})
    assert response.status_code == 422, response.text
    assert get_task(client, task["id"]) == before


@pytest.mark.parametrize("priority", [0, 6, True, 4.0], ids=["0", "6", "true", "4.0"])
def test_spec_2_patch_priority_must_be_an_integer_from_1_to_5(client, task, priority):
    """SPEC.md section 2: a patched priority must be an integer 1–5, not a boolean or float."""
    before = get_task(client, task["id"])
    response = patch_task(client, task["id"], {"priority": priority})
    assert response.status_code == 422, response.text
    assert get_task(client, task["id"]) == before


PARTIAL_PATCHES = {
    "skipped-transition": (lambda ids: {"title": "Changed", "status": "done"}, 409),
    "priority-out-of-range": (lambda ids: {"title": "Changed", "priority": 6}, 422),
    "observer-as-assignee": (lambda ids: {"title": "Changed", "assignee_id": ids["observer"]}, 422),
    "unknown-assignee": (lambda ids: {"title": "Changed", "assignee_id": MISSING_USER_ID}, 422),
    "naive-due-at": (lambda ids: {"title": "Changed", "due_at": "2026-03-01T12:00:00"}, 422),
    "unknown-field": (lambda ids: {"title": "Changed", "colour": "red"}, 422),
    "blank-title": (lambda ids: {"description": "Changed", "title": "   "}, 422),
}


@pytest.mark.parametrize("case", sorted(PARTIAL_PATCHES))
def test_spec_2_rejected_patch_does_not_partially_modify_the_task(client, ids, task, case):
    """SPEC.md section 2: invalid operations must not partially modify data."""
    make_body, expected = PARTIAL_PATCHES[case]
    before = get_task(client, task["id"])
    response = patch_task(client, task["id"], make_body(ids))
    assert response.status_code == expected, response.text
    assert get_task(client, task["id"]) == before
