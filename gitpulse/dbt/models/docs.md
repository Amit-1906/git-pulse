{% docs gitpulse_overview %}
GitPulse is an end-to-end ELT data platform for engineering intelligence and GitHub activity analytics.
This dbt project models raw GitHub REST API event streams into dimensional marts and operational dashboards.
{% enddocs %}

{% docs stg_repositories_doc %}
Contains sanitized, deduplicated snapshots of monitored repositories, extracting metadata like language, star count, and branch configuration from JSONB.
{% enddocs %}

{% docs stg_commits_doc %}
Normalized Git commit logs extracted from GitHub API Bronze tables, preserving author and committer dates, change metrics, and deduplicated on commit SHA.
{% enddocs %}

{% docs stg_pull_requests_doc %}
Cleaned pull request entities with standardized lifecycle status (open, merged, closed_unmerged), branches, line additions, and review statistics.
{% enddocs %}

{% docs stg_issues_doc %}
Cleaned issue entities filtered to exclude pull requests, with resolution state and author identity tracking.
{% enddocs %}

