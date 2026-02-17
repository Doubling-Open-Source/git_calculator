# Lake schema: gitextractor and refdiff

## Connection summary

- **Database**: `lake` (MySQL; same DB used by the Grafana MySQL datasource).
- **Tables inspected**: `commits`, `refs`, `commit_parents` (used by the [Commits - Raw Extractor](../dashboards/Commits%20-%20Raw%20Extractor.json) dashboard).
- **Source plugins**: gitextractor (commits, refs, commit_parents); refdiff uses `commits_diffs` and related tables; the dashboard queries the domain-layer `commits`, `refs`, and `commit_parents` with `_raw_data_params` for repo scoping.

---

**1. List tables in lake**

```
mysql> SHOW TABLES FROM lake;
+----------------------------------------------+
| Tables_in_lake                               |
+----------------------------------------------+
| _devlake_api_keys                            |
| _devlake_blueprint_connections               |
| _devlake_blueprint_labels                    |
| _devlake_blueprint_scopes                    |
| _devlake_blueprints                          |
| _devlake_collector_latest_state              |
| _devlake_locking_history                     |
| _devlake_locking_stub                        |
| _devlake_migration_history                   |
| _devlake_notifications                       |
| _devlake_pipeline_labels                     |
| _devlake_pipelines                           |
| _devlake_store                               |
| _devlake_subtask_states                      |
| _devlake_subtasks                            |
| _devlake_tasks                               |
| _tool_ae_commits                             |
| _tool_ae_connections                         |
| _tool_ae_projects                            |
| _tool_azuredevops_azuredevopsconnections     |
| _tool_azuredevops_builds                     |
| _tool_azuredevops_gitpullrequestcommits      |
| _tool_azuredevops_gitpullrequests            |
| _tool_azuredevops_gitrepositories            |
| _tool_azuredevops_gitrepositoryconfigs       |
| _tool_azuredevops_go_builds                  |
| _tool_azuredevops_go_commits                 |
| _tool_azuredevops_go_connections             |
| _tool_azuredevops_go_pull_request_commits    |
| _tool_azuredevops_go_pull_request_labels     |
| _tool_azuredevops_go_pull_requests           |
| _tool_azuredevops_go_repo_commits            |
| _tool_azuredevops_go_repos                   |
| _tool_azuredevops_go_scope_configs           |
| _tool_azuredevops_go_timeline_records        |
| _tool_azuredevops_go_users                   |
| _tool_azuredevops_jobs                       |
| _tool_bamboo_connections                     |
| _tool_bamboo_deploy_builds                   |
| _tool_bamboo_deploy_environments             |
| _tool_bamboo_job_builds                      |
| _tool_bamboo_jobs                            |
| _tool_bamboo_plan_build_commits              |
| _tool_bamboo_plan_builds                     |
| _tool_bamboo_plans                           |
| _tool_bamboo_projects                        |
| _tool_bamboo_scope_configs                   |
| _tool_bitbucket_accounts                     |
| _tool_bitbucket_commits                      |
| _tool_bitbucket_connections                  |
| _tool_bitbucket_deployments                  |
| _tool_bitbucket_issue_comments               |
| _tool_bitbucket_issues                       |
| _tool_bitbucket_pipeline_steps               |
| _tool_bitbucket_pipelines                    |
| _tool_bitbucket_pull_request_comments        |
| _tool_bitbucket_pull_request_commits         |
| _tool_bitbucket_pull_requests                |
| _tool_bitbucket_repo_commits                 |
| _tool_bitbucket_repos                        |
| _tool_bitbucket_scope_configs                |
| _tool_bitbucket_server_connections           |
| _tool_bitbucket_server_pull_request_comments |
| _tool_bitbucket_server_pull_request_commits  |
| _tool_bitbucket_server_pull_requests         |
| _tool_bitbucket_server_repos                 |
| _tool_bitbucket_server_scope_configs         |
| _tool_bitbucket_server_users                 |
| _tool_circleci_accounts                      |
| _tool_circleci_connections                   |
| _tool_circleci_jobs                          |
| _tool_circleci_pipelines                     |
| _tool_circleci_projects                      |
| _tool_circleci_scope_configs                 |
| _tool_circleci_workflows                     |
| _tool_customized_fields                      |
| _tool_feishu_chats                           |
| _tool_feishu_connections                     |
| _tool_feishu_meeting_top_user_items          |
| _tool_feishu_messages                        |
| _tool_gitee_accounts                         |
| _tool_gitee_commit_stats                     |
| _tool_gitee_commits                          |
| _tool_gitee_connections                      |
| _tool_gitee_issue_comments                   |
| _tool_gitee_issue_labels                     |
| _tool_gitee_issues                           |
| _tool_gitee_pull_request_comments            |
| _tool_gitee_pull_request_commits             |
| _tool_gitee_pull_request_issues              |
| _tool_gitee_pull_request_labels              |
| _tool_gitee_pull_requests                    |
| _tool_gitee_repo_commits                     |
| _tool_gitee_repos                            |
| _tool_gitee_reviewers                        |
| _tool_github_account_orgs                    |
| _tool_github_accounts                        |
| _tool_github_commit_stats                    |
| _tool_github_commits                         |
| _tool_github_connections                     |
| _tool_github_deployments                     |
| _tool_github_issue_assignees                 |
| _tool_github_issue_comments                  |
| _tool_github_issue_events                    |
| _tool_github_issue_labels                    |
| _tool_github_issues                          |
| _tool_github_jobs                            |
| _tool_github_milestones                      |
| _tool_github_pull_request_comments           |
| _tool_github_pull_request_commits            |
| _tool_github_pull_request_issues             |
| _tool_github_pull_request_labels             |
| _tool_github_pull_request_reviews            |
| _tool_github_pull_requests                   |
| _tool_github_releases                        |
| _tool_github_repo_accounts                   |
| _tool_github_repo_commits                    |
| _tool_github_repos                           |
| _tool_github_reviewers                       |
| _tool_github_runs                            |
| _tool_github_scope_configs                   |
| _tool_gitlab_accounts                        |
| _tool_gitlab_assignees                       |
| _tool_gitlab_commits                         |
| _tool_gitlab_connections                     |
| _tool_gitlab_deployments                     |
| _tool_gitlab_issue_assignees                 |
| _tool_gitlab_issue_labels                    |
| _tool_gitlab_issues                          |
| _tool_gitlab_jobs                            |
| _tool_gitlab_merge_requests                  |
| _tool_gitlab_mr_comments                     |
| _tool_gitlab_mr_commits                      |
| _tool_gitlab_mr_labels                       |
| _tool_gitlab_mr_notes                        |
| _tool_gitlab_pipeline_projects               |
| _tool_gitlab_pipelines                       |
| _tool_gitlab_project_commits                 |
| _tool_gitlab_projects                        |
| _tool_gitlab_reviewers                       |
| _tool_gitlab_scope_configs                   |
| _tool_gitlab_tags                            |
| _tool_icla_committer                         |
| _tool_jenkins_build_commits                  |
| _tool_jenkins_builds                         |
| _tool_jenkins_connections                    |
| _tool_jenkins_job_dags                       |
| _tool_jenkins_jobs                           |
| _tool_jenkins_scope_configs                  |
| _tool_jenkins_stages                         |
| _tool_jira_accounts                          |
| _tool_jira_board_issues                      |
| _tool_jira_board_sprints                     |
| _tool_jira_boards                            |
| _tool_jira_connections                       |
| _tool_jira_issue_changelog_items             |
| _tool_jira_issue_changelogs                  |
| _tool_jira_issue_comments                    |
| _tool_jira_issue_commits                     |
| _tool_jira_issue_fields                      |
| _tool_jira_issue_labels                      |
| _tool_jira_issue_relationships               |
| _tool_jira_issue_types                       |
| _tool_jira_issues                            |
| _tool_jira_projects                          |
| _tool_jira_remotelinks                       |
| _tool_jira_scope_configs                     |
| _tool_jira_sprint_issues                     |
| _tool_jira_sprints                           |
| _tool_jira_statuses                          |
| _tool_jira_worklogs                          |
| _tool_opsgenie_assignments                   |
| _tool_opsgenie_connections                   |
| _tool_opsgenie_incidents                     |
| _tool_opsgenie_responders                    |
| _tool_opsgenie_scope_configs                 |
| _tool_opsgenie_services                      |
| _tool_opsgenie_teams                         |
| _tool_opsgenie_users                         |
| _tool_pagerduty_assignments                  |
| _tool_pagerduty_connections                  |
| _tool_pagerduty_incidents                    |
| _tool_pagerduty_scope_configs                |
| _tool_pagerduty_services                     |
| _tool_pagerduty_users                        |
| _tool_q_dev_connections                      |
| _tool_q_dev_s3_file_meta                     |
| _tool_q_dev_user_data                        |
| _tool_q_dev_user_metrics                     |
| _tool_refdiff_finished_commits_diffs         |
| _tool_slack_channel_messages                 |
| _tool_slack_channels                         |
| _tool_slack_connections                      |
| _tool_sonarqube_accounts                     |
| _tool_sonarqube_connections                  |
| _tool_sonarqube_file_metrics                 |
| _tool_sonarqube_hotspots                     |
| _tool_sonarqube_issue_code_blocks            |
| _tool_sonarqube_issue_impacts                |
| _tool_sonarqube_issues                       |
| _tool_sonarqube_projects                     |
| _tool_sonarqube_scope_configs                |
| _tool_tapd_accounts                          |
| _tool_tapd_bug_changelog_items               |
| _tool_tapd_bug_changelogs                    |
| _tool_tapd_bug_commits                       |
| _tool_tapd_bug_custom_field_value            |
| _tool_tapd_bug_custom_fields                 |
| _tool_tapd_bug_labels                        |
| _tool_tapd_bug_statuses                      |
| _tool_tapd_bugs                              |
| _tool_tapd_connections                       |
| _tool_tapd_iteration_bugs                    |
| _tool_tapd_iteration_stories                 |
| _tool_tapd_iteration_tasks                   |
| _tool_tapd_iterations                        |
| _tool_tapd_scope_configs                     |
| _tool_tapd_stories                           |
| _tool_tapd_story_bugs                        |
| _tool_tapd_story_categories                  |
| _tool_tapd_story_changelog_items             |
| _tool_tapd_story_changelogs                  |
| _tool_tapd_story_commits                     |
| _tool_tapd_story_custom_field_value          |
| _tool_tapd_story_custom_fields               |
| _tool_tapd_story_labels                      |
| _tool_tapd_story_statuses                    |
| _tool_tapd_task_changelog_items              |
| _tool_tapd_task_changelogs                   |
| _tool_tapd_task_commits                      |
| _tool_tapd_task_custom_field_value           |
| _tool_tapd_task_custom_fields                |
| _tool_tapd_task_labels                       |
| _tool_tapd_tasks                             |
| _tool_tapd_workitem_types                    |
| _tool_tapd_worklogs                          |
| _tool_tapd_workspace_bugs                    |
| _tool_tapd_workspace_iterations              |
| _tool_tapd_workspace_stories                 |
| _tool_tapd_workspace_tasks                   |
| _tool_tapd_workspaces                        |
| _tool_teambition_accounts                    |
| _tool_teambition_connections                 |
| _tool_teambition_projects                    |
| _tool_teambition_sprints                     |
| _tool_teambition_task_activities             |
| _tool_teambition_task_flow_status            |
| _tool_teambition_task_scenarios              |
| _tool_teambition_task_tag_tasks              |
| _tool_teambition_task_tags                   |
| _tool_teambition_task_worktime               |
| _tool_teambition_tasks                       |
| _tool_trello_boards                          |
| _tool_trello_cards                           |
| _tool_trello_check_items                     |
| _tool_trello_connections                     |
| _tool_trello_labels                          |
| _tool_trello_lists                           |
| _tool_trello_members                         |
| _tool_trello_scope_configs                   |
| _tool_webhook_connections                    |
| _tool_zentao_accounts                        |
| _tool_zentao_bug_commits                     |
| _tool_zentao_bug_repo_commits                |
| _tool_zentao_bugs                            |
| _tool_zentao_changelog                       |
| _tool_zentao_changelog_detail                |
| _tool_zentao_connections                     |
| _tool_zentao_departments                     |
| _tool_zentao_execution_stories               |
| _tool_zentao_execution_summary               |
| _tool_zentao_executions                      |
| _tool_zentao_product_summary                 |
| _tool_zentao_products                        |
| _tool_zentao_project_stories                 |
| _tool_zentao_projects                        |
| _tool_zentao_scope_configs                   |
| _tool_zentao_stories                         |
| _tool_zentao_story_commits                   |
| _tool_zentao_story_repo_commits              |
| _tool_zentao_task_commits                    |
| _tool_zentao_task_repo_commits               |
| _tool_zentao_tasks                           |
| _tool_zentao_worklogs                        |
| accounts                                     |
| board_issues                                 |
| board_repos                                  |
| board_sprints                                |
| boards                                       |
| calendar_months                              |
| cicd_deployment_commits                      |
| cicd_deployments                             |
| cicd_pipeline_commits                        |
| cicd_pipelines                               |
| cicd_releases                                |
| cicd_scopes                                  |
| cicd_tasks                                   |
| commit_file_components                       |
| commit_files                                 |
| commit_line_change                           |
| commit_parents                               |
| commits                                      |
| commits_diffs                                |
| components                                   |
| cq_file_metrics                              |
| cq_issue_code_blocks                         |
| cq_issue_impacts                             |
| cq_issues                                    |
| cq_projects                                  |
| dora_benchmarks                              |
| incident_assignees                           |
| incidents                                    |
| issue_assignee_history                       |
| issue_assignees                              |
| issue_changelogs                             |
| issue_comments                               |
| issue_commits                                |
| issue_custom_array_fields                    |
| issue_labels                                 |
| issue_relationships                          |
| issue_repo_commits                           |
| issue_status_history                         |
| issue_worklogs                               |
| issues                                       |
| project_incident_deployment_relationships    |
| project_mapping                              |
| project_metric_settings                      |
| project_pr_metrics                           |
| projects                                     |
| pull_request_assignees                       |
| pull_request_comments                        |
| pull_request_commits                         |
| pull_request_issues                          |
| pull_request_labels                          |
| pull_request_reviewers                       |
| pull_requests                                |
| qa_apis                                      |
| qa_projects                                  |
| qa_test_case_executions                      |
| qa_test_cases                                |
| ref_commits                                  |
| refs                                         |
| refs_issues_diffs                            |
| refs_pr_cherrypicks                          |
| repo_commits                                 |
| repo_snapshot                                |
| repos                                        |
| sprint_issues                                |
| sprints                                      |
| team_users                                   |
| teams                                        |
| user_accounts                                |
| users                                        |
+----------------------------------------------+
353 rows in set (0.00 sec)
```

