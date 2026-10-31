{{ config(materialized='view') }}

with staged_prs as (
    select * from {{ ref('stg_pull_requests') }}
),

lifecycle_calculations as (
    select
        internal_record_id,
        repository_id,
        github_pr_id,
        pr_number,
        title,
        state,
        is_merged,
        standardized_status,
        author_login,
        base_branch,
        head_branch,
        created_at_gh,
        updated_at_gh,
        closed_at_gh,
        merged_at_gh,
        comments_count,
        review_comments_count,
        additions,
        deletions,
        changed_files,
        created_date,

        -- 1. ELAPSED TIME: Total clock duration from creation to final resolution (merge or close)
        case
            when coalesce(closed_at_gh, merged_at_gh) is not null
            then round(cast(extract(epoch from (coalesce(closed_at_gh, merged_at_gh) - created_at_gh)) / 3600.0 as numeric), 2)
            else null
        end as elapsed_time_hours,

        -- 2. MERGED TIME: Duration from PR open to successful merge into base branch
        case
            when is_merged and merged_at_gh is not null
            then round(cast(extract(epoch from (merged_at_gh - created_at_gh)) / 3600.0 as numeric), 2)
            else null
        end as merged_time_hours,

        -- 3. OPEN TIME: Current active duration if still open, or time spent open prior to closing
        case
            when state = 'open'
            then round(cast(extract(epoch from (current_timestamp - created_at_gh)) / 3600.0 as numeric), 2)
            else round(cast(extract(epoch from (coalesce(closed_at_gh, merged_at_gh) - created_at_gh)) / 3600.0 as numeric), 2)
        end as open_time_hours,

        -- PR change size tier
        case
            when (additions + deletions) < 50 then 'XS'
            when (additions + deletions) between 50 and 200 then 'S'
            when (additions + deletions) between 201 and 800 then 'M'
            when (additions + deletions) between 801 and 2000 then 'L'
            else 'XL'
        end as pr_size_category,

        -- Review activity indicator
        case
            when comments_count + review_comments_count > 10 then 'high_discussion'
            when comments_count + review_comments_count between 1 and 10 then 'moderate_discussion'
            else 'no_discussion'
        end as review_engagement_level

    from staged_prs
)

select * from lifecycle_calculations

