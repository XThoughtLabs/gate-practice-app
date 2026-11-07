# PUB-03 evidence: the observer-create test and a planted permission regression

Issue #16, OPEN-ISSUES.md PUB-03. Recorded 2026-11-07.

## What the test checks

`tests/test_api.py::test_observer_create` accepted `201` or `403` for an observer's `POST /tasks`, so it passed when an observer could create a task. It now checks what SPEC.md requires, and nothing more:

| SPEC.md | Requirement | Assertion |
|---|---|---|
| Section 3, `POST /tasks` | "Admin/member only" | the observer's request returns exactly `403` |
| Section 5 | `403` for a request that is authenticated but forbidden | (same) |
| Section 1 | "Observers never write." | afterwards the administrator's `GET /tasks` has `items == []` and `total == 0` |
| Section 2 | "Invalid operations must not partially modify data." | (same) |

The `detail` text of the `403` is not asserted, because SPEC.md does not fix it. The test keeps its name. No application code is changed.

## What was run

- Starter test: commit `1ce6e90fd37e50863f11dc9073b4240dd071b373`, the base of this branch on `candidate/a`.
- Strengthened test: commit `aaa7d1ce9af0191ebe65f114e2d8de7005f420d3`, the first commit of this PR. It changes only `tests/test_api.py`, so both commits have the same application code.
- Environment: Windows 11 build 26200, CPython 3.13.17, pytest 9.2.0 and FastAPI 0.162.0, installed from `requirements.lock` into a virtual environment outside the repository. The baseline passport used CPython 3.13.15.
- Method: the script below exports each commit with `git archive` into its own folder under the temporary directory, outside the repository. It changes only that copy's `workflow/service.py` and runs the test and the whole suite inside the copy. The `python -c` line in each run shows that the copy imported its own `workflow/service.py`. Nothing in the repository was checked out or changed: `git status --short` was empty after the run.

The two regressions, planted only in the copies (the diffs are in the log):

- **R1, check removed:** `Service.create` no longer calls `require_writer`. The observer gets `201` and a stored task.
- **R2, check after the write:** `Service.create` calls `require_writer` only after `store.create`. The observer gets `403`, but the task stays stored.

## Results

Exit codes from the summary at the end of the log:

| Test | Application copy | Observer test | Whole suite |
|---|---|---|---|
| starter | unchanged | 0, 1 passed | 0, 91 passed |
| starter | R1, check removed | 0, 1 passed | 0, 91 passed |
| starter | R2, check after the write | 0, 1 passed | 0, 91 passed |
| strengthened | unchanged | 0, 1 passed | 0, 91 passed |
| strengthened | R1, check removed | **1**, `assert 201 == 403` | **1**, 1 failed, 90 passed |
| strengthened | R2, check after the write | **1**, the observer's task (`creator_id` 4) is stored, `total` 1 | **1**, 1 failed, 90 passed |

No starter test detects either regression: the whole starter suite stays green under both. The strengthened test passes on the unchanged code and fails on each regression, at a different assertion each time. R1 fails at the status check and R2 at the check that nothing was stored, so both assertions are needed.

## How to reproduce

Save the script below outside the repository. Then run it from any folder with the environment's `python`, and give it an empty folder outside the repository:

```text
python plant_regression.py <repository> 1ce6e90fd37e50863f11dc9073b4240dd071b373 aaa7d1ce9af0191ebe65f114e2d8de7005f420d3 <work folder>
```

The run recorded here was:

```text
python "<TMP>\..\plant_regression.py" "<TRIAL_ROOT>\repo" 1ce6e90fd37e50863f11dc9073b4240dd071b373 aaa7d1ce9af0191ebe65f114e2d8de7005f420d3 "<TMP>"
```

Exit code 0. The script writes `raw.log` and `normalized.log` to the work folder. A rerun should differ only in durations and timestamps.

## Log

This is `normalized.log` with its Windows CRLF line endings changed to LF, because the repository stores Markdown with LF. The SHA-256 of this LF text is `c44b68218ce61fa473307ab6a70e19cdfc177bcbfc7ddc81ee00b9047404129c`. It differs from `raw.log` only in local folder names. `<TMP>` is the work folder (`%TEMP%\pub03-evidence\run`). `<TRIAL_ROOT>` is the folder that holds the repository and its virtual environment. In 24 lines, two warning lines for each of the 12 pytest runs, the virtual environment's path is shown as `<TRIAL_ROOT>\venv`. The single-test runs use `--tb=short`, which leaves the fixtures' bearer tokens out of the output.

