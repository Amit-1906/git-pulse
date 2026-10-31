-- Test: Closed issues must have a closed_at timestamp on or after created_at
select
    github_issue_id,
    created_at_gh,
    closed_at_gh
from {{ ref('fct_issues') }}
where closed_at_gh is not null
  and closed_at_gh < created_at_gh