**2. Document commits**

```
mysql> DESCRIBE lake.commits;
+------------------+-----------------+------+-----+---------+-------+
| Field            | Type            | Null | Key | Default | Extra |
+------------------+-----------------+------+-----+---------+-------+
| created_at       | datetime(3)     | YES  |     | NULL    |       |
| updated_at       | datetime(3)     | YES  |     | NULL    |       |
| _raw_data_params | varchar(255)    | YES  | MUL | NULL    |       |
| _raw_data_table  | varchar(255)    | YES  |     | NULL    |       |
| _raw_data_id     | bigint unsigned | YES  |     | NULL    |       |
| _raw_data_remark | longtext        | YES  |     | NULL    |       |
| sha              | varchar(40)     | NO   | PRI | NULL    |       |
| additions        | bigint          | YES  |     | NULL    |       |
| deletions        | bigint          | YES  |     | NULL    |       |
| dev_eq           | bigint          | YES  |     | NULL    |       |
| message          | longblob        | YES  |     | NULL    |       |
| author_name      | varchar(255)    | YES  |     | NULL    |       |
| author_email     | varchar(255)    | YES  |     | NULL    |       |
| authored_date    | datetime(3)     | YES  |     | NULL    |       |
| author_id        | varchar(255)    | YES  |     | NULL    |       |
| committer_name   | varchar(255)    | YES  |     | NULL    |       |
| committer_email  | varchar(255)    | YES  |     | NULL    |       |
| committed_date   | datetime(3)     | YES  |     | NULL    |       |
| committer_id     | varchar(255)    | YES  | MUL | NULL    |       |
+------------------+-----------------+------+-----+---------+-------+
19 rows in set (0.03 sec)
```

