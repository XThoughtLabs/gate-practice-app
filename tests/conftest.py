import pytest
from fastapi.testclient import TestClient
from workflow.api import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as result:
        yield result


@pytest.fixture
def alice():
    return {"Authorization": "Bearer demo-alice"}


@pytest.fixture
def admin():
    return {"Authorization": "Bearer demo-admin"}


@pytest.fixture
def observer():
    return {"Authorization": "Bearer demo-observer"}


@pytest.fixture
def task(client, alice):
    result = client.post("/tasks", json={"title": "Review document", "assignee_id": 2}, headers=alice)
    assert result.status_code == 201
    return result.json()
