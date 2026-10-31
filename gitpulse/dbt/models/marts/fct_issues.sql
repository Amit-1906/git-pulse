{{ config(materialized='table') }}

with issue_lifecycle as (
    select * from {{ ref('int_issue_lifecycle') }}
),

final as (
    select
        github_issue_id,
        repository_id,
        issue_number,
        title,
        author_login,
        state,
        is_closed,
        state_reason,
        created_at_gh,
        updated_at_gh,
        closed_at_gh,
        created_date,

        -- Measures
        comments_count,
        resolution_time_hours,
        resolution_time_days,
        open_time_hours,

        -- Cohorts
        resolution_cohort,
        engagement_level,
        current_timestamp as dbt_loaded_at
    from issue_lifecycle
)

select * from final

