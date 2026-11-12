# DELIVERY — WorkFlow API v0.1.0 paid pilot, Candidate A

> **Status: final, written by HQ on 2026-11-10 after the 09:06:00 Israel time reading; approved by the customer as draft 1 ("I approve everything", 2026-11-10 07:06), then completed with the items it marked to confirm.** Figures come from the files named beside them; nothing here is an estimate unless it says so.

> **Round 2 (2026-11-12).** The customer's answer to this delivery found two defects; both are fixed, and section 16 reports how. The fixed application commit is now `candidate/a` = `7ca3ec7f0aecbada02b8d7b0aedb29977cdd35fa`, and the judge is pinned at quality-gate `76ab28b940b0992f4a37c436b12b023ece4fcd52`. Sections 1–15 describe the delivery of 2026-11-10 and are not changed.

> **Round 2b (2026-11-12).** The customer's re-acceptance accepted the fix of defect 1 and found one more path to a false green status for defect 2; it is fixed, and section 17 reports how. The judge is now pinned at quality-gate `21b42312fb92bf428831d4420bd185c6e5f584f5`; the fixed application commit is still `7ca3ec7f0aecbada02b8d7b0aedb29977cdd35fa`.

- **Customer:** Vladislav (XThoughtLabs). **Candidate:** A — Vladislav with Claude models. In this simulation the customer and the candidate are one person; every report says so.
- **Pilot clock:** started 2026-11-03 12:56:44 Asia/Jerusalem, on the customer's authorization (declaration v2 as amended by v3, and AA-01). **Delivery due:** 2026-11-12 23:59 Asia/Jerusalem. **Fee:** simulated fixed fee USD 650, capped at 20 working hours (§12).
- **Delivery PR:** `candidate/a` → `main`, opened after this file reaches `candidate/a`, and **left open**; `main` is never merged into.

## 1. What is delivered (identity)

