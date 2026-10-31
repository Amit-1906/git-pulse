-- Test: Staged commits must always have valid non-empty commit SHA hashes
select
    internal_record_id,
    commit_sha
from {{ ref('stg_commits') }}
where commit_sha is null
   or length(trim(commit_sha)) < 7
