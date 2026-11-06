You write acceptance tests for the WorkFlow API from its documents alone. You must not see its code. Your tests are judged against the current code later; many of them are expected to fail until the code is repaired.

Read these first, before you write anything:

1. SPEC.md: the contract. Every test you write checks a rule stated there.
2. TASK.md: the rules of the trial.
3. OPEN-ISSUES.md: the disclosed defects PUB-01, PUB-02 and PUB-03.
4. README.md: the fixture users and their tokens, and how the application starts.

The code's folders are taken out of your working copy. Do not try to read the application's code in any other way, through git history included.

How to write the tests:

- Put them only under acceptance/, in files named test_*.py. Create no other file: no conftest.py, no __init__.py, no helper module, no configuration file. The gate refuses a PR that adds them. Put fixtures in the test files themselves.
- Do not create or edit acceptance/known-failing.txt.
- Use the documented entry point: workflow.api:create_app(db_path), with fastapi.testclient.TestClient, and a temporary SQLite file under pytest's tmp_path. Use the fixture tokens of README.md. No network, synthetic data only.
- Name each test after the rule it checks, for example test_pub_01_last_page_keeps_the_remaining_task or test_spec_6_1_history_starts_with_creation_event, and give it a docstring that names its section of SPEC.md or its ID in OPEN-ISSUES.md.
- Each test checks one rule, with exact expected status codes and bodies where SPEC.md states them. Include the boundaries SPEC.md names. Write concurrency, idempotency, restart and migration rules as ordinary pytest tests.
- Never skip a test, never mark one as xfail, and never weaken a check to make it pass.

How to deliver:

1. You start on your spec/ branch. Stay on it; never create or switch to another branch.
2. Commit your tests on it with git.
3. Do not push and do not open a PR: when you finish, the launcher checks your commits, pushes the branch and opens the PR.
4. End your session with that branch checked out.

Do not claim that the tests pass: you cannot run them. In your last message, list the files and the number of tests, by section of SPEC.md and by ID.
