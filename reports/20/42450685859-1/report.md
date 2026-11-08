# Quality gate report

**Preliminary verdict: ready-for-human**

The final verdict comes after the evidence is stored: see the check `gate/final`, and `final.json` beside this report.

## Verification record

| Field | Value |
|---|---|
| repository | XThoughtLabs/gate-practice-app |
| head_repository | XThoughtLabs/gate-practice-app |
| pr | 20 |
| run_id | 42450685859 |
| run_attempt | 1 |
| event | pull_request_target |
| baseline_sha | 821330ffbb19f545fb81f3c223b0a286ff6c4980 |
| base_sha | 1290713f4b515bd34a57a275798472f70f0f1706 |
| head_sha | 59f32fddfd10faa40d21fefa09fb831e0e3a918f |
| gate_sha | 906ebaefdc10ca459ccd9c890ecb56c9b0f3acb9 |
| head_ref | maint/max-turns-120 |
| config .github/workflows/executor.yml | missing |
| config .github/workflows/feedback.yml | missing |
| config .github/workflows/judge.yml | 903e7701bb9b5a5edb9135c4fa2be227803ffca1437186480c11cf6e3f9521a2 |
| config .github/workflows/spec-tests.yml | missing |
| config CODEOWNERS | 039e179cda576eeac0ddd75086f9d1213bac9901a732a1c7dd949e17ab54db25 |
| config prompts/executor.md | 6d80c44da4d759d14f66a5c2610759bacac70e2c8a3c07165a162669a59a5030 |
| config prompts/spec-tests.md | 78e4b207926e3b5cffa38204aec5a80bc1ecc7047fa45d405e4f16351663419f |
| config quality.toml | 2aef7464abdcb815449b9a195523a1ba8578733ea39974d2e17a7643569861df |
| config security-review.md | missing |

## Reasons

None.

## Checks

| Check | Class | Conclusion | Exit codes |
|---|---|---|---|
| gate/env | mandatory | success | 0 |
| gate/guard | mandatory | success | 0 |
| gate/tests | mandatory | success | 0 |
| gate/acceptance | mandatory | success | 0 |
| gate/security | mandatory | success | 0 |
| diag/coverage | diagnostic | success | 0, 0, 0, 0 |
| diag/mypy | diagnostic | success | 0 |
| diag/ruff | diagnostic | failure | 1 |
| diag/semgrep | diagnostic | success | 0 |
| diag/schemathesis | diagnostic | success | none |
| diag/mutation | diagnostic | success | none |
| diag/benchmark | diagnostic | success | 0 |

## Marked for the code owner

None.

## Changes to security-review.md, flagged

None.

## Accepted foreign commits on the reports branch

None.

## Known-failing list