```text
python: 3.13.17
starter commit: 1ce6e90fd37e50863f11dc9073b4240dd071b373
strengthened commit: aaa7d1ce9af0191ebe65f114e2d8de7005f420d3

===== starter test (1ce6e90fd37e), unchanged: <TMP>/starter-unchanged =====
(workflow/service.py is unchanged)

$ python -c "import os, workflow.service as s; print(os.path.relpath(s.__file__))"
workflow\service.py
EXIT=0

$ python -m pytest -q -p no:cacheprovider --tb=short tests/test_api.py::test_observer_create
.                                                                        [100%]
============================== warnings summary ===============================
<TRIAL_ROOT>\venv\Lib\site-packages\fastapi\testclient.py:1
  <TRIAL_ROOT>\venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1 passed, 1 warning in 0.11s
EXIT=0

$ python -m pytest -q -p no:cacheprovider --tb=no
........................................................................ [ 79%]
...................                                                      [100%]
============================== warnings summary ===============================
<TRIAL_ROOT>\venv\Lib\site-packages\fastapi\testclient.py:1
  <TRIAL_ROOT>\venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
91 passed, 1 warning in 3.71s
EXIT=0

===== starter test (1ce6e90fd37e), R1-check-removed: <TMP>/starter-R1-check-removed =====
--- a/workflow/service.py
+++ b/workflow/service.py
@@ -60,7 +60,6 @@
             raise Problem(422, "assignee must be an administrator or member")
 
     def create(self, user, values, key=None):
-        self.require_writer(user)
         self.assignee_exists(values["assignee_id"])
         digest = hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()
         cache_key = (user["id"], key)

$ python -c "import os, workflow.service as s; print(os.path.relpath(s.__file__))"
workflow\service.py
EXIT=0

$ python -m pytest -q -p no:cacheprovider --tb=short tests/test_api.py::test_observer_create
.                                                                        [100%]
============================== warnings summary ===============================
<TRIAL_ROOT>\venv\Lib\site-packages\fastapi\testclient.py:1
  <TRIAL_ROOT>\venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1 passed, 1 warning in 0.11s
EXIT=0

$ python -m pytest -q -p no:cacheprovider --tb=no
........................................................................ [ 79%]
...................                                                      [100%]
============================== warnings summary ===============================
<TRIAL_ROOT>\venv\Lib\site-packages\fastapi\testclient.py:1
  <TRIAL_ROOT>\venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
91 passed, 1 warning in 3.50s
EXIT=0

===== starter test (1ce6e90fd37e), R2-check-after-write: <TMP>/starter-R2-check-after-write =====
--- a/workflow/service.py
+++ b/workflow/service.py
@@ -60,7 +60,6 @@
             raise Problem(422, "assignee must be an administrator or member")
 
     def create(self, user, values, key=None):
-        self.require_writer(user)
         self.assignee_exists(values["assignee_id"])
         digest = hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()
         cache_key = (user["id"], key)
@@ -70,6 +69,7 @@
                 raise Problem(409, "idempotency key reused with a different body")
             return self.existing(task_id)
         task = self.store.create(user, values, timestamp())
+        self.require_writer(user)
         if key is not None:
             self.request_cache[cache_key] = (digest, task["id"])
         return task

$ python -c "import os, workflow.service as s; print(os.path.relpath(s.__file__))"
workflow\service.py
EXIT=0

$ python -m pytest -q -p no:cacheprovider --tb=short tests/test_api.py::test_observer_create
.                                                                        [100%]
============================== warnings summary ===============================
<TRIAL_ROOT>\venv\Lib\site-packages\fastapi\testclient.py:1
  <TRIAL_ROOT>\venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1 passed, 1 warning in 0.11s
EXIT=0

$ python -m pytest -q -p no:cacheprovider --tb=no
........................................................................ [ 79%]
...................                                                      [100%]
============================== warnings summary ===============================
<TRIAL_ROOT>\venv\Lib\site-packages\fastapi\testclient.py:1
  <TRIAL_ROOT>\venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
91 passed, 1 warning in 3.67s
EXIT=0

===== strengthened test (aaa7d1ce9af0), unchanged: <TMP>/strengthened-unchanged =====
(workflow/service.py is unchanged)

$ python -c "import os, workflow.service as s; print(os.path.relpath(s.__file__))"
workflow\service.py
EXIT=0

$ python -m pytest -q -p no:cacheprovider --tb=short tests/test_api.py::test_observer_create
.                                                                        [100%]
============================== warnings summary ===============================
<TRIAL_ROOT>\venv\Lib\site-packages\fastapi\testclient.py:1
  <TRIAL_ROOT>\venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1 passed, 1 warning in 0.12s
EXIT=0

$ python -m pytest -q -p no:cacheprovider --tb=no
........................................................................ [ 79%]
...................                                                      [100%]
============================== warnings summary ===============================
<TRIAL_ROOT>\venv\Lib\site-packages\fastapi\testclient.py:1
  <TRIAL_ROOT>\venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
91 passed, 1 warning in 3.54s
EXIT=0

===== strengthened test (aaa7d1ce9af0), R1-check-removed: <TMP>/strengthened-R1-check-removed =====
--- a/workflow/service.py
+++ b/workflow/service.py
@@ -60,7 +60,6 @@
             raise Problem(422, "assignee must be an administrator or member")
 
     def create(self, user, values, key=None):
-        self.require_writer(user)
         self.assignee_exists(values["assignee_id"])
         digest = hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()
         cache_key = (user["id"], key)

$ python -c "import os, workflow.service as s; print(os.path.relpath(s.__file__))"
workflow\service.py
EXIT=0

$ python -m pytest -q -p no:cacheprovider --tb=short tests/test_api.py::test_observer_create
F                                                                        [100%]
================================== FAILURES ===================================
____________________________ test_observer_create _____________________________
tests\test_api.py:90: in test_observer_create
    assert result.status_code == 403
E   assert 201 == 403
E    +  where 201 = <Response [201 Created]>.status_code
============================== warnings summary ===============================
<TRIAL_ROOT>\venv\Lib\site-packages\fastapi\testclient.py:1
  <TRIAL_ROOT>\venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
FAILED tests/test_api.py::test_observer_create - assert 201 == 403
1 failed, 1 warning in 0.17s
EXIT=1

$ python -m pytest -q -p no:cacheprovider --tb=no
..........................F............................................. [ 79%]
...................                                                      [100%]
============================== warnings summary ===============================
<TRIAL_ROOT>\venv\Lib\site-packages\fastapi\testclient.py:1
  <TRIAL_ROOT>\venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
FAILED tests/test_api.py::test_observer_create - assert 201 == 403
1 failed, 90 passed, 1 warning in 3.61s
EXIT=1

===== strengthened test (aaa7d1ce9af0), R2-check-after-write: <TMP>/strengthened-R2-check-after-write =====
--- a/workflow/service.py
+++ b/workflow/service.py
@@ -60,7 +60,6 @@
             raise Problem(422, "assignee must be an administrator or member")
 
     def create(self, user, values, key=None):
-        self.require_writer(user)
         self.assignee_exists(values["assignee_id"])
         digest = hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()
         cache_key = (user["id"], key)
@@ -70,6 +69,7 @@
                 raise Problem(409, "idempotency key reused with a different body")
             return self.existing(task_id)
         task = self.store.create(user, values, timestamp())
+        self.require_writer(user)
         if key is not None:
             self.request_cache[cache_key] = (digest, task["id"])
         return task

$ python -c "import os, workflow.service as s; print(os.path.relpath(s.__file__))"
workflow\service.py
EXIT=0

$ python -m pytest -q -p no:cacheprovider --tb=short tests/test_api.py::test_observer_create
F                                                                        [100%]
================================== FAILURES ===================================
____________________________ test_observer_create _____________________________
tests\test_api.py:92: in test_observer_create
    assert (tasks["items"], tasks["total"]) == ([], 0)
E   AssertionError: assert ([{'id': 1, '...: 4, ...}], 1) == ([], 0)
E     
E     At index 0 diff: [{'id': 1, 'title': 'Observer task', 'description': '', 'creator_id': 4, 'assignee_id': None, 'status': 'todo', 'priority': 3, 'due_at': None, 'work_minutes': 0, 'created_at': '2026-11-07T19:50:27.735843+00:00', 'updated_at': '2026-11-07T19:50:27.735843+00:00'}] != []
E     Use -v to get more diff
============================== warnings summary ===============================
<TRIAL_ROOT>\venv\Lib\site-packages\fastapi\testclient.py:1
  <TRIAL_ROOT>\venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
FAILED tests/test_api.py::test_observer_create - AssertionError: assert ([{'i...
1 failed, 1 warning in 0.17s
EXIT=1

$ python -m pytest -q -p no:cacheprovider --tb=no
..........................F............................................. [ 79%]
...................                                                      [100%]
============================== warnings summary ===============================
<TRIAL_ROOT>\venv\Lib\site-packages\fastapi\testclient.py:1
  <TRIAL_ROOT>\venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
FAILED tests/test_api.py::test_observer_create - AssertionError: assert ([{'i...
1 failed, 90 passed, 1 warning in 3.55s
EXIT=1

===== summary: exit codes =====
test          application copy         observer test  whole suite
starter       unchanged                            0            0
starter       R1-check-removed                     0            0
starter       R2-check-after-write                 0            0
strengthened  unchanged                            0            0
strengthened  R1-check-removed                     1            1
strengthened  R2-check-after-write                 1            1
```

