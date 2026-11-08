"""GET /tasks?q= (SPEC.md sections 1, 3 and 5): search text is data, not SQL.

q is a literal, ASCII case-insensitive substring of the title or description. Quotes,
comments, parentheses and UNION in q are plain characters; %, _ and \\ match only
themselves; an empty q lists every visible task. A member's search, however it is
written, returns only tasks the member may read, and valid input never gives a 500.
"""

import pytest
from fastapi.testclient import TestClient

from workflow.api import create_app


HEADERS = {name: {"Authorization": f"Bearer demo-{name}"} for name in ("admin", "alice", "bob", "observer")}
IDS = {"admin": 1, "alice": 2, "bob": 3, "observer": 4}


@pytest.fixture
def client(tmp_path):
    # A server error comes back as a 500 response for the test to assert against,
    # not as an exception raised inside the test client.
    with TestClient(create_app(tmp_path / "test.sqlite3"), raise_server_exceptions=False) as result:
        yield result


def create(client, actor, title, description="", assignee=None):
    body = {"title": title, "description": description, "assignee_id": IDS.get(assignee)}
    response = client.post("/tasks", json=body, headers=HEADERS[actor])
    assert response.status_code == 201, response.text
    return response.json()["id"]


def search(client, actor, q):
    response = client.get("/tasks", params={"q": q, "limit": 100}, headers=HEADERS[actor])
    assert response.status_code == 200, response.text
    body = response.json()
    return [row["id"] for row in body["items"]], body["total"]


# --- SQL in q is plain text -----------------------------------------------------------

CRAFTED = {
    "apostrophe": "O'Brien",
    "both-quotes": "it's \"quoted\"",
    "quote-or-true": "' OR '1'='1",
    "line-comment": "' --",
    "block-comment-or-true": "'/* comment */ OR '1'='1",
    "closed-parenthesis": "')",
    "parenthesis-or-true": "') OR 1=1 --",
    "union": "zzz') UNION SELECT * FROM tasks --",
    "union-forged-row": "') UNION SELECT 99, 'forged', '', 1, NULL, 'todo', 3, NULL, 0, 'x', 'x' --",
    "stacked-drop": "'); DROP TABLE tasks; --",
    "nul": "\x00",
}


@pytest.mark.parametrize("q", list(CRAFTED.values()), ids=list(CRAFTED))
@pytest.mark.parametrize("actor", ["admin", "observer"])
def test_sql_in_q_matches_no_task_and_harms_nothing(client, actor, q):
    created = [create(client, "alice", title) for title in ("alpha", "beta", "gamma")]
    assert search(client, actor, q) == ([], 0)
    assert search(client, actor, "") == (created, 3)


# --- a member's crafted search stays within the member's tasks ------------------------

MEMBER_CRAFTED = {
    "quote-or-true": "' OR '1'='1",
    "parenthesis-or-true": "') OR 1=1 --",
    "union-all-tasks": "zzz') UNION SELECT * FROM tasks --",
    "union-bob-tasks": "zzz') UNION SELECT * FROM tasks WHERE creator_id = 3 --",
    "percent": "%",
    "underscore": "_",
}


def tasks_of_every_reader(client):
    """Alice reads her own task and the one assigned to her; Bob's and the admin's are hidden."""
    readable = [create(client, "alice", "Alice plan"),
                create(client, "admin", "Admin task for Alice", assignee="alice")]
    hidden = [create(client, "bob", "Bob secret"), create(client, "admin", "Admin unassigned")]
    return readable, hidden


@pytest.mark.parametrize("q", list(MEMBER_CRAFTED.values()), ids=list(MEMBER_CRAFTED))
def test_member_crafted_search_never_returns_an_unreadable_task(client, q):
    readable, hidden = tasks_of_every_reader(client)
    ids, total = search(client, "alice", q)
    assert not set(ids) & set(hidden)
    assert (ids, total) == ([], 0)
    assert search(client, "alice", "") == (readable, 2)
    assert search(client, "admin", "") == (sorted(readable + hidden), 4)


@pytest.mark.parametrize("q", list(MEMBER_CRAFTED.values()), ids=list(MEMBER_CRAFTED))
def test_member_finds_crafted_text_only_in_own_tasks(client, q):
    # The same text is stored in Alice's task and in Bob's: a literal search finds both
    # for the readers of every task, and only Alice's for Alice.
    readable, hidden = tasks_of_every_reader(client)
    mine = create(client, "alice", q)
    bobs = create(client, "bob", "Bob notes", description=q)
    assert search(client, "alice", q) == ([mine], 1)
    assert search(client, "bob", q) == ([bobs], 1)
    for reader in ("admin", "observer"):
        assert search(client, reader, q) == ([mine, bobs], 2)
    assert search(client, "alice", "") == (readable + [mine], 3)


# --- %, _ and \ match only themselves -------------------------------------------------

LITERAL_TITLES = {
    "percent": "100% done",
    "digits": "1000 done",
    "underscore": "snake_case",
    "letter": "snakeXcase",
    "backslash": "C:\\temp",
    "backslash-percent": "50\\% off",
}


def create_literal_titles(client):
    return {name: create(client, "alice", title) for name, title in LITERAL_TITLES.items()}


@pytest.mark.parametrize(("q", "expected"), [
    ("%", ["percent", "backslash-percent"]),
    ("0%", ["percent"]),
    ("%%", []),
    ("_", ["underscore"]),
    ("e_c", ["underscore"]),
    ("_x", []),
], ids=["percent", "digit-percent", "double-percent", "underscore", "letter-underscore-letter",
        "underscore-letter"])
def test_like_wildcards_match_only_themselves(client, q, expected):
    created = create_literal_titles(client)
    wanted = [created[name] for name in LITERAL_TITLES if name in expected]
    assert search(client, "admin", q) == (wanted, len(wanted))


def test_backslash_matches_only_itself(client):
    # A backslash is neither an escape for the character after it nor for itself.
    created = create_literal_titles(client)
    cases = {
        "\\": ["backslash", "backslash-percent"],
        "\\t": ["backslash"],
        "\\%": ["backslash-percent"],
        "\\_": [],
        "\\\\": [],
    }
    found = {q: search(client, "admin", q) for q in cases}
    wanted = {}
    for q, expected in cases.items():
        ids = [created[name] for name in LITERAL_TITLES if name in expected]
        wanted[q] = (ids, len(ids))
    assert found == wanted


# --- case-insensitive matching still works ---------------------------------------------

@pytest.mark.parametrize(("q", "expected"), [
    ("o'brien's report", ["apostrophe"]),
    ("O'BRIEN'S REPORT", ["apostrophe"]),
    ("O'bRiEn", ["apostrophe"]),
    ("50%_off", ["description"]),
    ("50%_OFF", ["description"]),
    ("Ends With 50%", ["description"]),
], ids=["lower-title", "upper-title", "mixed-title", "lower-description", "upper-description",
        "mixed-description"])
def test_search_is_ascii_case_insensitive(client, q, expected):
    created = {
        "apostrophe": create(client, "alice", "O'Brien's Report"),
        "description": create(client, "alice", "Plain title", description="ends WITH 50%_Off"),
        # Matches the description queries only if % or _ act as wildcards.
        "decoy": create(client, "alice", "OBriens report", description="it ends with 500 offices"),
    }
    wanted = [created[name] for name in created if name in expected]
    assert search(client, "admin", q) == (wanted, len(wanted))