```
mysql> SELECT * FROM lake.commits LIMIT 2;
+-------------------------+-------------------------+-----------------------+-----------------+--------------+------------------+------------------------------------------+-----------+-----------+--------+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+----------------+---------------------------------------------------+-------------------------+---------------------------------------------------+----------------+-----------------------+-------------------------+-----------------------+
| created_at              | updated_at              | _raw_data_params      | _raw_data_table | _raw_data_id | _raw_data_remark | sha                                      | additions | deletions | dev_eq | message                                                                                                                                                                                            | author_name    | author_email                                      | authored_date           | author_id                                         | committer_name | committer_email       | committed_date          | committer_id          |
+-------------------------+-------------------------+-----------------------+-----------------+--------------+------------------+------------------------------------------+-----------+-----------+--------+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+----------------+---------------------------------------------------+-------------------------+---------------------------------------------------+----------------+-----------------------+-------------------------+-----------------------+
| 2026-02-16 01:05:12.017 | 2026-02-16 01:05:12.017 | local:sXXXXX     | gitextractor    |            0 |                  | 000578c55984e35eb786e153c54d54385b3cc049 |       109 |        19 |      0 | 0x5570646174656420666574636853636F6F707342795479706520636C6F75642066756E6374696F6E20746F20696E636C75646520746F74616C53636F6F7073206E756D62657220756E64657220706167696E6174696F6E2073656374696F6E0A | PXXX CXXX | XXXX@XXXX.com                             | 2025-09-24 14:14:25.000 | XXXX@XXXX.com                             | PXXX CXXX | XXXX@XXXX.com | 2025-09-24 14:14:25.000 | XXXX@XXXX.com |
| 2026-02-16 01:04:55.958 | 2026-02-16 01:04:55.958 | local:***REMOVED*** | gitextractor    |            0 |                  | 0016a69fe6f130b965c929bd1537b417212249af |         6 |         9 |      0 | 0x4D657267652070756C6C207265717565737420233238332066726F6D2053686172652D53636F6F70732F72656C656173650A0A52656C65617365                                                                             | ZXXX KXXXXX      | 50744499+XXXX@users.noreply.github.com | 2023-02-25 02:24:41.000 | 50744499+XXXX@users.noreply.github.com | GitHub         | XXXX@github.com    | 2023-02-25 02:24:41.000 | XXXX@github.com    |
+-------------------------+-------------------------+-----------------------+-----------------+--------------+------------------+------------------------------------------+-----------+-----------+--------+----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+----------------+---------------------------------------------------+-------------------------+---------------------------------------------------+----------------+-----------------------+-------------------------+-----------------------+
2 rows in set (0.00 sec)
```

