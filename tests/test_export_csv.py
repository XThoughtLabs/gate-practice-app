"""GET /tasks/export (PUB-02): a standard CSV parser recovers every title in one field."""

import csv
import io

import pytest


BOB = {"Authorization": "Bearer demo-bob"}
HEADER = ["id", "title", "status", "assignee_id"]
ISSUE_TITLE = 'Review, phase "B"'

# Each title holds a comma, a double quote or a line break, which the export must quote.
STRUCTURED = [
    ("issue", ISSUE_TITLE),
    ("unicode", 'Überprüfung, „Phase B“ — "東京" ✓ 🚀'),
    ("line-feed", "first line\nsecond line"),
    ("crlf", "first line\r\nsecond line"),
    ("carriage-return", "first line\rsecond line"),
    ("mixed-breaks", 'Line one,\n"line two"\r\nline three\r'),
    ("fully-quoted", '"Fully quoted"'),
    ("lone-quote", '"'),
    ("trailing-comma", "Trailing comma,"),
    ("only-comma", ","),
    ("unicode-line-break", "Zeile 1 — ä\nЗадача 2 ✓"),
]


def create(client, headers, title, **fields):
    response = client.post("/tasks", json={"title": title, **fields}, headers=headers)
    assert response.status_code == 201
    assert response.json()["title"] == title
    return response.json()


def export(client, headers):
    response = client.get("/tasks/export", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    return response.content


def rows(client, headers):
    text = export(client, headers).decode("utf-8")
    return list(csv.reader(io.StringIO(text, newline="")))


def test_issue_title_is_one_field(client, alice):
    task = create(client, alice, ISSUE_TITLE)
    assert rows(client, alice) == [HEADER, [str(task["id"]), ISSUE_TITLE, "todo", ""]]


def test_issue_title_uses_standard_quoting(client, alice):
    task = create(client, alice, ISSUE_TITLE, assignee_id=3)
    assert export(client, alice) == (
        b"id,title,status,assignee_id\r\n"
        + str(task["id"]).encode() + b',"Review, phase ""B""",todo,3\r\n')


@pytest.mark.parametrize("title", [title for _, title in STRUCTURED],
                         ids=[name for name, _ in STRUCTURED])
def test_structured_title_is_recovered(client, alice, title):
    task = create(client, alice, title)
    assert rows(client, alice) == [HEADER, [str(task["id"]), title, "todo", ""]]


def test_many_structured_titles_keep_exact_columns(client, alice, admin):
    titles = [title for _, title in STRUCTURED] + ["Überprüfung — 東京 ✓ 🚀", "  spaces kept\t"]
    expected = [HEADER]
    for number, title in enumerate(titles):
        assignee = 3 if number % 2 else None
        task = create(client, alice, title, assignee_id=assignee)
        expected.append([str(task["id"]), title, "todo", "" if assignee is None else "3"])
    hidden = create(client, BOB, 'Bob, "private"\nnote')
    assert rows(client, alice) == expected
    assert rows(client, admin) == expected + [[str(hidden["id"]), hidden["title"], "todo", ""]]
    assert rows(client, BOB) == [HEADER] + [row for row in expected[1:] if row[3] == "3"] + [
        [str(hidden["id"]), hidden["title"], "todo", ""]]
