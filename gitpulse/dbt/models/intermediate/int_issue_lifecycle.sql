{{ config(materialized='view') }}

with staged_issues as (
    select * from {{ ref('stg_issues') }}
),

lifecycle_calculations as (
    select
        internal_record_id,
        repository_id,
        github_issue_id,
        issue_number,
        title,
        state,
        author_login,
        created_at_gh,
        updated_at_gh,
        closed_at_gh,
        comments_count,
        state_reason,
        is_closed,
        created_date,

        -- 1. RESOLUTION TIME: Total time to close the issue (hours and days)
        case
            when closed_at_gh is not null
            then round(cast(extract(epoch from (closed_at_gh - created_at_gh)) / 3600.0 as numeric), 2)
            else null
        end as resolution_time_hours,

        case
            when closed_at_gh is not null
            then round(cast(extract(epoch from (closed_at_gh - created_at_gh)) / 86400.0 as numeric), 2)
            else null
        end as resolution_time_days,

        -- 2. OPEN TIME: Current active backlog age if open, or duration prior to closing
        case
            when state = 'open'
            then round(cast(extract(epoch from (current_timestamp - created_at_gh)) / 3600.0 as numeric), 2)
            else round(cast(extract(epoch from (closed_at_gh - created_at_gh)) / 3600.0 as numeric), 2)
        end as open_time_hours,

        -- Resolution speed cohort
        case
            when closed_at_gh is null then 'unresolved'
            when extract(epoch from (closed_at_gh - created_at_gh)) < 86400.0 then 'fast_resolved_under_24h'
            when extract(epoch from (closed_at_gh - created_at_gh)) between 86400.0 and 604800.0 then 'standard_1_to_7d'
            when extract(epoch from (closed_at_gh - created_at_gh)) between 604800.0 and 2592000.0 then 'slow_7_to_30d'
            else 'stale_resolution_gt_30d'
        end as resolution_cohort,

        -- Community engagement cohort
        case
            when comments_count > 10 then 'high_activity'
            when comments_count between 2 and 10 then 'moderate_activity'
            when comments_count = 1 then 'low_activity'
            else 'no_comments'
        end as engagement_level

    from staged_issues
)

select * from lifecycle_calculations