**3. Document refs**

```
mysql> DESCRIBE lake.refs;
+------------------+-----------------+------+-----+---------+-------+
| Field            | Type            | Null | Key | Default | Extra |
+------------------+-----------------+------+-----+---------+-------+
| created_at       | datetime(3)     | YES  |     | NULL    |       |
| updated_at       | datetime(3)     | YES  |     | NULL    |       |
| _raw_data_params | varchar(255)    | YES  | MUL | NULL    |       |
| _raw_data_table  | varchar(255)    | YES  |     | NULL    |       |
| _raw_data_id     | bigint unsigned | YES  |     | NULL    |       |
| _raw_data_remark | longtext        | YES  |     | NULL    |       |
| repo_id          | varchar(255)    | YES  |     | NULL    |       |
| name             | varchar(255)    | YES  |     | NULL    |       |
| commit_sha       | varchar(40)     | YES  |     | NULL    |       |
| is_default       | tinyint(1)      | YES  |     | NULL    |       |
| ref_type         | varchar(255)    | YES  |     | NULL    |       |
| created_date     | datetime(3)     | YES  |     | NULL    |       |
| id               | varchar(500)    | NO   | PRI | NULL    |       |
+------------------+-----------------+------+-----+---------+-------+
13 rows in set (0.01 sec)
```

