import csv
import io
import pytest


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


@pytest.mark.parametrize("path", ["/users", "/tasks", "/tasks/1", "/tasks/export"])
def test_authentication_required(client, path):
    assert client.get(path).status_code == 401


def test_bad_token(client):
    assert client.get("/tasks", headers={"Authorization": "Bearer unknown"}).status_code == 401


def test_users(client, alice):
    users = client.get("/users", headers=alice).json()
    assert [user["id"] for user in users] == [1, 2, 3, 4]
    assert all("token" not in user for user in users)


def test_create(client, task):
    assert task["title"] == "Review document"
    assert task["creator_id"] == 2
    assert task["status"] == "todo"
    assert task["work_minutes"] == 0


def test_get_own(client, alice, task):
    assert client.get(f"/tasks/{task['id']}", headers=alice).json() == task


def test_unknown_task(client, alice):
    assert client.get("/tasks/9999", headers=alice).status_code == 404


def test_empty_collection(client, alice):
    response = client.get("/tasks", headers=alice)
    assert response.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}


def test_list_full_page(client, alice):
    for title in ["One", "Two"]:
        client.post("/tasks", json={"title": title}, headers=alice)
    data = client.get("/tasks?limit=2", headers=alice).json()
    assert [row["title"] for row in data["items"]] == ["One", "Two"]
    assert data["total"] == 2


@pytest.mark.parametrize("body", [
    {"title": ""}, {"title": "   "}, {"title": "X" * 121},
    {"title": "T", "priority": 0}, {"title": "T", "priority": 6},
    {"title": "T", "priority": True}, {"title": "T", "priority": 1.5},
    {"title": "T", "unknown": "ignored?"}, {"title": "T", "due_at": "2026-01-01"},
])
def test_invalid_create(client, alice, body):
    assert client.post("/tasks", json=body, headers=alice).status_code == 422


@pytest.mark.parametrize("assignee_id", [4, 999])
def test_invalid_assignee(client, alice, assignee_id):
    assert client.post("/tasks", json={"title": "Task", "assignee_id": assignee_id}, headers=alice).status_code == 422


def test_progress_and_complete(client, alice, task):
    path = f"/tasks/{task['id']}"
    assert client.patch(path, json={"status": "in_progress"}, headers=alice).status_code == 200
    assert client.patch(path, json={"status": "done"}, headers=alice).json()["status"] == "done"


def test_cannot_skip_progress(client, alice, task):
    assert client.patch(f"/tasks/{task['id']}", json={"status": "done"}, headers=alice).status_code == 409


def test_admin_reopens(client, alice, admin, task):
    path = f"/tasks/{task['id']}"
    client.patch(path, json={"status": "in_progress"}, headers=alice)
    client.patch(path, json={"status": "done"}, headers=alice)
    assert client.patch(path, json={"status": "in_progress"}, headers=alice).status_code == 403
    assert client.patch(path, json={"status": "in_progress"}, headers=admin).status_code == 200


def test_observer_create(client, observer):
    result = client.post("/tasks", json={"title": "Observer task"}, headers=observer)
    assert result.status_code in (201, 403)


def test_observer_cannot_patch(client, observer, task):
    assert client.patch(f"/tasks/{task['id']}", json={"title": "Changed"}, headers=observer).status_code == 403


@pytest.mark.parametrize("body", [{}, {"title": None}, {"title": " "}, {"priority": 7}, {"status": "unknown"}])
def test_invalid_patch(client, alice, task, body):
    assert client.patch(f"/tasks/{task['id']}", json=body, headers=alice).status_code == 422


def test_work_log(client, alice, task):
    path = f"/tasks/{task['id']}/work"
    assert client.post(path, json={"minutes": 15}, headers=alice).json()["work_minutes"] == 15
    assert client.post(path, json={"minutes": 10}, headers=alice).json()["work_minutes"] == 25
    logs = client.get(path, headers=alice).json()["items"]
    assert [entry["minutes"] for entry in logs] == [15, 10]


@pytest.mark.parametrize("minutes", [0, -1, 481, True, 1.5])
def test_invalid_work(client, alice, task, minutes):
    assert client.post(f"/tasks/{task['id']}/work", json={"minutes": minutes}, headers=alice).status_code == 422


def test_idempotency_same_process(client, alice):
    headers = {**alice, "Idempotency-Key": "request-one"}
    first = client.post("/tasks", json={"title": "Retry me"}, headers=headers)
    second = client.post("/tasks", json={"title": "Retry me"}, headers=headers)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert client.post("/tasks", json={"title": "Different"}, headers=headers).status_code == 409


def test_export_simple(client, alice, task):
    rows = list(csv.DictReader(io.StringIO(client.get("/tasks/export", headers=alice).text)))
    assert rows == [{"id": str(task["id"]), "title": "Review document", "status": "todo", "assignee_id": "2"}]


def test_overdue_ordinary_case(client, alice):
    response = client.post("/tasks", json={"title": "Past", "due_at": "2026-01-01T00:00:00Z"}, headers=alice)
    rows = client.get("/tasks/overdue?at=2026-01-02T00:00:00Z", headers=alice).json()["items"]
    assert [row["id"] for row in rows] == [response.json()["id"]]
