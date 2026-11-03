# Paid pilot: controlled AI-assisted SDLC

Customer: Vladislav. Exercise: WorkFlow API v0.1.0. Date: 2026-11-03.

## Objective

Demonstrate a repeatable process that takes a specification, changes unfamiliar code with AI assistance, checks the result, fixes confirmed defects, preserves execution evidence and stops acceptance when mandatory checks fail. Deliver a working application and an operable process. A collection of prompts alone does not establish automated enforcement.

## Starting material and repositories

The customer supplies the frozen `XThoughtLabs/gate-practice-app` baseline. Its exact commit and source-archive checksum are in the handover record. `BASELINE.md` records the environment and observed checks; `SPEC.md` is the behavioural contract; `OPEN-ISSUES.md` is the disclosed subset of defects.

Use `XThoughtLabs/quality-gate` for your reusable pipeline. Application work belongs in a candidate branch/PR against the baseline in this repository. Do not merge your delivery into the customer's baseline. Preserve its commit and all submitted evidence. Local tools are acceptable; a hosted CI product is not mandatory. Your own earlier training application is not the customer's acceptance target.

## Work

1. Record the baseline identity, environment and an initial run before edits. Name your selected models/tools and the expected evidence each will produce.
2. Build or adapt the reusable process in `quality-gate`. Keep execution, verification and human acceptance distinct. Document a repeatable entry command, configuration, per-stage outcomes, exit codes and saved logs.
3. Implement status history and restricted task modification exactly as `SPEC.md` section 6 defines. Preserve existing compatible behaviour and data.
4. Investigate and repair contract defects. For each confirmed defect provide the trigger, expected/actual result on baseline, cause, fix and regression test. Keep unresolved claims explicit. Correct the disclosed weak test and show that it detects the intended permission regression.
5. Run the whole public suite, your new tests, coverage and security/static checks. Review each actionable finding; do not silently suppress checks or weaken requirements. Preserve both failures and later successful attempts.
6. Show the process rejecting an intentionally failing mandatory check and refusing to label an incomplete/interrupted run verified. A model's “ready” response must not override a failed check. Record exact tested code/configuration commits.
7. Provide reproducible setup and a handover that another operator can follow. A second small unfamiliar application will be supplied separately for the transfer check; do not use your own training application as its substitute.

## Effort, cost and tools

The agreed planning frame remains **16–20 working hours** and **USD 500–800 for the paid pilot**. This is a range, not a selected fixed fee or a promise of a particular hourly rate. Before billable execution, confirm the chosen amount/arrangement with Vladislav. Keep an effort log; do not silently exceed 20 hours. Report a bounded partial result if the cap is reached and ask for a decision on further work.

No calendar deadline has been set. Propose a delivery date before starting the timed pilot. The date printed on this document is not a deadline.

A separate customer API-spending allowance and a specific provider/model allow-list have not been set. Declare the models/services you intend to use, existing access, expected cost and whether you require any additional customer payment. Obtain approval before new customer charges or use of a service whose authorization is unclear. Never put keys in code, reports, prompts or logs. This task uses public synthetic exercise code; it grants no access to the customer's private projects, credentials or real data.

Log human active minutes separately from automated wall time, tool/API charges, retries and pre-existing subscription use. Mark an unavailable charge as unknown, not zero. Earlier work on your own training app is disclosed separately from trial effort. The later transfer check must have its scope/time allocation agreed before it begins; it does not silently increase this pilot's cap.

## Delivery

- Application branch/PR or commit plus a source archive and SHA-256; no customer merge.
- Pipeline commit, entry command, configuration and dependency versions.
- `DELIVERY.md`: requirement-to-evidence table, defect table, changed files, baseline/final commits, commands, exit codes, test results, coverage, reviewed security findings, remaining limitations and reproducibility steps.
- Raw execution logs, including failed attempts, with hashes; diagnostics and summaries may supplement them.
- Effort and cost report; list each manual intervention and what blocked unattended progress.

## Assessment

The proposed weights remain 30% correctness/regressions, 25% defect investigation/repair, 20% automation/reproducibility, 15% security/control, 10% cost/manual effort. Each category is rated 0–4: 0 absent, 1 claim/demo only, 2 partly reproduced with material gaps, 3 reproduced within the stated scope, 4 independently reproduced with relevant negative/boundary evidence and a usable handover. Weighted points are weight × rating / 4. The score supports a hiring discussion; it does not turn a failed mandatory requirement into acceptance.

Mandatory application requirements are `SPEC.md` and the disclosed task. Customer-held acceptance tests cover that contract and are held separately. Starter tests can be changed for a justified correction or strengthening; document the reason. Removing tests, skipping failures or changing the contract to obtain a green run is not a repair.

False claims of executed checks, unauthorized data access, bypassing mandatory checks to accept a change, or a confirmed critical failure are blocking matters regardless of weighted score. A correctly reported limitation is not a falsified test result. Report issues in the exam itself before implementing a speculative interpretation; any clarification is recorded and applies consistently.

This is a limited pilot, not a request for a production-wide SDLC platform, full corporate security, deployment, custom authentication or unrelated product features.
