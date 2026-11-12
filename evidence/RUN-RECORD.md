# Baseline run 01 — WorkFlow API, before any edit

- Pilot clock started: 2026-11-03 12:56:44 Asia/Jerusalem (10:56:44 UTC), on receipt of the customer's authorization.
- Operator: HQ (Claude in Cowork), automated, in an isolated Linux sandbox. No human action.
- Source: fresh clone of XThoughtLabs/gate-practice-app, `git archive 821330ffbb19f545fb81f3c223b0a286ff6c4980`; manifest re-checked: 29 files, 0 differences.
- Environment: see attempt-*/environment.json and pip-freeze.txt (pip freeze equals requirements.lock exactly).
- Commands: the customer's evidence/commands.json, run from the source root with the venv's python. Each log ends with an EXIT= line; numeric exit codes and durations are in exit-codes.tsv.

## Attempt 1 — failed (operator error and one reproducibility finding)
- starter-tests: exit 1, 42 errors at setup: FileNotFoundError, because the --basetemp parent directory did not exist in this sandbox. Operator error; not a product result.
- benchmark (`python tools/benchmark.py`, as recorded): exit 1, ModuleNotFoundError: No module named 'workflow'.

## Attempt 2 — completed
- Parent directory for --basetemp created; nothing else changed.
- Results equal to the customer's passport: 42 passed (1 warning); statements 252/266; branches 46/56; combined 92.55%; Bandit exit 1 with one B608 MEDIUM/MEDIUM at workflow/store.py:121; pip check exit 0.
- Benchmark as recorded: exit 1 again (ModuleNotFoundError). With `PYTHONPATH=.`: exit 0. This is a reported discrepancy, not a fix (DISC-01).
