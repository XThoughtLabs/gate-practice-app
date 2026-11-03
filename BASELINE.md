# Baseline passport — WorkFlow API v0.1.0

Measured: 2026-11-03. Purpose: a customer-prepared synthetic SDLC assessment. This is a deliberately imperfect starting state, not a security-approved product. The customer has not received or graded a candidate solution.

## Identity

The frozen application/task commit and the SHA-256 of the customer-generated source archive are given in the customer's handover message. `SOURCE-MANIFEST.json` independently lists SHA-256 and byte size for every distributed file except the manifest itself. GitHub-generated download ZIPs can have different container bytes; use the manifest to compare their extracted content.

Do not grade against a moving branch name alone. Record the actual starting and delivered commits. A document-only clarification does not silently replace this source baseline.

## Environment and dependencies

| Item | Measured value |
|---|---|
| OS | Windows 11, build 26200, AMD64 |
| Python | CPython 3.13.15, 64-bit |
| SQLite runtime | 3.50.4; ordinary rollback journal, not WAL |
| FastAPI | 0.162.0 |
| Starlette | 1.10.0 |
| Pydantic | 2.14.2 |
| Uvicorn | 0.54.0 |
| HTTPX | 0.28.1 |
| pytest | 9.2.0 |
| Coverage.py | 7.17.0 |
| Bandit | 1.9.4 |

`requirements.lock` pins the complete measured environment's application/checking dependency set. `evidence/environment.json` lists exact versions, Python build and platform. All packages were installed in an isolated environment for this exercise. Other projects and the system Python were not modified. Python/SQLite are runtime prerequisites, not pip-managed dependencies; report differences rather than claiming identical environments.

Dependency versions were checked against the publishers' PyPI release metadata and resolved together. This is not a dependency vulnerability audit or a claim that every selected release is vulnerability-free. No external AI API call or production secret was used to prepare this application.

## Starting behaviour

Four public fixture users exist; the task collection is initially empty. The intended existing contract is SPEC.md sections 1–5. Actual baseline behaviour contains faults. SPEC.md section 6 is the requested functional extension; status history is absent initially and PATCH still has its documented legacy permission.

The disclosed reports are in OPEN-ISSUES.md. The customer also holds undisclosed cases and evidence outside this repository. They exercise the published contract; they are not additional secret product requirements.

## Executed public checks

| Check | Observed result | Evidence |
|---|---|---|
| `python -m pip check` | Exit 0; no broken requirements | `evidence/dependency-check.log` |
| Starter suite under Coverage.py | **42 passed**, one deprecation warning; exit 0 | `evidence/starter-tests.log` |
| Statement coverage | **252 / 266 = 94.74%** | `evidence/coverage.json` |
| Branch coverage | **46 / 56 = 82.14%** | `evidence/coverage.json` |
| Combined coverage metric | **92.55%**; includes statement and branch opportunities | `evidence/coverage-report.log` |
| Bandit scan | Exit **1**; one MEDIUM severity / MEDIUM confidence B608 finding | `evidence/bandit.json` and `evidence/bandit.log` |
| Diagnostic benchmark | Exit 0; three repetitions | `evidence/benchmark.json` |

The Bandit report is a scanner observation requiring review. It is not a complete defect list. In particular, a scanner can flag bounded SQL construction and miss an exploitable construction elsewhere. Do not convert this nonzero baseline result into an unexplained green check or assume the absence of other findings.

Starlette warns that the HTTPX-based TestClient is deprecated in favour of its newer client. The pinned combination executed successfully. The warning is retained in the evidence; migrating the test transport is not itself an exercise requirement.

Commands, exit codes and run durations are recorded in `evidence/commands.json`. Public logs normalize line endings and replace the examiner's workstation path with `<TRIAL_ROOT>`. They otherwise preserve command output and the `EXIT=` marker. Originals are retained by the customer; the manifest hashes the distributed, explicitly redacted copies.

## Control measurements

Boundary: HTTP TestClient in-process round trip, including application and SQLite, **without TCP**, one request at a time. Dataset: 500 synthetic tasks; warm-up: 20 GET requests; three repetitions of 100 measured task reads. Clock: `perf_counter_ns`; units: milliseconds. No production performance or concurrent-load result is claimed.

| Repetition | p50, ms | p95, ms |
|---|---:|---:|
| 1 | 2.31610 | 3.04790 |
| 2 | 2.13765 | 3.17400 |
| 3 | 2.09875 | 2.62310 |

The full observations, minimum and maximum are in `evidence/benchmark.json`. There is no hidden latency rejection threshold. Use the same measurement boundary and describe machine load when comparing a later run.

## Execution limits and unverified areas

- These results were obtained on the listed Windows environment, outside the coding agent's restricted execution environment. An earlier restricted attempt stalled before a test summary and was stopped; it is not counted as a pass. A separate single-test diagnostic passed, followed by the complete recorded run.
- No Linux/macOS test run, hosted CI run, container test, external penetration test, OS power-loss test or third-party dependency advisory scan was performed.
- Authentication is a public fixture mechanism; it is not a production token-management design. This application must stay on loopback with synthetic data.
- The starter suite has known coverage gaps and at least one deliberately weak assertion. Coverage does not prove behaviour. Independent customer checks will be run on the delivery.
- The public source has no AI inference feature and incurs no model charges. The candidate selects and declares the AI-assisted tooling used for the trial according to TASK.md.
- The second transfer application is not part of this starting archive; its bounded task and time allocation will be supplied separately.

The passport records the initial condition. Passing the initial starter suite does not mean the hiring exercise has been completed.
