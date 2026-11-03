# WorkFlow API — customer-provided SDLC trial

This is a deliberately imperfect, synthetic assessment application. It is supplied by the customer, independently of the candidate's own training application. It is not a production service. Run it on loopback only. All four bearer tokens below are public demonstration fixtures, not credentials.

Start with [TASK.md](TASK.md), [SPEC.md](SPEC.md), [OPEN-ISSUES.md](OPEN-ISSUES.md) and [BASELINE.md](BASELINE.md).

## Setup

The measured baseline uses Python 3.13.15 on Windows. Exact package versions are in `requirements.lock`; direct dependencies are in `requirements.in`. Use an isolated environment.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn workflow.api:create_app --factory --host 127.0.0.1 --port 8765
```

On Linux/macOS use `.venv/bin/python` in place of the Windows executable. Those platforms are not claimed as baseline-tested unless the passport explicitly records a run there. SQLite must support STRICT tables (3.37+). Report runtime differences.

The server uses `data/workflow.sqlite3` unless `WORKFLOW_DB_PATH` specifies another file. Importing the module does not start a server or open a database; the factory creates its database when called. Tests use isolated temporary databases. `/docs` provides the OpenAPI UI; it may fetch its UI assets from a public CDN, so use `/openapi.json` or an HTTP client when working offline.

| Actor | Role | Authorization header |
|---|---|---|
| Administrator | admin | `Bearer demo-admin` |
| Alice | member | `Bearer demo-alice` |
| Bob | member | `Bearer demo-bob` |
| Observer | observer | `Bearer demo-observer` |

The baseline starts with users only and no tasks. No customer data, AI API keys or production secrets are needed. Do not bind this intentionally flawed service to a public interface.

## Useful commands

```text
python -m pytest -q
python -m coverage run -m pytest -q
python -m coverage report
python -m bandit -r workflow -f json
python tools/benchmark.py
```

Bandit findings and a green starter suite are observations, not a security certificate. The baseline contains defects that the starter suite does not cover. Preserve failed attempts and record command exit codes. The candidate may improve the public tests, but cannot remove requirements to make a check pass.

The customer holds additional acceptance checks outside this repository. No answer key or private acceptance suite is included here. The source and public task are the frozen starting material; identify your starting commit in every delivery.
