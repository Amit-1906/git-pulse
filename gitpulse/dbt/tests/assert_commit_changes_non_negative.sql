-- Test: Commit additions and deletions must be non-negative
select
    commit_sha,
    additions,
    deletions,
    total_changes
from {{ ref('fct_commits') }}
where additions < 0
   or deletions < 0
   or total_changes < 0

