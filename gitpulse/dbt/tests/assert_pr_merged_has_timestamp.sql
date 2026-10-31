-- Test: Any PR marked as merged must have a valid merged_at timestamp
select
    github_pr_id,
    pr_number,
    is_merged,
    merged_at_gh
from {{ ref('fct_pull_requests') }}
where is_merged = true
  and merged_at_gh is null

