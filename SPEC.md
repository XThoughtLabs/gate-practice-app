# WorkFlow API contract v1

Status: customer trial contract. Sections 1–5 define intended existing behaviour, including behaviour not reliably implemented by the flawed baseline. Section 6 defines new work. Only the specified contract is acceptance-relevant; hidden tests must not invent additional product requirements.

## 1. Identity and visibility

This is one synthetic organization, not a tenant-isolation or production-authentication exercise. Authentication uses the documented fixed fixture tokens. `/health` and OpenAPI documentation are public. All business endpoints require authentication: missing or invalid tokens return 401. User listings never return bearer tokens.

An administrator or observer may read all tasks. A member may read only tasks they created or are assigned. Task lists, search, overdue views, exports, work logs and (after implementation) history obey this same visibility rule. For a missing or unreadable task use 404 and `{"detail":"task not found"}`. No global task counts may leak through a member's list. Observers never write. Other permissions are specified below.

## 2. Task fields and validation

`id` is a database-generated positive integer. `title` is a nonblank Unicode string, 1–120 characters, preserved exactly. `description` is a string up to 2,000 characters, default empty. `priority` is an integer 1–5, default 3; booleans/floats are not integers for input validation. `creator_id` is the authenticated creator and cannot be patched. `assignee_id` is null or an existing admin/member ID. `due_at` is null or an ISO-8601 timezone-aware timestamp, normalized to UTC. Naive timestamps and unknown input fields return 422.

Status begins `todo`. Allowed transitions: `todo → in_progress → done`; unchanged status is a no-op. Only an administrator can reopen `done → in_progress`. Skipping `todo → done` returns 409. `created_at` and `updated_at` are UTC timestamps. Unknown fields, null for non-nullable fields and empty PATCH bodies return 422. Invalid operations must not partially modify data.

## 3. Existing endpoints

| Endpoint | Contract |
|---|---|
| `GET /health` | 200, `status: ok`, version |
| `GET /users` | ID/name/role fixture directory; no tokens |
| `POST /tasks` | Admin/member only; JSON creation fields; 201 task; optional `Idempotency-Key` |
| `GET /tasks?q=&limit=20&offset=0` | Ordered by increasing ID; q is a literal case-insensitive ASCII substring of title/description; empty q means all visible tasks; limit 1–100; offset >= 0; `items,total,limit,offset` |
| `GET /tasks/overdue?at=<aware timestamp>` | Visible, unfinished tasks with due_at **strictly earlier** than at; exact equality is not overdue; increasing ID |
| `GET /tasks/export` | All visible tasks, no pagination; UTF-8 CSV; exact columns `id,title,status,assignee_id`; standard CSV quoting of commas, double quotes and line breaks; null assignee is empty |
| `GET /tasks/{id}` | Visible task, otherwise uniform 404 |
| `PATCH /tasks/{id}` | Update a nonempty subset of title/description/assignee_id/status/priority/due_at; 200 task |
| `POST /tasks/{id}/work` | Admin/member with task visibility; body minutes, strict integer 1–480; 200 updated task; done tasks return 409 |
| `GET /tasks/{id}/work` | Visible task's ordered `items` of work logs, with actor_id/minutes/created_at |

`total` counts the complete visible matching collection before paging. A partial final page retains every remaining match. Search text is data, not SQL. SQL LIKE wildcard characters `%` and `_` supplied by the caller are literal characters, not search operators. The baseline needs assessment against this contract.

Legacy PATCH permission in the starting implementation allows any authenticated admin/member to update an existing task. This legacy permission is intentionally strengthened by section 6.2; it is a feature change, not an undisclosed starting requirement. Read permissions above already apply in the existing contract.

## 4. Durability, retries and concurrency

An acknowledged task or work log survives closing and recreating the application against the same SQLite file. Each accepted work entry is recorded once and the task's work_minutes equals the sum of its work entries, including simultaneous accepted requests. A rejected request has no work effect.

For task creation, `Idempotency-Key` is optional, nonblank and 1–128 characters. The key is scoped to the actor. Repeating the same normalized request body with the same actor/key returns the same task ID and 201, including after application restart; no duplicate task is created. A different body with that actor/key returns 409. The same string used by a different actor is a separate key. Concurrent retries obey the same rule. No idempotency guarantee is requested for the work endpoint.

SQLite schema/data changes must preserve tasks and work logs in an existing database. Use a documented migration or a backward-compatible initialization; deleting the database is not an upgrade procedure. All data in this exercise is synthetic. No cryptographic witness, production login system, distributed transaction system, Rust port or new database engine is required.

## 5. Errors and compatibility

Use 401 unauthenticated, 403 authenticated but forbidden where visibility is not hidden, 404 task missing/unreadable, 409 invalid state/idempotency conflict, 422 invalid input. Valid input must not produce an internal SQL error. Existing field names, route names and CSV column order remain compatible unless a written customer clarification approves a change. Keep `workflow.api:create_app(db_path=None)` as the test entry point; transport internals may be refactored.

Performance measurements are diagnostic. This trial has no undisclosed latency or throughput rejection threshold. State the data size, measurement boundary, repetitions and units. Functional and access-control requirements remain mandatory.

## 6. New functionality to implement

### 6.1 Status history

Add `GET /tasks/{id}/history`, using the same read permissions as the task. Return `{"items":[...]}` ordered by a per-task `sequence` starting at 1. Each new task has a creation event: `from_status: null`, `to_status: todo`. Each actual successful status transition appends exactly one event with `sequence, actor_id, from_status, to_status, changed_at`. `changed_at` is an aware UTC timestamp. Do not create events for unchanged status, non-status edits, rejected requests or an idempotent creation retry.

The task update and history event commit atomically. History survives restart, is not editable through the API and is not rewritten by later changes. Existing pre-upgrade tasks receive one clearly labelled initial event with `origin: migration`, from_status null, to_status equal to the stored status, actor_id equal to creator_id; this records the migration starting state, not invented past transitions. New creation/transition events use `origin: operation`.

### 6.2 Changes to someone else's task

After the change, an admin may patch any task. A member may patch a task only when they are its creator or current assignee. An unreadable task returns 404. If the task is readable but the actor is otherwise prohibited (observer), return 403. Authorization uses the stored pre-update assignment; a member cannot grant themselves access by sending their own ID in an unauthorized patch. Rejected patches must change neither task fields nor status history. Existing reopen restrictions still apply. This rule concerns PATCH; work-entry permissions stay as defined above.

### 6.3 Acceptance scope

Repair discovered contract defects, implement both features and strengthen tests. The customer will examine the candidate's process as well as the resulting application. Additional defects found outside the planted set may be reported with a reproducible case; do not suppress them or assume that the planted set exhausts all possible defects.