```
mysql> SELECT * FROM lake.refs LIMIT 2;
+-------------------------+-------------------------+---------------------------+-----------------+--------------+------------------+---------------------------+------+------------------------------------------+------------+----------+--------------+--------------------------------+
| created_at              | updated_at              | _raw_data_params          | _raw_data_table | _raw_data_id | _raw_data_remark | repo_id                   | name | commit_sha                               | is_default | ref_type | created_date | id                             |
+-------------------------+-------------------------+---------------------------+-----------------+--------------+------------------+---------------------------+------+------------------------------------------+------------+----------+--------------+--------------------------------+
| 2026-02-16 01:04:57.026 | 2026-02-16 01:04:57.026 | local:***REMOVED***     | gitextractor    |            0 |                  | local:***REMOVED***     | main | fb3f7358e30d9ecf4f43991a60f3cd2c9db68699 |          1 | BRANCH   | NULL         | local:***REMOVED***:main     |
| 2026-02-16 01:05:34.204 | 2026-02-16 01:05:34.204 | local:***REMOVED*** | gitextractor    |            0 |                  | local:***REMOVED*** | main | 4899828e842a69742e8787b21a9ade396c282a8a |          1 | BRANCH   | NULL         | local:***REMOVED***:main |
+-------------------------+-------------------------+---------------------------+-----------------+--------------+------------------+---------------------------+------+------------------------------------------+------------+----------+--------------+--------------------------------+
2 rows in set (0.00 sec)
```

