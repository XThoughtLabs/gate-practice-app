"""Part 3 proof 2 (demonstration only, never merged).

A deliberately failing test, so the quality gate's mandatory gate/tests check turns red while
the PR's description claims the work is "ready". The gate must block the merge regardless of
that claim. This file is removed with the branch after proofs 2 and 3; it never reaches
candidate/a.
"""


def test_demo_intentional_failure():
    assert False, "Part 3 proof 2: a deliberately failing mandatory check"