Size: 117.
- remove from list: acceptance.test_open_issues_pub::test_pub_01_last_page_keeps_the_remaining_task
- remove from list: acceptance.test_open_issues_pub::test_pub_01_last_page_of_a_search_keeps_the_remaining_match
- remove from list: acceptance.test_open_issues_pub::test_pub_01_paging_boundaries_keep_every_remaining_task[tasks-1-limit-2-offset-0]
- remove from list: acceptance.test_open_issues_pub::test_pub_01_paging_boundaries_keep_every_remaining_task[tasks-5-limit-2-offset-4]
- remove from list: acceptance.test_open_issues_pub::test_pub_02_export_keeps_exact_columns_for_many_structured_titles
- remove from list: acceptance.test_open_issues_pub::test_pub_02_export_recovers_a_title_with_comma_and_quotes
- remove from list: acceptance.test_open_issues_pub::test_pub_02_export_recovers_unicode_and_line_breaks[comma]
- remove from list: acceptance.test_open_issues_pub::test_pub_02_export_recovers_unicode_and_line_breaks[crlf-comma-quotes]
- remove from list: acceptance.test_open_issues_pub::test_pub_02_export_recovers_unicode_and_line_breaks[line-feed]
- remove from list: acceptance.test_open_issues_pub::test_pub_02_export_recovers_unicode_and_line_breaks[mixed]
- remove from list: acceptance.test_open_issues_pub::test_pub_02_export_recovers_unicode_and_line_breaks[quoted]
- remove from list: acceptance.test_open_issues_pub::test_pub_02_export_recovers_unicode_and_line_breaks[unicode]
- remove from list: acceptance.test_spec_1_identity_and_visibility::test_spec_1_admin_and_observer_list_all_tasks[admin]
- remove from list: acceptance.test_spec_1_identity_and_visibility::test_spec_1_admin_and_observer_list_all_tasks[observer]
- remove from list: acceptance.test_spec_1_identity_and_visibility::test_spec_1_member_list_contains_only_visible_tasks[alice]
- remove from list: acceptance.test_spec_1_identity_and_visibility::test_spec_1_member_list_contains_only_visible_tasks[bob]
- remove from list: acceptance.test_spec_1_identity_and_visibility::test_spec_1_member_list_total_leaks_no_global_count[2-2-positions1]
- remove from list: acceptance.test_spec_1_identity_and_visibility::test_spec_1_member_search_returns_only_visible_matches
- remove from list: acceptance.test_spec_3_existing_endpoints::test_spec_3_empty_search_returns_all_visible_tasks
- remove from list: acceptance.test_spec_3_existing_endpoints::test_spec_3_list_accepts_limits_1_and_100[100]
- remove from list: acceptance.test_spec_3_existing_endpoints::test_spec_3_list_is_ordered_by_increasing_id
- remove from list: acceptance.test_spec_3_existing_endpoints::test_spec_3_search_is_a_literal_substring[inner-space]
- remove from list: acceptance.test_spec_3_existing_endpoints::test_spec_3_search_is_a_literal_substring[leading-space]
- remove from list: acceptance.test_spec_3_existing_endpoints::test_spec_3_search_is_a_literal_substring[no-space]
- remove from list: acceptance.test_spec_3_existing_endpoints::test_spec_3_search_is_case_insensitive[REPORT]
- remove from list: acceptance.test_spec_3_existing_endpoints::test_spec_3_search_is_case_insensitive[RePoRt]
- remove from list: acceptance.test_spec_3_existing_endpoints::test_spec_3_search_is_case_insensitive[report]
- remove from list: acceptance.test_spec_3_existing_endpoints::test_spec_3_search_matches_the_description
- remove from list: acceptance.test_spec_3_existing_endpoints::test_spec_3_search_text_is_data_not_sql[double-quote-or]
- remove from list: acceptance.test_spec_3_existing_endpoints::test_spec_3_search_treats_like_wildcards_as_literal_characters[backslash]
- remove from list: acceptance.test_spec_3_existing_endpoints::test_spec_3_total_counts_every_match_before_paging
- remove from list: acceptance.test_spec_4_6_1_upgrade_of_existing_database::test_spec_4_upgrade_preserves_tasks_and_work_logs
- remove from list: acceptance.test_spec_4_durability_retries_concurrency::test_spec_4_acknowledged_task_survives_restart
- remove from list: acceptance.test_spec_5_errors_and_compatibility::test_spec_5_create_app_keeps_its_data_in_the_given_file
- remove from list: acceptance.test_spec_5_errors_and_compatibility::test_spec_5_list_keeps_its_documented_field_names
- remove from list: acceptance.test_spec_5_errors_and_compatibility::test_spec_5_text_with_sql_metacharacters_is_stored_and_found[double-quotes]
- remove from list: acceptance.test_spec_5_errors_and_compatibility::test_spec_5_text_with_sql_metacharacters_is_stored_and_found[drop]
- remove from list: acceptance.test_spec_5_errors_and_compatibility::test_spec_5_text_with_sql_metacharacters_is_stored_and_found[like-chars]

## Findings

None.

## Dependency changes

None.

## Bypass merges

- PR 17, merge 1ce6e90fd37e50863f11dc9073b4240dd071b373, by None
- PR 8, merge bea74090ac43c598a445ea30789a3f3ecb09acf5, by None
- PR 6, merge 00d6b64706d1080a8ff79733281f83972034d97f, by None
- PR 3, merge 76f31ea79bd4a39f4179a2e6da72ca7c9131fcf5, by None
- PR 2, merge 191d202628383c9e18f397f52f3eff49f614d701, by None
- PR 1, merge be7ce57f6998b232b225a96a257a6086924d3e29, by None
- PR None, merge c45c851ff430f493409ed353c1416f4e28bc5c4c, by XThoughtLabs
- PR None, merge 59f32fddfd10faa40d21fefa09fb831e0e3a918f, by XThoughtLabs
- PR None, merge ab3a460d1ad90df2888603b84fd3147759caffc6, by XThoughtLabs

## Resources

- executor_runs: unknown
- executor_turns: unknown
- codex_runs: 0
- codex_tokens: unknown
- actions_minutes: 1.87
- human interventions: 0
- human minutes: 0

## Semi-automatic steps

- The independent review is started by hand on the laptop.
- A person approves and merges each PR.

This report was generated by a script. No model wrote or edited it.
