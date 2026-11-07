"""Acceptance tests for SPEC.md section 5: errors and compatibility.

Written from SPEC.md, TASK.md, OPEN-ISSUES.md and README.md alone, without the
application's code. Each test runs the documented entry point
workflow.api:create_app(db_path) on its own temporary SQLite file, with the
fixture tokens of README.md and synthetic data only.
"""

import os
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
TASK_FIELDS = {
    "id",
    "title",
    "description",
    "priority",
    "status",
    "creator_id",
    "assignee_id",
    "due_at",
    "created_at",
    "updated_at",
    "work_minutes",
}


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


def search(client, q):
    response = client.get("/tasks", params={"q": q, "limit": 100}, headers=auth("admin"))
    assert response.status_code == 200, response.text
    body = response.json()
    return [item["id"] for item in body["items"]], body["total"]


SQL_TEXT = [
    "O'Brien's task",
    'Say "hello"',
    "1; DROP TABLE tasks; --",
    "Robert'); DELETE FROM tasks; --",
    "50% off_sale \\ backslash",
    "' OR '1'='1",
]


@pytest.mark.parametrize("title", SQL_TEXT, ids=["apostrophe", "double-quotes", "drop", "delete", "like-chars", "or-true"])
def test_spec_5_text_with_sql_metacharacters_is_stored_and_found(client, title):
    """SPEC.md sections 3 and 5: valid input with SQL metacharacters never causes an internal error;
    it is stored exactly and found as literal text."""
    other = create_task(client, title="Unrelated neighbour")
    created = create_task(client, title=title, description=title)
    response = client.get(f"/tasks/{created['id']}", headers=auth("admin"))
    assert response.status_code == 200, response.text
    assert (response.json()["title"], response.json()["description"]) == (title, title)
    assert search(client, title) == ([created["id"]], 1)
    assert search(client, "") == (sorted([other["id"], created["id"]]), 2)


def test_spec_5_task_keeps_its_documented_field_names(client):
    """SPEC.md section 5: existing field names remain compatible."""
    created = create_task(client, title="Named fields")
    response = client.get(f"/tasks/{created['id']}", headers=auth("admin"))
    assert response.status_code == 200, response.text
    assert TASK_FIELDS <= set(response.json()), response.json()
    assert TASK_FIELDS <= set(created), created


def test_spec_5_list_keeps_its_documented_field_names(client):
    """SPEC.md sections 3 and 5: the task list keeps items, total, limit and offset."""
    create_task(client, title="Listed")
    response = client.get("/tasks", headers=auth("admin"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert {"items", "total", "limit", "offset"} <= set(body), body
    assert TASK_FIELDS <= set(body["items"][0]), body


def test_spec_5_work_log_keeps_its_documented_field_names(client):
    """SPEC.md sections 3 and 5: work log items keep actor_id, minutes and created_at."""
    task = create_task(client, title="Logged")
    logged = client.post(f"/tasks/{task['id']}/work", json={"minutes": 10}, headers=auth("alice"))
    assert logged.status_code == 200, logged.text
    assert TASK_FIELDS <= set(logged.json()), logged.json()
    response = client.get(f"/tasks/{task['id']}/work", headers=auth("admin"))
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) == 1, items
    assert {"actor_id", "minutes", "created_at"} <= set(items[0]), items


def test_spec_5_create_app_keeps_its_data_in_the_given_file(tmp_path):
    """SPEC.md section 5: workflow.api:create_app(db_path) is the entry point; its data lives in that file."""
    first_path = str(tmp_path / "first.sqlite3")
    second_path = str(tmp_path / "second.sqlite3")
    with running_app(first_path) as client:
        created = create_task(client, title="Only in the first file")
    assert os.path.isfile(first_path)
    with running_app(second_path) as client:
        assert search(client, "") == ([], 0)
    with running_app(first_path) as client:
        assert search(client, "") == ([created["id"]], 1)
