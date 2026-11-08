# Quality gate report

**Preliminary verdict: ready-for-human**

The final verdict comes after the evidence is stored: see the check `gate/final`, and `final.json` beside this report.

## Verification record

| Field | Value |
|---|---|
| repository | XThoughtLabs/gate-practice-app |
| head_repository | XThoughtLabs/gate-practice-app |
| pr | 26 |
| run_id | 42460435600 |
| run_attempt | 1 |
| event | pull_request_target |
| baseline_sha | 821330ffbb19f545fb81f3c223b0a286ff6c4980 |
| base_sha | e0128451e357ecc0090b1a7ba32fdd093949cd7e |
| head_sha | 8ffe529f2ad3bbb92ea3cb1171684ef7b8ca5e04 |
| gate_sha | 906ebaefdc10ca459ccd9c890ecb56c9b0f3acb9 |
| head_ref | ai/25-get-tasks-id-ignores-task-visibility |
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
- remove from list: acceptance.test_spec_1_identity_and_visibility::test_spec_1_business_endpoints_require_a_valid_token[GET /tasks/{task_id}/history-invalid]
- remove from list: acceptance.test_spec_1_identity_and_visibility::test_spec_1_business_endpoints_require_a_valid_token[GET /tasks/{task_id}/history-missing]
- remove from list: acceptance.test_spec_1_identity_and_visibility::test_spec_1_member_cannot_read_history_of_unrelated_task
- remove from list: acceptance.test_spec_1_identity_and_visibility::test_spec_1_member_cannot_read_unrelated_task
- remove from list: acceptance.test_spec_1_identity_and_visibility::test_spec_1_member_list_contains_only_visible_tasks[alice]
- remove from list: acceptance.test_spec_1_identity_and_visibility::test_spec_1_member_list_contains_only_visible_tasks[bob]
- remove from list: acceptance.test_spec_1_identity_and_visibility::test_spec_1_member_list_total_leaks_no_global_count[2-2-positions1]
- remove from list: acceptance.test_spec_1_identity_and_visibility::test_spec_1_member_loses_read_access_when_no_longer_assigned
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
- remove from list: acceptance.test_spec_4_6_1_upgrade_of_existing_database::test_spec_6_1_migration_event_is_not_repeated_or_rewritten_on_later_restarts
- remove from list: acceptance.test_spec_4_6_1_upgrade_of_existing_database::test_spec_6_1_pre_upgrade_task_gets_one_migration_event
- remove from list: acceptance.test_spec_4_6_1_upgrade_of_existing_database::test_spec_6_1_restart_adds_no_migration_event_to_current_tasks
- remove from list: acceptance.test_spec_4_6_1_upgrade_of_existing_database::test_spec_6_1_task_created_after_upgrade_gets_an_operation_creation_event
- remove from list: acceptance.test_spec_4_6_1_upgrade_of_existing_database::test_spec_6_1_transition_after_upgrade_appends_an_operation_event
- remove from list: acceptance.test_spec_4_durability_retries_concurrency::test_spec_4_acknowledged_task_survives_restart
- remove from list: acceptance.test_spec_5_errors_and_compatibility::test_spec_5_create_app_keeps_its_data_in_the_given_file
- remove from list: acceptance.test_spec_5_errors_and_compatibility::test_spec_5_list_keeps_its_documented_field_names
- remove from list: acceptance.test_spec_5_errors_and_compatibility::test_spec_5_text_with_sql_metacharacters_is_stored_and_found[double-quotes]
- remove from list: acceptance.test_spec_5_errors_and_compatibility::test_spec_5_text_with_sql_metacharacters_is_stored_and_found[drop]
- remove from list: acceptance.test_spec_5_errors_and_compatibility::test_spec_5_text_with_sql_metacharacters_is_stored_and_found[like-chars]
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_changed_at_is_aware_utc_and_follows_the_sequence
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_concurrent_identical_transitions_append_one_event
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_creation_event_actor_is_the_creator[admin]
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_creation_event_actor_is_the_creator[bob]
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_each_transition_appends_one_event
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_earlier_events_are_not_rewritten_by_later_changes
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_history_body_is_an_items_object
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_history_is_not_editable_through_the_api[DELETE]
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_history_is_not_editable_through_the_api[PATCH]
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_history_is_not_editable_through_the_api[POST]
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_history_is_not_editable_through_the_api[PUT]
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_history_is_readable_by_task_readers[admin]
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_history_is_readable_by_task_readers[assignee]
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_history_is_readable_by_task_readers[creator]
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_history_is_readable_by_task_readers[observer]
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_history_of_former_assignee_is_hidden
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_history_of_missing_task_returns_404[admin]
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_history_of_missing_task_returns_404[alice]
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_history_of_missing_task_returns_404[observer]
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_history_starts_with_creation_event
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_history_survives_restart
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_no_event_for_a_rejected_reopen
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_no_event_for_an_idempotent_creation_retry
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_no_event_for_non_status_edits
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_no_event_for_rejected_requests[invalid-companion-field]
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_no_event_for_rejected_requests[observer]
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_no_event_for_rejected_requests[skipped-transition]
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_no_event_for_rejected_requests[unknown-companion-field]
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_no_event_for_rejected_requests[unknown-status]
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_no_event_for_rejected_requests[unrelated-member]
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_no_event_for_unchanged_status[in_progress]
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_no_event_for_unchanged_status[todo]
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_sequence_is_counted_per_task
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_status_change_with_other_fields_appends_one_event
- remove from list: acceptance.test_spec_6_1_status_history::test_spec_6_1_task_patch_cannot_write_history
- remove from list: acceptance.test_spec_6_2_changes_to_others_tasks::test_spec_6_2_assignee_may_reassign_the_task_away
- remove from list: acceptance.test_spec_6_2_changes_to_others_tasks::test_spec_6_2_former_assignee_cannot_patch
- remove from list: acceptance.test_spec_6_2_changes_to_others_tasks::test_spec_6_2_member_cannot_grant_self_access_by_assigning_self
- remove from list: acceptance.test_spec_6_2_changes_to_others_tasks::test_spec_6_2_member_cannot_patch_task_assigned_to_someone_else
- remove from list: acceptance.test_spec_6_2_changes_to_others_tasks::test_spec_6_2_member_cannot_patch_unrelated_task[priority]
- remove from list: acceptance.test_spec_6_2_changes_to_others_tasks::test_spec_6_2_member_cannot_patch_unrelated_task[status]
- remove from list: acceptance.test_spec_6_2_changes_to_others_tasks::test_spec_6_2_member_cannot_patch_unrelated_task[title]
- remove from list: acceptance.test_spec_6_2_changes_to_others_tasks::test_spec_6_2_observer_patch_of_missing_task_returns_404
- remove from list: acceptance.test_spec_6_2_changes_to_others_tasks::test_spec_6_2_observer_patch_returns_403[assignee]
- remove from list: acceptance.test_spec_6_2_changes_to_others_tasks::test_spec_6_2_observer_patch_returns_403[everything]
- remove from list: acceptance.test_spec_6_2_changes_to_others_tasks::test_spec_6_2_observer_patch_returns_403[status]
- remove from list: acceptance.test_spec_6_2_changes_to_others_tasks::test_spec_6_2_observer_patch_returns_403[title]
- remove from list: acceptance.test_spec_6_2_changes_to_others_tasks::test_spec_6_2_reopen_restriction_still_applies[assignee]
- remove from list: acceptance.test_spec_6_2_changes_to_others_tasks::test_spec_6_2_reopen_restriction_still_applies[creator]

