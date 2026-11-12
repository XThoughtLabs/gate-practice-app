"""GET /tasks paging (PUB-01): a partial final page keeps every remaining task."""

import pytest


BOB = {"Authorization": "Bearer demo-bob"}


def create(client, headers, *titles):
    tasks = []
    for title in titles:
        response = client.post("/tasks", json={"title": title}, headers=headers)
        assert response.status_code == 201
        tasks.append(response.json())
    return tasks


def listing(client, headers, **params):
    response = client.get("/tasks", params=params, headers=headers)
    assert response.status_code == 200
    return response.json()


def test_last_page_keeps_the_third_task(client, alice):
    tasks = create(client, alice, "First", "Second", "Third")
    assert listing(client, alice, limit=2, offset=2) == {
        "items": [tasks[2]], "total": 3, "limit": 2, "offset": 2}


PAGES = [
    # (tasks, limit, offset, positions of the tasks on the page)
    (0, 1, 0, []),
    (0, 100, 0, []),
    (0, 2, 2, []),
    (1, 1, 0, [0]),
    (1, 2, 0, [0]),
    (1, 100, 0, [0]),
    (1, 1, 1, []),
    (1, 2, 1, []),
    (2, 2, 0, [0, 1]),
    (3, 3, 0, [0, 1, 2]),
    (3, 1, 2, [2]),
    (4, 2, 2, [2, 3]),
    (4, 2, 4, []),
    (3, 5, 0, [0, 1, 2]),
    (3, 100, 2, [2]),
    (5, 2, 4, [4]),
    (5, 3, 3, [3, 4]),
    (3, 2, 3, []),
    (3, 2, 10, []),
]


@pytest.mark.parametrize(
    ("count", "limit", "offset", "positions"), PAGES,
    ids=[f"tasks{count}-limit{limit}-offset{offset}" for count, limit, offset, _ in PAGES],
)
def test_page_boundaries(client, alice, count, limit, offset, positions):
    tasks = create(client, alice, *(f"Task {number}" for number in range(count)))
    assert listing(client, alice, limit=limit, offset=offset) == {
        "items": [tasks[p] for p in positions], "total": count, "limit": limit, "offset": offset}


def test_every_page_is_the_matching_slice(client, alice):
    ids = []
    for count in range(7):
        for limit in (1, 2, 3, 4, 100):
            walked = []
            for offset in range(count + 2):
                body = listing(client, alice, limit=limit, offset=offset)
                assert body["total"] == count
                assert [row["id"] for row in body["items"]] == ids[offset:offset + limit]
                if offset % limit == 0:
                    walked.extend(row["id"] for row in body["items"])
            assert walked == ids
        ids.extend(task["id"] for task in create(client, alice, f"Task {count}"))


def test_last_page_of_a_search_keeps_the_remaining_match(client, alice):
    tasks = create(client, alice, "Report A", "Note", "Report B", "Report C", "Another note")
    assert listing(client, alice, q="report", limit=2, offset=2) == {
        "items": [tasks[3]], "total": 3, "limit": 2, "offset": 2}


def test_member_last_page_counts_only_visible_tasks(client, alice):
    mine = []
    for number in range(3):
        create(client, BOB, f"Bob task {number}")
        mine.extend(create(client, alice, f"Alice task {number}"))
    assert listing(client, alice, limit=2, offset=2) == {
        "items": [mine[2]], "total": 3, "limit": 2, "offset": 2}