```
mysql> SELECT DISTINCT repo_id FROM lake.refs;
+---------------------------+
| repo_id                   |
+---------------------------+
| local:***REMOVED***     |
| local:***REMOVED*** |
| local:sXXXXX         |
| local:***REMOVED***   |
| local:***REMOVED***   |
| local:***REMOVED***        |
+---------------------------+
6 rows in set (0.00 sec)
```

**4. Document commit_parents**

```
mysql> DESCRIBE lake.commit_parents;
+-------------------+-----------------+------+-----+---------+-------+
| Field             | Type            | Null | Key | Default | Extra |
+-------------------+-----------------+------+-----+---------+-------+
| commit_sha        | varchar(40)     | NO   | PRI | NULL    |       |
| parent_commit_sha | varchar(40)     | NO   | PRI | NULL    |       |
| created_at        | datetime(3)     | YES  |     | NULL    |       |
| updated_at        | datetime(3)     | YES  |     | NULL    |       |
| _raw_data_params  | varchar(255)    | YES  | MUL | NULL    |       |
| _raw_data_table   | varchar(255)    | YES  |     | NULL    |       |
| _raw_data_id      | bigint unsigned | YES  |     | NULL    |       |
| _raw_data_remark  | longtext        | YES  |     | NULL    |       |
+-------------------+-----------------+------+-----+---------+-------+
8 rows in set (0.01 sec)
```

```
mysql> SELECT * FROM lake.commit_parents LIMIT 2;
+------------------------------------------+------------------------------------------+-------------------------+-------------------------+-----------------------+-----------------+--------------+------------------+
| commit_sha                               | parent_commit_sha                        | created_at              | updated_at              | _raw_data_params      | _raw_data_table | _raw_data_id | _raw_data_remark |
+------------------------------------------+------------------------------------------+-------------------------+-------------------------+-----------------------+-----------------+--------------+------------------+
| 000578c55984e35eb786e153c54d54385b3cc049 | ebc70c48abaaf3f0ceee6257ac5995f5affe77f9 | 2026-02-16 01:05:11.954 | 2026-02-16 01:05:11.954 | local:sXXXXX     | gitextractor    |            0 |                  |
| 0016a69fe6f130b965c929bd1537b417212249af | abe6368f7dac4c26034d5da30b11bd67615c515c | 2026-02-16 01:04:55.950 | 2026-02-16 01:04:55.950 | local:***REMOVED*** | gitextractor    |            0 |                  |
+------------------------------------------+------------------------------------------+-------------------------+-------------------------+-----------------------+-----------------+--------------+------------------+
2 rows in set (0.01 sec)
```

---

## Repo filter

- **Exact predicate** used to restrict to one repo on both `commits` and `refs`:
  - `WHERE _raw_data_params IN ('$repo_id')`
- **`_raw_data_params`** holds the repo scope on each row; values match the format of `repo_id` (e.g. `local:***REMOVED***`, `local:sXXXXX`).
- **`$repo_id`** in the dashboard is provided by the template variable whose query is:
  - `SELECT DISTINCT repo_id FROM refs;`
- So filtering commits (or refs) to a single repo uses the same value as in `refs.repo_id`, e.g. `WHERE _raw_data_params IN ('local:***REMOVED***')`.