## Findings

None.

## Dependency changes

None.

## Bypass merges

- PR 22, merge 09dbea24a1000b3506c732d0642ffea5b980190b, by None
- PR 20, merge c45c851ff430f493409ed353c1416f4e28bc5c4c, by None
- PR 17, merge 1ce6e90fd37e50863f11dc9073b4240dd071b373, by None
- PR 8, merge bea74090ac43c598a445ea30789a3f3ecb09acf5, by None
- PR 6, merge 00d6b64706d1080a8ff79733281f83972034d97f, by None
- PR 3, merge 76f31ea79bd4a39f4179a2e6da72ca7c9131fcf5, by None
- PR 2, merge 191d202628383c9e18f397f52f3eff49f614d701, by None
- PR 1, merge be7ce57f6998b232b225a96a257a6086924d3e29, by None
- PR None, merge ab3a460d1ad90df2888603b84fd3147759caffc6, by XThoughtLabs

## Resources

- executor_runs: unknown
- executor_turns: unknown
- codex_runs: 0
- codex_tokens: unknown
- actions_minutes: 2.0
- human interventions: 0
- human minutes: 0

## Semi-automatic steps

- The independent review is started by hand on the laptop.
- A person approves and merges each PR.

This report was generated by a script. No model wrote or edited it.
