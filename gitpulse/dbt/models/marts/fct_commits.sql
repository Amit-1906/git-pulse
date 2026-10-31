{{ config(materialized='table') }}

with commits as (
    select * from {{ ref('stg_commits') }}
),

final as (
    select
        commit_sha,
        repository_id,
        author_login,
        author_name,
        author_email,
        author_date,
        committer_name,
        committer_date,
        commit_message,
        additions,
        deletions,
        total_changes,
        commit_date,
        extracted_at,
        current_timestamp as dbt_loaded_at
    from commits
)

select * from final

