{{ config(materialized='table') }}

with pr_lifecycle as (
    select * from {{ ref('int_pull_request_lifecycle') }}
),

final as (
    select
        github_pr_id,
        repository_id,
        pr_number,
        title,
        author_login,
        state,
        is_merged,
        standardized_status,
        base_branch,
        head_branch,
        created_at_gh,
        updated_at_gh,
        closed_at_gh,
        merged_at_gh,
        created_date,

        -- Measures
        additions,
        deletions,
        changed_files,
        comments_count,
        review_comments_count,
        elapsed_time_hours,
        merged_time_hours,
        open_time_hours,

        -- Cohort dimensions
        pr_size_category,
        review_engagement_level,
        current_timestamp as dbt_loaded_at
    from pr_lifecycle
)

select * from final

