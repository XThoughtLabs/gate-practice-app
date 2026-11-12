# Idempotency keys: the stored record and upgrading an existing database

SPEC.md section 4, issue #32. This describes where `POST /tasks` keeps each `Idempotency-Key`, how a request with a key is judged, and what happens to an existing SQLite file when this version opens it.

## Why the record is in the database

The earlier version kept used keys in a dictionary in the application's memory. It checked and wrote that dictionary without a lock, and lost it when the application restarted. So simultaneous retries each created a task, simultaneous requests with different bodies were all accepted, and a retry after a restart created a second task. The record is now kept in the SQLite file, beside the task it created.

## The record

| Column | Value |
|---|---|
| `actor_id` | the authenticated creator |
| `idempotency_key` | the `Idempotency-Key` header as received |
| `body_digest` | SHA-256, in hex, of the validated request body |
| `task_id` | the task the request created |
| `created_at` | the task's `created_at` |

`(actor_id, idempotency_key)` is the table's primary key, so the file holds at most one record per actor and key. The same key string sent by another actor is a different record.

The digest is taken from the body after validation: unset fields have their defaults, and `due_at` is normalized to UTC. Field order, whitespace and the offset used to write the same `due_at` instant do not change it. The digest is `json.dumps(values, sort_keys=True)` hashed with SHA-256. Do not change this form, or adding a creation field with a default: a retry of a key stored before such a change would get 409.

## How a request with a key is judged

`Store.create` does everything in one `BEGIN IMMEDIATE` transaction, after the request has passed authentication, the observer refusal (403) and validation (422):

1. Look up the record for the actor and key.
2. If there is one with the same digest: write nothing and return the task it names, as stored now, with 201.
3. If there is one with a different digest: write nothing and return 409, `{"detail": "idempotency key reused with a different body"}`.
4. If there is none: insert the task, its creation event in `status_history` and the key record, then commit.

`BEGIN IMMEDIATE` takes the database's write lock before the lookup. Simultaneous requests with one actor and key are therefore judged one after another. The first writes its task and record, and each later one finds that record. The primary key also refuses a second record for the same actor and key if any other path writes one. Because the task, its event and the record commit together, a failure in any of the three inserts writes none of them, and the key stays unused. A rejected request (401, 403, 422, 409) records no key. A request without a key writes no record and behaves as before.

## Upgrading an existing database

There is no separate command. `create_app(db_path)` opens the file through `Store(path)`. It runs `CREATE TABLE IF NOT EXISTS idempotency_keys ...` with the rest of the schema before the application serves a request. Nothing is deleted. An empty or new file goes through the same steps.

| Item | Change |
|---|---|
| `users`, `tasks`, `work_logs` | Unchanged: no rows are modified or removed, and no columns are added. |
| `status_history` and its triggers | Unchanged in a file that already has them. A file made before status history first gets them, with its migration events, as described in `docs/status-history-migration.md`. |
| `idempotency_keys` | New table, empty after the upgrade, with its primary-key index `sqlite_autoindex_idempotency_keys_1`. |
| `PRAGMA user_version` | Not changed by this step: 1 stays 1. A file at 0 becomes 1 through the status-history migration. |

The table needs no data step, so it has no version number of its own. `CREATE TABLE IF NOT EXISTS` makes it in a file without it and does nothing in a file that has it. Two processes that open the file together run it one after the other.

The earlier version never wrote its keys to the file, so there are no records to carry over. A retry of a request that the earlier version accepted is not recognized after the upgrade and creates a new task. Every key used after the upgrade is recorded.

## Procedure

1. Stop the running version.
2. Copy the database file (by default `data/workflow.sqlite3`, or the file named by `WORKFLOW_DB_PATH`) as a backup.
3. Start the new version on the same file.
4. Check the upgrade: `SELECT name FROM sqlite_master WHERE name = 'idempotency_keys'` returns one row. `PRAGMA user_version` returns 1. A `POST /tasks` with an `Idempotency-Key`, repeated with the same body after a restart, returns the same task ID with 201.

To go back, stop the new version and restore the backup. The earlier version can still run on an upgraded file, because it ignores the new table. But it records no keys, so retries of requests it accepted would not be recognized when the new version runs again.

## Tests

`tests/test_idempotent_creation.py`:

- 8 simultaneous retries create one task.
- 8 simultaneous different bodies give one 201 and seven 409.
- Alice's and Bob's simultaneous requests with one key string create one task each.
- A retry after a restart returns the same task.
- The task, its event and its key record commit together.
- A rejected request records no key.
- The file refuses a second record for one actor and key.

The simultaneous requests are held on their way into `Store.create` until all of them are there. A check made outside the store's transaction would then let every one of them through, every time.

The upgrade test builds two files: one with the schema before status history (baseline 821330ff), and one with the schema before this change (c220363, with status-history events). Both schemas are copied verbatim. For each file, the test checks that every row, table, index and trigger is kept unchanged, that only the expected tables are added, and that keyed creation then holds across a restart.
