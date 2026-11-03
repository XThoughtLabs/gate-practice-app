# Open defect reports

These are the disclosed reports, not the complete defect list. Reproduce them on the frozen baseline, provide a focused fix and regression test, and report any discrepancy in the customer-provided material.

## PUB-01 — the last page can lose a task

With an empty temporary database, Alice creates three tasks. Request `/tasks?limit=2&offset=2` as Alice. The remaining third task must be returned. The total must still be three. Check related empty/one-item/exact-page boundaries.

## PUB-02 — CSV export corrupts structured titles

Create a title such as `Review, phase "B"` and export tasks. A standard CSV parser must recover the original title in one title field and exactly the documented columns. Include Unicode and embedded line breaks in validation; do not repair CSV by stripping user content.

## PUB-03 — a negative test may accept success

The starter test for an observer creating a task is too permissive for the specification. Strengthen it and demonstrate that a deliberate permission regression makes the test fail. Preserve evidence of the unchanged implementation's result as well as the planted regression's result.

No closed defect catalog, acceptance-test source, private fixture or reference repair is supplied. You may discover other issues using the code, contract and permitted tools.
