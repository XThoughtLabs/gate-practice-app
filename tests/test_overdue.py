"""GET /tasks/overdue (SPEC.md sections 2 and 3): due_at strictly earlier than at, as instants.

A task due exactly at the requested instant is not overdue, whatever offsets due_at and at
are written with; a task due any earlier, even by a microsecond, is.
"""

import pytest


ALICE = {"Authorization": "Bearer demo-alice"}

# name: due_at, each placed against the instant 2026-03-01T10:00:00Z
DUE = {
    "second-earlier": "2026-03-01T09:59:59Z",
    "microsecond-earlier-plus-0530": "2026-03-01T15:29:59.999999+05:30",
    "exactly": "2026-03-01T10:00:00Z",
    "exactly-plus-0100": "2026-03-01T11:00:00+01:00",
    "exactly-minus-0500": "2026-03-01T05:00:00-05:00",
    "microsecond-later": "2026-03-01T10:00:00.000001Z",
    "second-later-plus-0200": "2026-03-01T12:00:01+02:00",
    "undated": None,
}
EARLIER = ["second-earlier", "microsecond-earlier-plus-0530"]
EXACTLY = ["exactly", "exactly-plus-0100", "exactly-minus-0500"]


def create_all(client):
    ids = {}
    for name, due_at in DUE.items():
        response = client.post("/tasks", json={"title": f"Due {name}", "due_at": due_at}, headers=ALICE)
        assert response.status_code == 201, response.text
        ids[name] = response.json()["id"]
    return ids


def overdue(client, at):
    response = client.get("/tasks/overdue", params={"at": at}, headers=ALICE)
    assert response.status_code == 200, response.text
    return [row["id"] for row in response.json()["items"]]


@pytest.mark.parametrize("at", [
    "2026-03-01T10:00:00Z",
    "2026-03-01T10:00:00.000000+00:00",
    "2026-03-01T12:00:00+02:00",
    "2026-03-01T04:30:00-05:30",
], ids=["z", "utc-microseconds", "plus-0200", "minus-0530"])
def test_due_exactly_at_is_not_overdue(client, at):
    ids = create_all(client)
    assert overdue(client, at) == sorted(ids[name] for name in EARLIER)


@pytest.mark.parametrize("at", [
    "2026-03-01T10:00:00.000001Z",
    "2026-03-01T09:00:00.000001-01:00",
], ids=["z", "minus-0100"])
def test_a_microsecond_later_the_exact_instant_is_overdue(client, at):
    # The task due a microsecond after 10:00 is now the one due exactly at at: not overdue.
    ids = create_all(client)
    assert overdue(client, at) == sorted(ids[name] for name in EARLIER + EXACTLY)
