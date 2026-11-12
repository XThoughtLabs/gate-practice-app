# Status history: upgrading an existing database

SPEC.md sections 4 and 6.1, issue #19. This describes what happens to a SQLite file made by the version before status history when the new version opens it.

## When it runs

There is no separate command. `create_app(db_path)` opens the file through `Store(path)`, which runs the upgrade before the application serves a request. Nothing is deleted, and an empty or new file goes through the same steps.

## What changes in the file

| Item | Change |
|---|---|
| `users`, `tasks`, `work_logs` | Unchanged: no rows are modified or removed, and no columns are added. |
| `status_history` | New table: `task_id`, `sequence`, `actor_id`, `from_status`, `to_status`, `changed_at`, `origin`, unique per `(task_id, sequence)`. |
| Triggers `status_history_no_update`, `status_history_no_delete` | New: they refuse any `UPDATE` or `DELETE` of a stored event, so history can only be appended to. |
| `PRAGMA user_version` | 0 before the upgrade, 1 after it. |

## The migration event

Each task that has no event yet gets exactly one:

| Field | Value |
|---|---|
| `sequence` | 1 |
| `origin` | `migration` |
| `from_status` | `null` |
| `to_status` | the task's stored status |
| `actor_id` | the task's `creator_id` |
| `changed_at` | the UTC time of the migration |

This event records the task's status when the migration ran. The earlier version did not record transitions, so none are invented. Later transitions append events from sequence 2 with `origin: operation`. Tasks created after the upgrade start with their own creation event, `origin: operation`, and never get a migration event.

## Once, and all at once

The migration events and the new `user_version` are written in one `BEGIN IMMEDIATE` transaction. Either all of them are committed or none are. A later start sees `user_version` 1 and writes nothing. A second process that opens the file at the same moment waits for the lock and then also skips. The insert also skips any task that already has an event.

## Procedure

1. Stop the running version.
2. Copy the database file (by default `data/workflow.sqlite3`, or the file named by `WORKFLOW_DB_PATH`) as a backup.
3. Start the new version on the same file.
4. Check the upgrade: `PRAGMA user_version` returns 1, and `GET /tasks/{id}/history` for an existing task returns one event with `origin: migration`.

To go back, stop the new version and restore the backup. Do not run the earlier version on an upgraded file. It does not know `status_history`, so its status changes and new tasks would get no events, and the migration would not run again because `user_version` is already 1.

## Tests

`tests/test_status_history.py` builds a file with the earlier schema, copied verbatim from the baseline. It checks that the upgrade gives one migration event per task and keeps every stored value of tasks and work logs. It also checks that a restart adds nothing and that later events use `origin: operation`.