| Item | Value |
|---|---|
| Baseline (customer's frozen commit) | `XThoughtLabs/gate-practice-app` `main` = `821330ffbb19f545fb81f3c223b0a286ff6c4980`, untouched (ruleset 26750363 refuses pushes; proof 1) |
| Final application commit | `candidate/a` = `95f1a6363db6e2328f5de550a677d204c6ecefb7` (PR #43's merge, 2026-11-10 06:18:46) |
| Source archives (`git archive --format=zip`, from a fresh clone) | `gate-practice-app-95f1a63.zip` SHA-256 `7e71fd505188fb9732c417bef603c3f18d2284212cd7aa5a97c50454d8d5ba25`; baseline `gate-practice-app-821330ff.zip` SHA-256 `825589a1b2ab54d1ba29311b6f8ffc6cdfb4fde5a616c2a072c9f8ca7f58fcee` |
| Pipeline | `XThoughtLabs/quality-gate` (public, Apache 2.0): the judge is pinned at `906ebaefdc10ca459ccd9c890ecb56c9b0f3acb9` (self-test green on Linux, run 42376823450); `main` = `ffa026ad74aa7179419d9946e2cb96e9ba9d3617` after PR #1 added `launcher/` and nothing else (self-test green on its head `65b7c797`, whose tree equals `ffa026ad`'s: runs 42771034125 and 42771082510, 2,476 tests each) |
| Entry points | the judge runs by itself on every PR into `candidate/a` (`.github/workflows/judge.yml`, `pull_request_target`, calling quality-gate at its full SHA); `make check` and `make reproduce REPO=<url> SHA=<sha>` in quality-gate; the executor's launcher (`launcher/` in quality-gate at `ffa026ad`) and the reviewer's command (§13) |
| Configuration | `quality.toml` at `95f1a63`, SHA-256 `2aef7464abdcb815449b9a195523a1ba8578733ea39974d2e17a7643569861df` (turn limit 80, timeout 60 min, 3 rounds) |
| Dependency versions | application: `requirements.lock`, unchanged from the baseline, SHA-256 `8d8c777bb797920fda33e681c830ab9ffb25ab20b2b3f3ebebb4409b5d2c5b29`; pipeline at `906ebae`: `ACTIONS-LOCK.md` `2274277e…`, `Makefile` `2a883294…`, `REPRODUCE.md` `cda34c44…`, and `locks/`; judge environment: GitHub runner `ubuntu24` image 20261101.360.1, CPython 3.13.15; operator's laptop: Windows, git 2.55.0, GitHub CLI 2.101.0, CPython 3.13.15, Claude Code 2.1.322, Codex CLI 0.167.0 |
| Acceptance list | `acceptance/known-failing.txt` empty (two comment lines, SHA-256 `966a018f…`); list size 0 on every judge run since PR #37 |

## 2. Requirement → evidence

| TASK.md requirement | What was done | Evidence |
|---|---|---|
| 1. Baseline identity, environment, initial run before edits; models and tools named | Baseline run 01 on 2026-11-03 before any edit: 42 starter tests passed, coverage 92.55 %, Bandit one B608; the benchmark's recorded command fails in a clean environment (DISC-01). Models and tools declared in the pre-start declaration v2/v3 | `evidence/RUN-RECORD.md` and `evidence/attempt-1/`, `attempt-2/` on `candidate/a`; declaration v3 |
| 2. A reusable process in quality-gate; execution, verification and human acceptance kept apart; entry command, configuration, per-stage outcomes, exit codes, saved logs | quality-gate: judge (`run` → `publish` → `archive`), guard, acceptance, security, report, archive, reproduce, local reviewer. The executor (a Claude model) writes code; the judge (GitHub Actions, no secret) and the independent reviewer (Codex) verify; only a person approves and merges | quality-gate `906ebae`: `docs/CONTRACTS.md`, `REPRODUCE.md`, 2,471 own tests on Linux, 243 of 243 broken versions caught (`docs/mutants-results.json`, at `f0988c3`); every judge run's `exit-codes.tsv` and logs on the public `reports` branch |
| 3. SPEC §6 status history and restricted modification, preserving data | §6.1 by PR #21, with a migration of existing databases (`docs/status-history-migration.md`); §6.2 by PR #24 | §3 rows S-6.1, S-6.2; acceptance tests `test_spec_6_1_*`, `test_spec_6_2_*`, `test_spec_4_6_1_upgrade_of_existing_database` |
| 4. Investigate and repair contract defects; trigger, baseline result, cause, fix, regression test; correct the weak test | 3 disclosed reports, 12 further defects and one structural risk (B608) repaired (§3); the weak test corrected and shown to catch a planted regression (PUB-03) | §3; `docs/pub-03-observer-create-evidence.md` |
| 5. Whole public suite, new tests, coverage, security and static checks; every finding reviewed; failures and later successes preserved | Final judge run 42751543290: 482 tests passed, 357 of 357 acceptance tests, coverage 99 %, Bandit / semgrep / pip-audit / gitleaks clean; ruff diagnostic only. Every failed attempt is kept | §5, §6, §7; `reports` branch |
| 6. An intentionally failing mandatory check is rejected; an interrupted run is never labelled verified; a model's "ready" does not override a failed check | Seven proofs on demonstration PRs closed unmerged | §8 |
| 7. Reproducible setup and a handover another operator can follow | quality-gate `REPRODUCE.md`; the executor's launcher published in quality-gate `launcher/`; this file §13 | §13; quality-gate PR #1, merge `ffa026ad74aa7179419d9946e2cb96e9ba9d3617` |
| Delivery: branch/PR plus source archive and SHA-256; no customer merge | §1 | §1 |
| Delivery: pipeline commit, entry command, configuration, dependency versions | §1 | §1, §13 |
| Delivery: DELIVERY.md fields | this file | — |
| Delivery: raw execution logs with hashes, failed attempts included | the judge's logs are public on the `reports` branch; the operator's logs stay on the candidate's laptop, and their hash lists are in `evidence/delivery/` (§11) | §11 |
| Delivery: effort and cost report; each manual intervention and its blocker | §12 | `evidence/effort-log.csv` |

## 3. Defect table

All "actual" results are on the baseline `821330ff`. Every fix was written by the executor (a Claude model under a separate Windows user, reaching GitHub only as the app `xtl-gate-executor`), judged `ready-for-human` by the gate, passed by the independent reviewer ("Codex: pass", no findings), checked by HQ, approved by the customer as code owner and merged normally (no bypass). Each regression test was required to fail on the code before the fix.

**Source of each finding:** *disclosed* = `OPEN-ISSUES.md`; *our search* = found by our own investigation (the blind spec-derived acceptance tests, the executor's work, the baseline scanners); *comparison* = found by comparing our results with a second, separately run candidate after our search had ended (§14, DEV-03); *audit* = found by the outside audit of `f8c2fbc` (§6.3).

| ID | Source | Trigger | Expected (SPEC.md / OPEN-ISSUES.md) | Actual on baseline | Cause | Fix | Regression test |
|---|---|---|---|---|---|---|---|
| PUB-01 | disclosed | 3 tasks; `GET /tasks?limit=2&offset=2` | the third task; total 3 | the last task of a short page is dropped (here an empty page); total 3 | `Service.list` cut the last row whenever a page was shorter than `limit` | PR #13 → `f0f8fb1` | `tests/test_list_paging.py` (23 tests: the case and 19 boundaries) |
| PUB-02 | disclosed | title `Review, phase "B"`, `GET /tasks/export` | a CSV parser recovers the title in one field and exactly the documented columns | the title is split across columns | rows were joined with `","` without CSV quoting | PR #15 → `ff53ecd` (`csv.writer`, excel dialect) | `tests/test_export_csv.py` (14 tests, Unicode and line breaks) |
| PUB-03 | disclosed | `test_observer_create` | an observer's create is refused (403) | the starter test accepted 201 or 403 | a too-permissive assertion | PR #18 → `1290713`: the test asserts 403 and no task created; a planted permission regression makes it fail; the plant never merged | `tests/test_api.py::test_observer_create`; `docs/pub-03-observer-create-evidence.md` |
| B608 | our search (baseline Bandit) | Bandit B608 MEDIUM at `workflow/store.py:121` | no SQL built by string formatting | SQL `UPDATE` assembled with an f-string; the column names come from an allow-list and the values are bound, so no exploit was reproduced | structural risk, not a behavioural defect | PR #11 → `9fcae64`: one constant statement | `tests/test_store_update.py` (12 tests, behaviour unchanged) |
| VIS | our search (the executor during §6.2; acceptance tests) | a member requests `GET /tasks/{id}` of a task they neither created nor are assigned | 404 `task not found` | 200 with the task | `Service.get` returned any existing task without the visibility check | PR #26 → `8746709` | `tests/test_task_read_visibility.py` |
| D1 | our search (acceptance tests) | search text with SQL metacharacters, e.g. `' OR 1=1 --` | search text is data; no internal SQL error | 500, or every task returned; at the store level a member could read other members' tasks and every user's token (reproduced by HQ on a temporary database) | `visible_rows` built the search condition with an f-string | PR #28 → `e35f138`: bound parameters | `tests/test_search.py` |
| D2 | our search (acceptance tests) | search for `%` or `_` | wildcards are literal characters | `%` and `_` act as LIKE operators | no escaping | PR #28 (with D1): `ESCAPE` with `%`, `_` and the escape character escaped | `tests/test_search.py` |
| D3 | our search (acceptance tests) | `GET /tasks/overdue?at=` equal to a task's `due_at`, also across offsets | due strictly earlier than `at` | the equal instant is included | `<=` instead of `<` | PR #30 → `e01030a` | `tests/test_overdue.py` |
| D4 | our search (acceptance tests) | idempotent create retried concurrently, with a different body, or after a restart | one task; 409 for a different body; the same task after restart | 8 tasks for 8 concurrent retries; 8 × 201; a second task after restart | the idempotency record was a dict in memory, unlocked and lost on restart | PR #33 → `416319f`: keys stored in SQLite (`STRICT` table, SQLite ≥ 3.37) | `tests/test_idempotent_creation.py`; `docs/idempotency-keys.md` |
| D5 | our search (acceptance tests) | simultaneous `POST /tasks/{id}/work` | `work_minutes` equals the sum of accepted entries | 6 instead of 136 | read-modify-write across two transactions with a sleep between | PR #30 (with D3): one transaction | `tests/test_work_entries.py` |
| F-1 | comparison | a task ID beyond SQLite's signed 64-bit range, e.g. `9223372036854775808` | 404 for a missing task | 500 on five routes | an integer too large for SQLite raised an error that was not handled | PR #37 → `075e810` | `tests/test_edge_inputs.py` |
| F-2 | comparison | `q` longer than 200 characters | no length limit on `q` (a description holds 2,000) | 422 | an undocumented limit | PR #37 | `tests/test_edge_inputs.py` |
| F-3 | comparison | an aware timestamp whose UTC value falls outside years 1–9999, e.g. `9999-12-31T23:59:59-01:00` | 422 | 500 on create, patch and overdue | overflow on conversion to UTC | PR #37 | `tests/test_edge_inputs.py` (63 tests in all for F-1–F-3) |
| F-4 | comparison | a title containing U+0000 | stored and returned exactly | 500 | the table's `CHECK(length(title) BETWEEN 1 AND 120)`: SQLite's `length()` stops at the NUL | PR #40 → `98e30b5`: the `tasks` table rebuilt by a migration to `user_version` 2, every row, index, trigger and sequence kept | `tests/test_nul_titles.py` (38 tests); `docs/nul-title-migration.md` |
| V-01 | audit | `PATCH /tasks/{id}` whose only field is the stored status | an unchanged status is a no-op | `updated_at` rewritten | the update path always wrote | PR #43 → `95f1a63` | `tests/test_unchanged_status_and_observer_work.py` |
| V-02 | audit | an observer's `POST /tasks/{id}/work` for a missing task | 404 | 403 | the writer check ran before the lookup | PR #43 | same file (69 tests for V-01 and V-02; 17 fail on the old code) |

**Features of SPEC §6** (not defects): **S-6.1** status history, PR #21 → `e3e1318`, `tests/test_status_history.py`, `docs/status-history-migration.md`; **S-6.2** changes to another member's task, PR #24 → `e012845`, `tests/test_patch_permissions.py`.

**Unresolved claims:** none open in the application. **V-03** (a 500 on a storage fault injected by the auditor, with a correct rollback) is not a defect: HQ's audit task graded every 500 as a failure without excepting the fault it invited (§6.3).

**Starter tests changed:** only `tests/test_api.py::test_observer_create` (PUB-03, a strengthening). In PR #40 three of the executor's own earlier tests were adjusted for the new schema version (`tests/test_idempotent_creation.py`, `tests/test_status_history.py`). No test was removed or skipped.

## 4. Changed files (`821330ff..95f1a63`)

69 files, +8,747 −74 (`diff-stat.txt`). By kind:

- **Application code (3 files):** `workflow/store.py` +266 −31, `workflow/service.py` +94 −40, `workflow/api.py` +8 −1.
- **Tests:** `tests/test_api.py` +6 −2 (the PUB-03 strengthening); 13 new test files (§3).
- **Acceptance tests (blind, from SPEC.md only, D-08):** 9 files under `acceptance/` and `acceptance/known-failing.txt`, 357 tests.
- **Documents:** `docs/status-history-migration.md`, `docs/idempotency-keys.md`, `docs/nul-title-migration.md`, `docs/pub-03-observer-create-evidence.md`.
- **Control part:** `.github/workflows/judge.yml`, `.github/ISSUE_TEMPLATE/task.md`, `CODEOWNERS`, `quality.toml`, `prompts/executor.md`, `prompts/spec-tests.md`.
- **Evidence:** the baseline run (`evidence/RUN-RECORD.md`, `evidence/attempt-1/`, `evidence/attempt-2/`) and `evidence/effort-log.csv`.

The full list with line counts: `diff-numstat.txt`, `diff-name-status.txt` (§11).

## 5. Commands and exit codes (final judge run 42751543290, head `e76db87`, whose tree equals `95f1a63`)

| Check | Command (as recorded) | Exit | Seconds |
|---|---|---|---|
| gate/env | `python -P -m gate.env_check --role …` | 0 | 1.07 |
| gate/guard | `python -P -m gate.guard --repo … --base … --head …` | 0 | 0.21 |
| setup | `python -m pip install --quiet -r requirements.lock` | 0 | 5.12 |
| setup | `python -m pip check` | 0 | 0.27 |
| gate/tests | `python -m pytest -q -p no:cacheprovider --ignore=acceptance --junitxml=…` | 0 | 25.96 |
| gate/acceptance | `python -P -m gate.acceptance --junit … --known-failing …` | 0 | 16.40 |
| gate/security | `python -P -m gate.security_check --bandit … --pip-audit … ` | 0 | 8.28 |
| diag/coverage | `python -m coverage run -m pytest -q -p no:cacheprovider --ignore=acceptance`; `coverage json`; `coverage report`; `gate.diag_summary coverage` | 0, 0, 0, 0 | 35.69, 0.17, 0.16, 0.11 |
| diag/mypy | `mypy --python-executable … workflow` | 0 | 2.97 |
| diag/ruff | `ruff check . --no-cache --output-format json` | **1** (diagnostic) | 0.03 |
| diag/semgrep | `semgrep scan --metrics off --config …/rules.yml` | 0 | 1.97 |
| diag/benchmark | `python tools/benchmark.py` | 0 | 3.42 |

Verdict `ready-for-human`, no reasons; all 8 mandatory gate checks and `independent-review` succeeded. The run's own conclusion is red only because of the diagnostic ruff, by design (mandatory and diagnostic checks are kept apart).

## 6. Test results and coverage

### 6.1 Baseline and final

| | Baseline `821330ff` (run 01, 2026-11-03) | Final `95f1a63` (judge run 42751543290) |
|---|---|---|
| Starter and own tests (`tests/`) | 42 passed | 482 passed, 0 failed |
| Acceptance tests (`acceptance/`, 357) | — (written later; 240 passed, 117 failed on their first real run, 42361091565) | 357 passed, 0 listed, 0 new failures, list size 0 |
| Statement coverage | 252 / 266 | 364 / 366 |
| Branch coverage | 46 / 56 | 99 / 102 (3 partial) |
| Combined coverage | 92.55 % | 99 % (98.93 %) |
| Environment | Linux x86_64, CPython 3.13.17, SQLite 3.53.1 | GitHub runner ubuntu24, CPython 3.13.15 |

The customer's passport was measured on Windows 11 with CPython 3.13.15; the baseline reproduced it exactly for tests, coverage and Bandit. The final counts are from the run's `coverage report`: 366 statements, 2 missed; 102 branches, 3 partial.

### 6.2 How the tests were checked

- Each executor PR's new tests were required to fail on the code before the fix; HQ reproduced this for the later batches (e.g. PR #43: 17 of 69 fail on the old code).
- The executor ran mutants of its own changes; **HQ did not reproduce them** (e.g. batch 13's three mutants).
- quality-gate's own suite: 2,471 tests on Linux; 243 of 243 broken versions of the gate caught.

### 6.3 Independent checks of the application

- **Outside audit** of `candidate/a` `f8c2fbc` by a clean Codex session (model Sol 6.1) under a separate Windows user, with a 37-item property list: 1,349 cases, 1,331 passed, 18 failed; 33 items held, 4 did not (B7, C9, F4, E1). HQ reran the audit's unchanged tests on Linux under two time zones: the same 18 failures. Of them, V-01 and V-02 were real (both inherited from the baseline) and are fixed (§3); the rest were V-03, a fault the audit injected on purpose, graded as a failure by HQ's own wording. On PR #43's head the same suite gives 1,343 passed and only the 6 V-03 injections failing.
- **Control:** the same suite on the baseline `821330ff` failed in every known defect group (454 failed, 99 errors, 64 real 500s).

## 7. Reviewed security findings

| Finding | Where | Decision |
|---|---|---|
| B608, SQL by string formatting (MEDIUM) | baseline Bandit | fixed (PR #11) |
| SQL injection in search with disclosure of other members' tasks and every user's token (D1) | found by the spec-derived acceptance tests | fixed (PR #28). **The gate's scanners never flagged it** (Bandit, semgrep, pip-audit, gitleaks), only the contract tests did |
| Any task readable by ID (VIS) | found by the executor and the acceptance tests | fixed (PR #26) |
| CSV export and spreadsheet formulas (CWE-1236) | seen while fixing PUB-02 | **not changed**: SPEC.md does not ask for formula neutralization and the export must return titles exactly; a question for the customer (§15) |
| Dependencies pinned without hashes | `requirements.lock`; pip-audit warns; proof 5 | not changed (customer material); a dependency change needs the code owner |
| Final run | Bandit 0 results; semgrep 0 findings; pip-audit "No known vulnerabilities found"; gitleaks "no leaks found" | clean |
| ruff (diagnostic) | 51 findings, mostly import order (I001 18), FastAPI defaults (B008 10), `UTC` alias (UP017 12) | not acted on: style, diagnostic class |
| Secret-shaped strings in the evidence | 20 lines in the operator's logs | all synthetic test fixtures (keys of 9–144 characters, a token of 3 distinct characters, test names); no real secret. **No key or token is stored in GitHub** (DEV-06) |

## 8. Control proofs (TASK item 6), each on a demonstration PR closed unmerged

| # | Proof | Result | Evidence |
|---|---|---|---|
| 1 | A direct push to `main` | refused: GH013, protected ref | `part-3/proofs/1-push-to-main/` |
| 2 | A PR with a failing mandatory check while the executor's text says "ready" | `gate/final` failure, verdict `blocked`; PR #4 cannot merge | `part-3/proofs/2-failing-check/` |
| 3 | A judge run cancelled midway | verdict `incomplete`; its evidence still archived (run 42386819911) | `part-3/proofs/3-cancel-incomplete/` |
| 4 | An executor push touching `.github/workflows/` | the model declined; two barriers remain: GitHub refuses an app without the workflows permission, and the guard refuses protected paths | `part-3/proofs/4-workflow-push-refused/` |
| 5 | A dependency change | needs the code owner; PR #5 blocked (run 42388191348); the guard also red (`DEPENDENCY_NO_HASH`) | `part-3/proofs/5-dependency-codeowner/` |
| 6 | A force push and a delete of `reports` | both refused | `part-3/proofs/6-reports-protected/` |
| 7 | A broken environment (a wrong OS pin) | `gate/env` failed with the right message (run 42389359889); restored by PR #8 | `part-3/proofs/7-broken-env/` |

Tested code and configuration: quality-gate `906ebae` (proofs 2–7) and the `candidate/a` commits named in each folder.

## 9. Merges into `candidate/a` and every bypass

26 merges before this file's own PR, all by the customer's account (GitHub rule suites, `rule-suites-summary.txt`):

- **13 normal merges** of executor PRs, each with the code owner's approval and every required check green: #11, #13, #15, #18, #21, #24, #26, #28, #30, #33, #37, #40, #43.
- **13 merges by the repository owner's bypass** (each recorded by GitHub as `bypass`):
  - #1 — the blind acceptance tests (`acceptance/` only): `gate/security` was red on every PR until B608 was fixed by #11;
  - #2, #3 — pins of quality-gate after the first real runs found three gate defects;
  - #6, #8 — proof 7's break and restore;
  - #17, #20, #22, #31, #34, #38, #41 — the executor's turn limit in `quality.toml` raised for one task and set back;
  - #35 — `known-failing.txt` emptied after all 357 acceptance tests passed.
- **This file** reaches `candidate/a` the same way: the delivery documents PR (this file, the effort log and the evidence hashes) is merged by the owner's bypass, the 14th.

Why: these are the customer's own maintenance PRs to protected control files and documents. By decision W such changes go only through the code owner's maintenance PR, flagged as a bypass; the author cannot approve his own PR, and the independent reviewer is not run on them, so the required checks cannot all be green. Checked from GitHub's file lists: the 13 bypass PRs changed only `acceptance/` (#1, 10 files; #35, `known-failing.txt`), `.github/workflows/judge.yml` (#2, #3) and `quality.toml` (the other nine). **No change to `workflow/` or `tests/` entered by bypass.**

## 10. Remaining limitations

1. **The executor's local account (DEV-06).** The model runs as the Windows user that can also read the executor app's key; Windows gives it no sandbox. With the key it can act as the app on this repository only: it cannot merge, approve, or change settings or workflows. Accepted and disclosed (D-13).
2. **The launcher runs on Windows only and outside `make check`.** It is published in quality-gate `launcher/` (PR #1, merge `ffa026ad`, 2026-11-10 09:03:30), with its contract, a README and its own tests (431 passed, 8 skipped on Windows); quality-gate's self-test does not run them, and the laptop's own paths in its documents and tests were replaced by placeholders.
3. **`make reproduce` was not run on a GitHub-hosted runner** in this pilot. Independent reproduction of the application's tests was done instead by the outside audit and by HQ's reruns.
4. The launcher's example configuration and contract still show `["claude"]` as the model command, and its preflight does not start that command; on Windows the full path to `claude.exe` is needed (O-13).
5. `setup_apps.py` reads GitHub's 404 for a private app as "no such app", so a rerun could create a duplicate (O-14).
6. The judge depends on GitHub's release downloads; three runs failed on GitHub's 504 and the gate failed closed (`incomplete`); the customer reran them.
7. The turn limit is one value for all tasks in a protected file, so a large task needs a maintenance PR (seven of them here); the measured turns were 40 to 94.
8. The idempotency table needs SQLite ≥ 3.37; keys from before the upgrade are not carried (they lived in memory).
9. The executor's own mutants were not reproduced by HQ; one executor run overstated its test count (13 claimed, 12 counted).
10. The benchmark is a diagnostic; its numbers come from different machines and are not a performance claim. DISC-01 stands for the recorded command.
11. The transfer check on a second application has not started; it needs a separate authorization.
12. quality-gate's own list: L1–L50 in `docs/LIMITATIONS.md`.

## 11. Raw logs and their hashes

By the customer's decision, the operator's raw logs stay on the candidate's laptop and are given on request; this file carries their hashes.

- **Public:** every judge run's archive (reports, exit codes, logs, `SHA256SUMS`) is on the `reports` branch of gate-practice-app: head `4c4f1d63cf66dd231a7ad094aaa84b6059df967c`, 1,344 files, 15,170,870 bytes. 31 judge runs in all, failed attempts included.
- **On the laptop**, hashed file by file:
  - `SHA256SUMS-gate-practice-app-evidence-local.txt` (SHA-256 `90cb5e71d380c385c659bc9bdbad8520d7cb7bda318a6a7e347f974749487fed`): 1,216 files, 15,381,878 bytes (Part 2: 98, Part 3: 89, Part 4: 1,029);
  - `SHA256SUMS-quality-gate-evidence-local.txt` (SHA-256 `2ea53220d964688866b49be584bbf8569537af08ebc05b5f0d68e6a8ae395156`): 124 files, 3,834,262 bytes (Part 1 reviews, whole runs, mutants; the customer's answers; the test registry).
  - Not covered: the launcher's own run logs under the executor's Windows user (not read by the hashing step).
- Both lists and the two archives' `.sha256` files are on `candidate/a` under `evidence/delivery/`.

## 12. Effort and cost

**What counts toward the 20-hour cap.** Only the customer's own active minutes (decision Y, 2026-11-03). Automated wall time is a separate cost line. This is our reading of TASK.md, stated plainly; the employer was not asked.

**The customer's active time:** not measured. His own estimates: "not more than 2 hours" for the whole project to 2026-11-08 13:34, and about 30 minutes on the night of 2026-11-09/10; the delivery's reading and merges on 2026-11-10 are not estimated. Total: **about 2.5 hours (an estimate) of the 20-hour cap, plus the delivery morning.**

**His manual touches, counted from the evidence:**

| Touch | Count | What blocked unattended progress |
|---|---|---|
| Starting the executor through the launcher | 17 (7 + 7 + 3 on days 5–7; one stopped at once on `BRANCH_EXISTS`) | no model credential is stored in GitHub (DEV-06), so no Actions event can start the executor |
| Starting the independent reviewer | 16 (4 + 7 + 5) | the reviewer's key is a local file, for the same reason |
| Approving and merging an executor PR | 13 | human acceptance, by design |
| Merging a maintenance PR by bypass | 13, and 1 for this file's PR | protected control files change only by the code owner (§9) |
| Merging the launcher's PR in quality-gate | 1 | the owner's acceptance, by design |
| Word to open an issue, in Claude Code's window | 14 | by design: the customer chooses each task |
| Rerunning a whole judge run after GitHub's 504 | 3 | GitHub's release downloads |
| One-time setup | app creation (2 runs of the setup script), the Actions policy and "Restrict actors", sign-ins, two folder permissions, two messages to the outside auditor | first setup |

**Machine time (separate from the cap):**

| Actor | Time | Source |
|---|---|---|
| Claude Code on the laptop (builds the gate, follows PRs, reads back merges, gathers the delivery's facts) | about 42 h 40 min to row 57, partly approximate; one stretch on 2026-11-07 not timed; plus 46 min of waiting on 2026-11-03; the delivery's last steps (this file's PR, the delivery PR) are in the HQ copy of the log | `evidence/effort-log.csv` rows 6–57 |
| The executor (Claude, under its own Windows user) | at least 2 h 24 min 53 s over the 10 timed runs of 17; 608 turns over the 9 runs of days 6–7 | rows 38, 43, 49 |
| The independent reviewer (Codex) | not measured | rows 39, 44, 50 |
| The outside auditor (Codex, Sol 6.1) | 32.39 min | row 51 |
| HQ (Claude, planning, review, logs) | not measured as active time | the HQ rows |

**Charges:** no new charges, and none to the customer. Existing subscriptions were used: Claude Max (HQ, Claude Code), a Claude subscription signed in under the executor's user, ChatGPT (Codex reviewer and auditor; the audit used about 30 % of a 5-hour window). GitHub Actions ran on a public repository. Shares of each subscription: unknown.

**Pre-trial preparation** (declarations, design v0.2–v0.5) is not counted here; no training application was used (decision M).

**The published effort log** (`evidence/effort-log.csv`, rows 1–59) is the candidate's log with one change, by the customer's decision: in four rows the operator's Windows user name is replaced by "the operator's user". The original stays on the candidate's laptop (SHA-256 `fa4df03174330cf6e98b15d80652b61725715e6dc7b2dc016070dbbc3290a361`); the published copy's SHA-256 is `601b1145075c407673648e21513f626dc9eb9d2c548b40ddb57e7f62d9e598ed`.

## 13. Reproducibility steps

1. **The pipeline.** Clone `XThoughtLabs/quality-gate` at `ffa026a` (the judge's pin `906ebae` plus `launcher/`); `make check` runs its own tests (Linux; the self-test workflow does the same on `ubuntu-24.04`). Setup, accounts and the environment table: `REPRODUCE.md`.
2. **The application.** From the source archive (§1) or `git checkout 95f1a63`: `python -m pip install -r requirements.lock`, then `python -m pytest -q --ignore=acceptance` (482 pass) and `python -m pytest -q acceptance` (357 pass). Coverage and the security tools as in §5.
3. **The judge.** Any PR into `candidate/a` starts `judge.yml`; the verdict is the required check `gate/final`; the report is archived to the `reports` branch. `make reproduce REPO=<url> SHA=<sha>` reruns the deterministic checks in the pinned container and compares the report (needs Docker; §10 item 3).
4. **The executor.** Set up the launcher from quality-gate `launcher/` as its `README.md` and `INSTRUCTION-CEO.md` say; then a task issue and, as the executor's Windows user: `python -I <launcher>\xtl_launcher.py task --issue <n>` (§10 items 2 and 4).
5. **The independent reviewer.** In the operator's own window, with the reviewer app's ID, installation ID and key path set: `python -P -m gate.review_local --repo OWNER/NAME --pr N --sha <head> --issue N --out review.json` (`REPRODUCE.md` §3).
6. **Acceptance.** The code owner approves and merges; nothing merges with a red mandatory check without the owner's recorded bypass.

## 14. Disclosures and deviations

- **DISC-01.** The customer's recorded benchmark command fails in a clean environment (`ModuleNotFoundError: workflow`); our runs set `PYTHONPATH=.`. Not changed in the application.
- **AA-01 / DEV-02.** Three permissions beyond the approved table, authorized by the customer before work: `archive` `checks: write`; `publish` `actions: read` and `contents: read`. No `actions: write` anywhere.
- **DEV-01.** XThoughtLabs on GitHub is a personal account, not an organization. No organization-only feature is used.
- **DEV-03.** The candidate's HQ had read a second candidate's pre-start defect hypotheses and, while freezing its result, saw some of its folder names (no content). That candidate's material was fenced off: never given to Claude Code or the executor, not used in our search, which stayed general. After our search had ended (2026-11-08, PR #33), the customer approved a comparison (2026-11-10): HQ reproduced four of its findings independently on our code; our executor fixed them from HQ's own issue text (F-1 to F-4, marked *comparison* in §3). The outside auditor's two disclosed process deviations: a file-name search over the parent folder that walked the names of that candidate's folder (no match, no content read), and temporary files first written beside the repository copy (moved, hashes unchanged).
- **DEV-04.** HQ once ran `git log` and `git status` from the laptop's shared-folder VM, against its own rule; no lock file was left. HQ reads `.git` as text since.
- **DEV-05.** In quality-gate's review rounds 3–6 the repair began before the blind test author started (by 14 s to 17 min); the tests were committed first only by order. The author never saw the code, and its tests still found faults in the repairs.
- **DEV-06.** The executor and the blind spec-test author run on the laptop, not in GitHub Actions; no secret or variable is stored in GitHub. Its risk: §10 item 1.
- **R.** The reviewer-triggered fix round starts from the reviewer bot's comment, not from a `status` event (the pinned action rejects `status`); no permission added.
- **Y.** The reading of the 20-hour cap (§12).
- **D-08.** The acceptance tests were written from SPEC.md only, with no OpenAPI file derived from the code.
- **Models.** Claude Code (Claude models) built the gate; Part 3 ran on Opus 4.8 after Opus 5.5's safeguards stopped the security-testing plan; Part 4 ran on Opus 5.5. The executor is Claude Code; the reviewer and the auditor are Codex. Decisions taken in Claude Code's window are transcribed in its `HQ-ANSWERS-*` files.

## 15. What the customer decides

1. The delivery PR `candidate/a` → `main` stays open; merging it is the customer's choice.
2. `candidate/a` is the default branch for the trial; whether to restore `main` as default.
3. The judge's "Restrict actors" policy (only the owner and the executor app may trigger it) stays until write rights are settled.
4. CWE-1236: whether the CSV export should neutralize spreadsheet formulas, which would change returned titles.
5. DISC-01: whether to fix the benchmark command.
6. The transfer check on a second application: its scope and time, before it starts.

## 16. Round 2: the customer's two findings (2026-11-10 to 2026-11-12)

> Written by HQ on 2026-11-12. Figures come from the files and runs named beside them.

**The customer's answer to the delivery** (2026-11-10 10:16): all 16 of the customer's hidden tests passed; two defects reproduced in the customer's independent check block acceptance and are to be fixed in one round:
1. **Read after revocation.** A request to the status history or the work log that began before an assignment was removed could return records created after the removal. A regression check for both routes, with that order of operations, was asked for.
2. **A premature final status.** In run 42751543290 `ready-for-human` appeared before the mandatory independent review. The final status must appear only after a successful archive and all mandatory checks on one commit, and a missing, failed or other-commit review must block it.

For re-acceptance: the fixed commit's SHA, links to the run and its archive, and the fixes through the open delivery PR #45 against the frozen `main`.

### 16.1 What changed (identity)

| Item | Value |
|---|---|
| Fixed application commit | `candidate/a` = `7ca3ec7f0aecbada02b8d7b0aedb29977cdd35fa` (PR #48's merge, 2026-11-12 00:57:00) |
| Judge pin | quality-gate `76ab28b940b0992f4a37c436b12b023ece4fcd52` (PR #2's merge, 2026-11-11 04:58:55; self-test green on it, run 42949652058, 2,756 tests), called by `judge.yml` and by the new `finalize.yml` on `candidate/a` since PR #46 (merge `fd0af0d7330af9064206243d0e12758ada17080f`) |
| Baseline | `main` = `821330ffbb19f545fb81f3c223b0a286ff6c4980`, untouched |
| Delivery PR | #45, `candidate/a` → `main`, still open |
| This section | reaches `candidate/a` by a documents-only maintenance PR; the application code at its merge equals `7ca3ec7` |

### 16.2 Defect 1: a read that began before an assignment was removed

- **Cause** (HQ, by reading the code at `c2d66819`): `GET /tasks/{id}/work` and `GET /tasks/{id}/history` checked the task's visibility in one database read and read the records in a second one. A removal of the assignment and a new record committed between the two reached the former assignee.
- **Fix** (issue #47, PR #48, written by the executor; 3 files: `workflow/service.py`, `workflow/store.py`, a new test file). Each route still refuses a missing or unreadable task first. Then the task's row is judged again and the records are read in one SQLite read transaction: an explicit `BEGIN`; with the rollback journal, the shared lock taken by its first read is kept to the end, so no write can commit in between. Schema, journal mode and connection settings are unchanged.
- **Tests** (`tests/test_records_read_in_one_snapshot.py`, 20 cases):
  - 4 regression cases, work and history, with the assignment removed to no one and to another member. Threading events fix the order, with no sleeps: the request's check passes, then the administrator removes the assignment and commits a new record, then the request reads. On the fixed code the former assignee gets 404 with `{"detail":"task not found"}`;
  - 2 store cases prove the single transaction: a write that tries to commit inside the check is refused, "database is locked";
  - 2 store cases for a missing task or an id outside SQLite's range;
  - 12 controls: with no removal the member's answer holds the new record; the administrator's and the observer's answers are unchanged.
- **The tests catch the defect**, reproduced by HQ before the merge, outside GitHub (Windows 11, CPython 3.13.15, the 30 pins of `requirements.lock`; `evidence-local/part-4/issue-47/hq-check-*`):
  - on the code before the fix (`fd0af0d`), 8 of the 20 fail: the 4 regression cases with 200 and the record committed after the removal, the 4 store cases with `TypeError`;
  - on the fixed code, all 20 pass;
  - a mutant without the `BEGIN` fails the 2 store snapshot cases;
  - a mutant without the second check fails the 4 regression cases.
  
  The executor ran the new file ten times in a row: 20 passed each time.
- **The judge** (run 43109775459, head `ef6387aa27b2d12f0a6e2b3aac3e086a188aa4af`): 502 tests (482 + 20), no failure; acceptance 357 passed, 0 listed, 0 new failures; security tools no findings; changed lines covered 21 of 21; the independent review (Codex) passed with no findings.

### 16.3 Defect 2: the final status before the independent review

- **Cause:** at quality-gate `906ebae`, the judge's archive job set `gate/final` from the preliminary verdict and the archive alone; the independent review only informed the report. In run 42751543290, `gate/final` became success at 03:50:50Z, and the review came at 03:59:45Z. The merge itself still waited for the review (the ruleset requires `independent-review`).
- **Fix** (quality-gate PR #2, merge `76ab28b`; rules FN-1 to FN-9 in `docs/CONTRACTS.md` §8.5):
  - `gate/final` success (`ready-for-human`) only when all of these hold on one commit, the PR's head: the archive is complete; each mandatory check's newest run is green; the newest `independent-review` status is a success created by the reviewer's bot account;
  - a ready gate whose review is missing or pending leaves `gate/final` **in progress**, "waiting for the independent review on <sha>"; a failed review gives `blocked`;
  - a new reusable `finalize.yml`, started by `status` events, decides again for the head. Its permissions are exactly `checks: write`, `contents: read`, `pull-requests: read`; it uses no secret and runs no PR code;
  - FN-9: the newest review decides last. Every success post re-reads the newest review just before and just after it. A failed read keeps `gate/final` in progress, and a failed post is tried once more.
- **Evidence in quality-gate:**
  - the tests were written before the code. On the old code the archive chain posted success with no review at all, reproducing the finding;
  - self-test: 2,756 passed on Linux at the PR's head `725c02f` and on the merge;
  - 85 mutants of the new code (groups FIN, 52, and FN9, 33), all killed, each kill confirmed by the killing test alone;
  - four rounds of fresh reviewers (one on the whole change, three narrow ones on the repair of its medium finding M-1); every medium finding was repaired before the merge; all the findings are recorded as L53 and L57–L76 in `docs/LIMITATIONS.md`.
- **On real runs in gate-practice-app:**

| Case | What GitHub shows | Evidence |
|---|---|---|
| Review missing | PR #48, head `ef6387aa`: `gate/final` in progress from 22:17:40Z, "waiting for the independent review on ef6387aa…"; the stored `final.json` has verdict `awaiting-review`, reason `REVIEW_MISSING` | [judge run 43109775459](https://github.com/XThoughtLabs/gate-practice-app/actions/runs/43109775459); [its archive](https://github.com/XThoughtLabs/gate-practice-app/tree/75aa46224ead868b5982ead9ef5ec67a011f2c00/reports/48/43109775459-1) |
| Review on the same commit | `independent-review` success at 22:30:50Z, then finalize, then `gate/final` success, "Final verdict: ready-for-human", at 22:31:13Z | [finalize run 43112390498](https://github.com/XThoughtLabs/gate-practice-app/actions/runs/43112390498) |
| Review of another commit | demonstration PR #49, closed unmerged: commit 1 `b5f1c285` reviewed, so `gate/final` success on commit 1 only; commit 2 `c7e0bf39` left `gate/final` in progress and never completed; no status and no finalize run on commit 2 | [PR #49](https://github.com/XThoughtLabs/gate-practice-app/pull/49); judge runs 43118092138 and 43120170533; finalize run 43119085287 |
| Review failed | shown by quality-gate's tests only (`tests/spec/test_final_after_review.py`): an honest reviewer cannot be made to fail on demand, so the customer chose tests over a staged run | quality-gate PR #2 |

### 16.4 Merges and bypasses in round 2

- **quality-gate PR #2** (the gate's change) was merged by the owner on 2026-11-11 at 04:58:55. Its description was corrected before the merge, so that it matches the code.
- **gate-practice-app:**
  - **#46** (maintenance: the judge's pin and the thin `finalize.yml` caller): the owner's bypass, **the 15th**. It was merged at 05:11:35, while its own judge run was still running. That run used the old pin from the default branch and later posted `gate/final` success with no review: the behaviour this round replaces.
  - **#48** (the executor's fix): the owner's bypass, **the 16th**, and the first executor PR of the pilot merged by bypass. All 9 required checks and the independent review passed; the only rule not met was the pull-request rule, which was waiting for the code owner's approving review. The bypass button was used by mistake. The owner's sign-off, written after HQ's check, is a comment on the PR: [comment 6809271327](https://github.com/XThoughtLabs/gate-practice-app/pull/48#issuecomment-6809271327). With #48, §9's sentence "No change to `workflow/` or `tests/` entered by bypass" is no longer true.
  - **#49** (the demonstration): closed unmerged; its branch is kept.
  - **This section's PR** (documents only): the owner's bypass, **the 17th**.
- The gate's own reports list every bypass merge; PR 46 and PR 48 appear there.

### 16.5 New limitations

1. **The executor's turn limit.** The run for issue #47 reported 90 turns under `--max-turns 80`, with result `success`. The launcher passes the flag as its contract says (LR-26); why Claude Code did not stop at 80 is not known. The 60-minute timeout is the bound that held: the run took 17 min 10 s.
2. **A superseded `gate/final` stays in progress.** finalize posts a new check run instead of completing the waiting one. GitHub's check list and the required check use the newest run (PR #48's required checks were green), but the history keeps an open run.
3. **What remains of the race after FN-9** (quality-gate L53, L65, L67–L69, L73–L75): a post that GitHub refuses twice, or a run that GitHub never starts, can leave a success newest at that moment. The other cases never show green. The ruleset's own `independent-review` requirement still blocks the merge.
4. **A failed review was not shown on GitHub**, only by tests (16.3).
5. **The customer's 16 hidden tests were not rerun by us** after round 2; our own 502 tests and the 357 acceptance tests pass on the fix.

### 16.6 Effort in round 2

- **The customer's active time:** not measured.
- **His touches, counted from the records:**
  - 17 answers to Claude Code's questions in its window, and 8 to HQ's questions, in 6 sittings;
  - 8 task messages pasted to Claude Code;
  - 1 executor start and 2 reviewer runs;
  - 3 merges (quality-gate PR #2, #46, #48), and 1 for this section's PR.
- **Machine time** (separate from the cap; from the readings in the records):

| Actor | Time |
|---|---|
| Claude Code on the laptop: the gate's change (2 h 17 min 46 s, not counting a pause of 1 h 18 min 1 s), the repair of M-1 (4 h 14 min 8 s), the texts, the caller and the read-backs (32 min 59 s), batch 14 with HQ's check (1 h 14 min 37 s), the sign-off and the demonstration (33 min 29 s) | 8 h 52 min 59 s |
| The executor, issue #47 | 17 min 10 s, 90 turns |
| The independent reviewer (Codex), 2 runs | not measured |
| HQ (Claude) | not measured as active time |

- **Charges:** none new, and none to the customer; the same subscriptions as in §12.

### 16.7 What the customer decides now

1. Re-acceptance of round 2 on the fixed commit `7ca3ec7`, in the delivery PR #45, which stays open.
2. Whether the executor's turn limit needs a check of its own (16.5, item 1).
3. Whether finalize should complete the waiting `gate/final` run instead of posting a new one (16.5, item 2).

## 17. Round 2b: the customer's re-acceptance and the fix of its finding (2026-11-12)

> Written by HQ on 2026-11-12. Figures come from the files and runs named beside them.

**The customer's re-acceptance** (2026-11-12; `evidence-local/round-2/customer/WORKFLOW-API-CANDIDATE-A-ROUND2-ACCEPTANCE.RU.md` on the candidate's laptop):
- **Defect 1 accepted.** The customer's 16 hidden tests passed, and so did the application's 502 tests and the 357 acceptance tests. Its own four scenarios for history and the work log, in SQLite's DELETE and WAL journal modes, returned 404 after the removal and a later record.
- **Defect 2: the original case fixed, the requirement not fully closed.** After FN-9 the success post re-read only the newest review. The mandatory checks were read once, for the decision, so a newer `gate/tests` with failure on the same SHA, arriving after that read, did not stop `gate/final` success and `ready-for-human`. This held in both paths (the archive job and finalize). The customer reproduced it with a test against the gate's own GitHub stand-in; the ruleset's own required `gate/tests` still blocked a normal merge.
- **Process.** The customer asked for explicit decisions on PR #48's bypass (16.4) and on how the declared turn limit is enforced (16.5, item 1).

**The customer's decisions** (the customer, 2026-11-12, word for word):
- On PR #48's bypass, to «Как заказчик: обход правил при слиянии PR #48 (все проверки и рецензия пройдены, не было только одобрения владельца до слияния, подпись дана после) — признаёте исключением?»: «Признать исключением (Recommended)». The bypass is an accepted exception.
- On the turn limit, to «Как заказчик: лимит ходов исполнителя (80) запускатель только передаёт Claude Code и сам не проверяет; в пакете 14 было 90. Что делаем?»: «Принять как ограничение (Recommended)». The 60-minute timeout is the hard bound. Claude Code itself holds the turn limit, and it exceeded it once (90 under 80). A check in the launcher is recorded for the future.

### 17.1 What changed (identity)

| Item | Value |
|---|---|
| Fixed application commit | still `7ca3ec7f0aecbada02b8d7b0aedb29977cdd35fa`; this round changed no application code |
| Judge pin | quality-gate `21b42312fb92bf428831d4420bd185c6e5f584f5` (PR #3's merge, 2026-11-12 07:16:31; self-test green on it, run 43160291435, 2,883 tests), called by `judge.yml` and `finalize.yml` on `candidate/a` since this section's PR |
| Delivery PR | #45, `candidate/a` → `main`, still open; `main` = `821330ff…`, untouched |
| This section's PR | the new pin in both workflows and this section, one maintenance PR merged by the owner's bypass, the 18th |

### 17.2 The fix: FN-10, a success re-reads every condition of the decision

quality-gate PR #3 (merge `21b4231`; `docs/CONTRACTS.md` §8.5: FN-10, with FN-1, FN-4, FN-9, "One decision" and the commands amended):
- **The decision made again.** Just before every `success` post, just after it, before a second try and after a second failure, the gate reads the SHA's statuses and its check runs again (`filter=all`, every page) and runs the one decision, `gate.report.final_decision`, again. Both paths do this, `post-final` in the archive job and finalize. A decision that no longer allows the success is posted instead of it (before) or after it (after).
- **An unfinished mandatory run waits.** A newest mandatory check run that is queued or in progress keeps `gate/final` in progress (`CHECK_NOT_COMPLETED`, "waiting for the mandatory checks on <head>"); it used to count as missing.
- **The archive job's own `gate/archive` is read again too** (the reviewer's medium finding F1). The job's own value stands only while the API lists no newer `gate/archive` than the job's own post, judged by the id of GitHub's answer to that post.
- The waiting `gate/final` for the review no longer says that the gate's checks passed. No workflow file changed.

**Evidence** (`evidence-local/round-2/gate/r2b-*` on the candidate's laptop):
- The tests were written before the code. The customer's test from its report is in `tests/spec/test_employer_round2.py`: the block's text, with its two line endings normalized to LF. `tests/spec/test_final_all_conditions.py` adds 121 tests for both paths:
  - a newer mandatory run that is not completed between the read and the post;
  - a newer failed or unfinished run just after the success post;
  - every mandatory check;
  - a success post that fails;
  - the archive job's own `gate/archive`;
  - controls.
  On the code before the fix (`76ab28b`) they fail for the right reason, and every test that passes there is a named control.
- 60 mutant results, all killed, each kill confirmed by the killing test alone: 41 for the changed functions, 17 for the repair of the review's findings, 2 for the direction of F1's id comparison.
- Whole suite on the laptop: 2,868 passed, 9 skipped (Windows-only). Self-test on Linux: 2,883 passed at the PR's head and on the merge.
- One round by a fresh reviewer: one medium (F1) and four lows. F1 to F4 were repaired; F5 is kept as a limitation with no workflow change (L77). A narrow check on the repair found no high or medium, and four lows. The direction of F1's id comparison was then pinned by tests (L85), and three texts were corrected (L82 to L84).
- Light research: GitHub's reruns of the judge (all jobs, the failed jobs and their dependents, one job and its dependents) and a reopened PR end with the archive job's `gate/final`, posted after it has read the check runs.
- Not staged on GitHub: a newer red check between a read and a post cannot be produced honestly on a live run, so tests show it, as for a failed review (16.3).

### 17.3 Limitations updated

1. **What FN-10 does not follow** (quality-gate L77): the window between the last read and the post; failed posts and lost runs; a change after which nothing posts. The remainders of L53, L65, L67 to L69 and L73 to L75 now name a newer failed or unfinished mandatory check next to API failures and lost events. The ruleset's own required checks and `independent-review` still block a merge.
2. **The turn limit** (16.5, item 1) is accepted by the customer as a limitation; see the decision above.
3. **The archived `final.json`** shows the state at archiving (for PR #48, `awaiting-review`). The decision made later is in the newer `gate/final` check run and in finalize's log (16.5, item 2).

### 17.4 Merges and bypasses in round 2b

- **quality-gate PR #3** was merged by the owner on 2026-11-12 at 07:16:31.
- **This section's PR** in gate-practice-app (the pin and this section): the owner's bypass, **the 18th**.

### 17.5 Effort in round 2b

- **The customer's active time:** not measured.
- **Touches, counted from the records:**
  - 3 answers to HQ's questions;
  - 7 answers to Claude Code's questions;
  - 3 task messages pasted to Claude Code;
  - 2 merges (quality-gate PR #3 and this section's PR).
- **Claude Code on the laptop:** 4 h 3 min 28 s, from its first reading at 03:20:32 to the read-back of the merge at 07:24:00, the reviewers' rounds included. No executor run.
- **Charges:** none new.

### 17.6 What the customer decides now

1. Re-acceptance of defect 2 on quality-gate `21b4231`, with the application unchanged at `7ca3ec7`, in the delivery PR #45, which stays open.
