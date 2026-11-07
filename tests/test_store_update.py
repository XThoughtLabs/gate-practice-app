"""Behaviour of Store.update, pinned before and after its SQL is made constant."""

from datetime import datetime, timezone
import sqlite3

import pytest

from workflow.store import Store


CREATED = "2026-01-01T00:00:00.000000+00:00"
UPDATED = "2026-01-02T03:04:05.000006+00:00"
QUOTED = "O'Brien's \"plan\"; DROP TABLE tasks; --"


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "store.sqlite3")


@pytest.fixture
def created(store):
    alice = store.user("demo-alice")
    values = {"title": "Original", "description": "Before", "assignee_id": 2,
              "priority": 3, "due_at": "2026-03-01T00:00:00.000000+00:00"}
    return store.create(alice, values, CREATED)


def test_several_fields_applied_together(store, created):
    values = {"title": "Renamed", "description": "After", "assignee_id": 3,
              "status": "in_progress", "priority": 5,
              "due_at": "2026-04-01T12:00:00.000000+00:00"}
    result = store.update(created["id"], values, UPDATED)
    assert result == store.task(created["id"])
    assert result == {**created, **values, "updated_at": UPDATED}


def test_fields_not_given_are_unchanged(store, created):
    result = store.update(created["id"], {"priority": 1}, UPDATED)
    assert result == {**created, "priority": 1, "updated_at": UPDATED}


def test_nullable_fields_can_be_cleared(store, created):
    result = store.update(created["id"], {"assignee_id": None, "due_at": None}, UPDATED)
    assert result == {**created, "assignee_id": None, "due_at": None, "updated_at": UPDATED}


def test_updated_at_is_the_given_timestamp(store, created):
    result = store.update(created["id"], {"title": "Renamed"}, UPDATED)
    assert result["updated_at"] == UPDATED
    assert result["created_at"] == CREATED


def test_quoted_values_stored_and_read_back_unchanged(store, created):
    result = store.update(created["id"], {"title": QUOTED, "description": QUOTED}, UPDATED)
    assert result["title"] == result["description"] == QUOTED
    assert result == {**created, "title": QUOTED, "description": QUOTED, "updated_at": UPDATED}


@pytest.mark.parametrize("values", [
    {"creator_id": 3},
    {"title": "Renamed", "work_minutes": 60},
    {"updated_at": UPDATED},
    {"title=?, creator_id": 3},
])
def test_unknown_field_refused(store, created, values):
    with pytest.raises(ValueError, match="^unknown update field$"):
        store.update(created["id"], values, UPDATED)
    assert store.task(created["id"]) == created


def test_failed_update_changes_nothing(store, created):
    with pytest.raises(sqlite3.IntegrityError):
        store.update(created["id"], {"title": "Renamed", "status": "in_progress", "priority": 9}, UPDATED)
    assert store.task(created["id"]) == created


def test_missing_task_returns_none(store, created):
    assert store.update(created["id"] + 1, {"title": "Renamed"}, UPDATED) is None
    assert store.task(created["id"]) == created


def test_patch_applies_several_fields_with_quotes(client, alice, admin, task):
    body = {"title": QUOTED, "description": "It's \"quoted\"", "status": "in_progress",
            "priority": 1, "assignee_id": 3, "due_at": "2026-05-01T09:30:00Z"}
    start = datetime.now(timezone.utc)
    response = client.patch(f"/tasks/{task['id']}", json=body, headers=alice)
    end = datetime.now(timezone.utc)
    assert response.status_code == 200
    after = client.get(f"/tasks/{task['id']}", headers=admin).json()
    assert response.json() == after
    assert start <= datetime.fromisoformat(after.pop("updated_at")) <= end
    expected = {**task, **body, "due_at": "2026-05-01T09:30:00.000000+00:00"}
    del expected["updated_at"]
    assert after == expected