## Script

```python
"""PUB-03 evidence: run test_observer_create, and the whole suite, on copies of two commits,
once unchanged and once with each permission regression planted in the copy's
workflow/service.py.

Usage: python plant_regression.py <repo> <starter-commit> <strengthened-commit> <work-dir>

The repository is only read, with git archive; nothing in it is checked out or changed.
Every copy lives under <work-dir>. Writes <work-dir>/raw.log and <work-dir>/normalized.log;
the normalized log replaces the local folders with <TRIAL_ROOT> and <TMP>.
"""

import difflib
import io
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tarfile

REPO = pathlib.Path(sys.argv[1]).resolve()
COMMITS = {"starter": sys.argv[2], "strengthened": sys.argv[3]}
WORK = pathlib.Path(sys.argv[4]).resolve()
TRIAL_ROOT = REPO.parent

CREATE = "    def create(self, user, values, key=None):\n        self.require_writer(user)\n"
CREATE_UNCHECKED = "    def create(self, user, values, key=None):\n"
STORE = "        task = self.store.create(user, values, timestamp())\n"

REGRESSIONS = {
    "unchanged": [],
    # R1: Service.create no longer checks the role, so an observer's POST /tasks is accepted.
    "R1-check-removed": [(CREATE, CREATE_UNCHECKED)],
    # R2: the role is checked only after the task is stored: 403 is returned, the task stays.
    "R2-check-after-write": [(CREATE, CREATE_UNCHECKED),
                             (STORE, STORE + "        self.require_writer(user)\n")],
}

# --tb=short keeps the assertion and leaves out the fixture arguments (the fixture tokens).
SINGLE = ["-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=short",
          "tests/test_api.py::test_observer_create"]
SUITE = ["-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=no"]
WHERE = ["-c", "import os, workflow.service as s; print(os.path.relpath(s.__file__))"]

log = []


def emit(text):
    log.append(text)


def run(arguments, cwd):
    env = {name: value for name, value in os.environ.items() if name != "PYTHONPATH"}
    shown = " ".join(f'"{a}"' if " " in a else a for a in arguments)
    emit(f"$ python {shown}\n")
    result = subprocess.run([sys.executable, *arguments], cwd=cwd, env=env,
                            capture_output=True, text=True)
    emit(result.stdout + result.stderr)
    emit(f"EXIT={result.returncode}\n\n")
    return result.returncode


def export(commit, destination):
    archive = subprocess.run(["git", "-C", str(REPO), "archive", "--format=tar", commit],
                             check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(destination, filter="data")


def plant(service, edits):
    original = service.read_text(encoding="utf-8")
    text = original
    for old, new in edits:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    service.write_text(text, encoding="utf-8")
    diff = "".join(difflib.unified_diff(original.splitlines(keepends=True),
                                        text.splitlines(keepends=True),
                                        "a/workflow/service.py", "b/workflow/service.py"))
    emit(diff or "(workflow/service.py is unchanged)\n")
    emit("\n")


def normalize(text):
    text = text.replace(str(WORK), "<TMP>").replace(str(TRIAL_ROOT), "<TRIAL_ROOT>")
    # pytest may print the virtual environment as a relative path from the copy.
    return re.sub(r"\S*?venv(?=\\Lib\\site-packages)", r"<TRIAL_ROOT>\\venv", text)


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    emit(f"python: {sys.version.split()[0]}\n")
    for label, commit in COMMITS.items():
        emit(f"{label} commit: {commit}\n")
    emit("\n")
    results = []
    for label, commit in COMMITS.items():
        for variant, edits in REGRESSIONS.items():
            copy = WORK / f"{label}-{variant}"
            if copy.exists():
                shutil.rmtree(copy)
            export(commit, copy)
            emit(f"===== {label} test ({commit[:12]}), {variant}: <TMP>/{copy.name} =====\n")
            plant(copy / "workflow" / "service.py", edits)
            run(WHERE, copy)
            single = run(SINGLE, copy)
            suite = run(SUITE, copy)
            results.append((label, variant, single, suite))
    emit("===== summary: exit codes =====\n")
    emit(f"{'test':<14}{'application copy':<24}{'observer test':>14}{'whole suite':>13}\n")
    for label, variant, single, suite in results:
        emit(f"{label:<14}{variant:<24}{single:>14}{suite:>13}\n")
    raw = "".join(log)
    (WORK / "raw.log").write_text(raw, encoding="utf-8")
    (WORK / "normalized.log").write_text(normalize(raw), encoding="utf-8")
    print(normalize(raw), end="")


if __name__ == "__main__":
    main()
```
