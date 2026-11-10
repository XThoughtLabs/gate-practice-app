"""Application operations, independent of the HTTP transport."""

from datetime import datetime, timezone
import csv
import hashlib
import io
import json

from workflow.store import KeyReused


class Problem(Exception):
    def __init__(self, status, detail):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def parse_time(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError("timezone required")
    try:
        return parsed.astimezone(timezone.utc)
    except OverflowError:
        # The offset moves its UTC value outside the years 1 to 9999 a datetime can hold.
        raise ValueError("timestamp out of range") from None


def visible(user, task):
    return user["role"] in ("admin", "observer") or user["id"] in (
        task["creator_id"], task["assignee_id"]
    )


def editable(user, task):
    # SPEC.md section 6.2: an admin may patch any task, a member only as its creator or
    # current assignee; an observer never.
    return user["role"] == "admin" or (
        user["role"] == "member" and user["id"] in (task["creator_id"], task["assignee_id"])
    )


def authorize_patch(user, task):
    # Judged against the stored task, so an assignee_id in the request itself grants nothing.
    if not visible(user, task):
        raise Problem(404, "task not found")
    if not editable(user, task):
        raise Problem(403, "write forbidden")


class Service:
    def __init__(self, store):
        self.store = store

    def authenticate(self, token):
        user = self.store.user(token)
        if user is None:
            raise Problem(401, "authentication required")
        return user

    def require_writer(self, user):
        if user["role"] == "observer":
            raise Problem(403, "write forbidden")

    def existing(self, task_id):
        task = self.store.task(task_id)
        if task is None:
            raise Problem(404, "task not found")
        return task

    def assignee_exists(self, assignee_id):
        if assignee_id is not None and not any(
            u["id"] == assignee_id and u["role"] != "observer" for u in self.store.users()
        ):
            raise Problem(422, "assignee must be an administrator or member")

    def create(self, user, values, key=None):
        self.require_writer(user)
        self.assignee_exists(values["assignee_id"])
        # The digest of the validated body (defaults filled in, due_at in UTC) is stored
        # with the key, so keep its form: a changed form would turn retries of stored keys
        # into 409.
        digest = hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()
        try:
            # The key is looked up and recorded in the task's own write transaction, so
            # simultaneous requests with one actor/key are judged one after another.
            return self.store.create(user, values, timestamp(), key, digest)
        except KeyReused:
            raise Problem(409, "idempotency key reused with a different body") from None

    def get(self, user, task_id):
        task = self.existing(task_id)
        if not visible(user, task):
            raise Problem(404, "task not found")
        return task

    def list(self, user, query, limit, offset):
        rows = self.store.visible_rows(user, query)
        page = rows[offset:offset + limit]
        return {"items": page, "total": len(rows), "limit": limit, "offset": offset}

    def overdue(self, user, at):
        # Both sides are aware UTC datetimes, so they compare as instants whatever offset
        # either was written with; a task due exactly at that instant is not yet overdue.
        instant = parse_time(at)
        return [row for row in self.store.visible_rows(user)
                if row["status"] != "done" and row["due_at"] is not None
                and parse_time(row["due_at"]) < instant]

    def update(self, user, task_id, values):
        # Missing or unreadable is 404 for every role, before 403 and before the body's
        # values are judged, so a refusal reveals nothing about the task.
        authorize_patch(user, self.existing(task_id))
        if "assignee_id" in values:
            self.assignee_exists(values["assignee_id"])

        def check(task):
            # Runs inside the store's write transaction, so simultaneous requests are
            # judged one after another against the assignment and the status each
            # actually changes.
            authorize_patch(user, task)
            new_status = values.get("status", task["status"])
            transitions = {"todo": {"todo", "in_progress"},
                           "in_progress": {"in_progress", "done"},
                           "done": {"done", "in_progress"}}
            if new_status not in transitions[task["status"]]:
                raise Problem(409, "invalid status transition")
            if task["status"] == "done" and new_status == "in_progress" and user["role"] != "admin":
                raise Problem(403, "only an administrator may reopen a task")

        task = self.store.update(task_id, values, timestamp(), user["id"], check)
        if task is None:
            raise Problem(404, "task not found")
        return task

    def add_work(self, user, task_id, minutes):
        if user["role"] == "observer":
            # An observer reads every task and writes none: a missing task is the uniform
            # 404 for them as for every role, and only an existing one is refused as a
            # write, 403. Both answers come before any write transaction.
            self.get(user, task_id)
        self.require_writer(user)

        def check(task):
            # Runs inside the store's write transaction, so each entry is judged against
            # the visibility and status the task has when the entry is written.
            if not visible(user, task):
                raise Problem(404, "task not found")
            if task["status"] == "done":
                raise Problem(409, "completed tasks do not accept work")

        task = self.store.append_work(task_id, user, minutes, timestamp(), check)
        if task is None:
            raise Problem(404, "task not found")
        return task

    def work(self, user, task_id):
        task = self.existing(task_id)
        if not visible(user, task):
            raise Problem(404, "task not found")
        return self.store.work_logs(task_id)

    def history(self, user, task_id):
        task = self.existing(task_id)
        if not visible(user, task):
            raise Problem(404, "task not found")
        return self.store.history(task_id)

    def export(self, user):
        # The csv module quotes commas, double quotes and line breaks (RFC 4180),
        # so every title comes back unchanged in one field.
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\r\n")
        writer.writerow(("id", "title", "status", "assignee_id"))
        for task in self.store.visible_rows(user):
            writer.writerow((task["id"], task["title"], task["status"],
                             "" if task["assignee_id"] is None else task["assignee_id"]))
        return buffer.getvalue()
