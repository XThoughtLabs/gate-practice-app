# Titles with U+0000: rebuilding the tasks table of an existing database

SPEC.md sections 2, 4 and 5, issue #39. This describes why the tasks table changed, and what happens to a SQLite file made by an earlier version when this version opens it.

## Why the table changed

A title is a nonblank Unicode string of 1 to 120 characters, preserved exactly. U+0000 (NUL) is one of its characters like any other, so the API accepts a title such as `"\u0000X"`. The tasks table checked `CHECK(length(title) BETWEEN 1 AND 120)`. SQLite's `length()` of a text counts only the characters before its first NUL, so that check counted 0 for a title beginning with NUL and refused it. `POST /tasks` and `PATCH /tasks/{id}` then answered 500.

SQLite has no character count that goes past a NUL. `replace()` and `trim()` do not remove a NUL, and `substr()` does not count past one either. The table now checks:

```sql
CHECK(length(title) <= 120 AND length(CAST(title AS BLOB)) BETWEEN 1 AND 480)
```

| Part | What it ensures |
|---|---|
| `length(title) <= 120` | The characters before the first NUL are at most 120. For a title without NUL this is its whole length, checked exactly as before. |
| `length(CAST(title AS BLOB)) BETWEEN 1 AND 480` | The title's UTF-8 bytes, NULs included. At least 1 byte means the title is not empty. A title of 1 to 120 characters takes 1 to 480 bytes, at most 4 per character. |

The check admits every title the API accepts and refuses an empty title, a title without NUL of more than 120 characters, and any title of more than 480 bytes. The API still checks the exact rule, nonblank and 1 to 120 characters, and answers 422 for any other title. Neither the API's rules nor any other column changed.

## When it runs

There is no separate command. `create_app(db_path)` opens the file through `Store(path)`, which runs the upgrade before the application serves a request. Nothing is deleted. An empty or new file goes through the same steps.

## What changes in the file

| Item | Change |
|---|---|
| `tasks` | Rebuilt with the new title check. Every task is kept with its id and every stored value. |
| `tasks_creator`, `tasks_assignee`, and any other index or trigger on `tasks` | Created again from the definitions the file stores, so they are unchanged. |
| AUTOINCREMENT sequence of `tasks` (`sqlite_sequence`) | Kept as it was, so a new task gets the id it would have got before the upgrade. That id is above every existing one. |
| `users`, `work_logs`, `status_history` and its triggers, `idempotency_keys` | Unchanged: no rows are modified or removed. Their references to `tasks` name the table, so they refer to the rebuilt one. |
| `PRAGMA user_version` | 2 after the upgrade. Files from earlier versions are at 1, or at 0 if they were made before status history. |

After the upgrade, the file's schema is the schema of a new file.

## The steps

All of these steps run in one `BEGIN IMMEDIATE` transaction, on a connection with foreign keys off:

1. If `user_version` is 2 or more, stop. The file is already upgraded and nothing is written.
2. If `user_version` is 0, write each task's migration event, as described in `docs/status-history-migration.md`.
3. Read the `tasks` sequence and the definitions of the indexes and triggers on `tasks`.
4. Copy every task into a temporary table, `task_rows`, on the same connection.
5. Drop `tasks` and create it again with the new definition.
6. Copy the tasks back, with their ids, and drop `task_rows`.
7. Create the indexes and triggers again. Triggers come after the copy, so none fires for a copied task.
8. Put back the stored sequence. Dropping the table removed it, and copying the tasks back set it to the highest id.
9. Run `PRAGMA foreign_key_check` over the whole file. Any reference to a missing row stops the upgrade.
10. Set `user_version` to 2 and commit.

Foreign keys are off because, with them on, `DROP TABLE tasks` first deletes every task, and the references of work logs, status history and idempotency keys refuse that with `FOREIGN KEY constraint failed`. That setting cannot change inside a transaction. Step 9 checks every reference before the commit instead.

## If it fails

Either all of these changes commit or none do. If any step fails, for example because the disk is full or a stored row breaks a check, the transaction rolls back. A file from the version before this one is then left exactly as it was, byte for byte, at `user_version` 1. The application does not start, and the error names the cause. The next start runs the whole upgrade again. If the process itself stops part-way, SQLite rolls the transaction back from its rollback journal when the file is next opened. The tests do not cover that case.

A file made before status history (`user_version` 0) first gets the empty `status_history` and `idempotency_keys` tables from the schema, before this transaction. These leave existing tables untouched. The transaction then writes the migration events, the rebuilt table and the new `user_version` together, or none of them.

Two kinds of stored row stop the upgrade. Neither can be written through the API:

| Row | Error |
|---|---|
| A title the earlier check let through but the new one refuses: a NUL after its first character and more than 480 bytes in all | `CHECK constraint failed` while copying the tasks back |
| A row that refers to a missing row, such as a work log of a missing task | `FOREIGN KEY constraint failed: work_logs row 4 refers to a missing tasks row` |

Correct or remove the row named in the error, then start the application again.

A second process that opens the file at the same moment waits for the write lock and then finds `user_version` 2. On a very large file it may wait longer than its 10-second busy timeout and fail to start. Starting it again then finds the file upgraded.

## Procedure

1. Stop the running version.
2. Copy the database file (by default `data/workflow.sqlite3`, or the file named by `WORKFLOW_DB_PATH`) as a backup.
3. Start the new version on the same file.
4. Check the upgrade:
   - `PRAGMA user_version` returns 2.
   - `SELECT sql FROM sqlite_master WHERE name = 'tasks'` shows `length(CAST(title AS BLOB))`.
   - `PRAGMA foreign_key_check` returns no rows.
   - A `POST /tasks` with the title `"\u0000X"` returns 201 and that title.

To go back, stop the new version and restore the backup. Tasks created after the upgrade are lost then.

## Earlier upgrade documents

`docs/status-history-migration.md` and `docs/idempotency-keys.md` describe their steps as they were added. On this version, a file upgraded by those steps ends at `user_version` 2, not 1, and its `tasks` table has the definition above. The rest of those documents still holds.

## Tests

`tests/test_nul_titles.py`:

- Titles that begin with, contain, or are made only of NUL, up to 120 characters, are created with 201. The task, list, search, overdue and export routes return them exactly. A search finds the text after the NUL.
- Titles of 121 characters with NUL still give 422, for POST and for PATCH.
- PATCH of such a title gives 200, alone or with a status change. A status change adds exactly one history event; a title-only change adds none.
- The table's own check admits 120 NULs and 120 four-byte characters. It refuses an empty title, 121 characters without NUL, and 481 bytes.
- An existing file is built with the schema before this change, copied verbatim. It holds tasks, work logs, status-history events and idempotency keys, a gap in the task ids, and a sequence above the highest id. After the upgrade:
  - every row and sequence is unchanged, and the schema is a new file's;
  - a restart leaves the file byte for byte as it was;
  - a stored key still names its task, and a NUL title is accepted;
  - a new task gets the stored sequence plus one.
- An extra index and triggers on `tasks` are created again unchanged. A trigger that would refuse the copied tasks does not fire.
- A failure injected at each step of the rebuild leaves the file byte for byte unchanged, and the next start completes the upgrade. So does an oversize stored title or a reference to a missing task.

`tests/test_status_history.py` and `tests/test_idempotent_creation.py` check the same upgrade from the files of the two earlier versions: `user_version` 2, and every row, index and trigger kept.
