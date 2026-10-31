{{ config(materialized='table') }}

with daily_activity as (
    select * from {{ ref('int_repository_activity') }}
),

repos as (
    select
        repository_id,
        full_name,
        repo_name,
        owner_login,
        primary_language,
        stargazers_count,
        forks_count
    from {{ ref('dim_repositories') }}
),

joined as (
    select
        da.repository_id,
        r.full_name as repository_full_name,
        r.repo_name,
        r.owner_login,
        r.primary_language,
        da.activity_date,

        -- Daily volume measures
        da.daily_commits,
        da.active_committers,
        da.daily_additions,
        da.daily_deletions,
        da.daily_lines_changed,
        da.daily_prs_opened,
        da.daily_prs_merged,
        da.active_pr_authors,
        da.daily_issues_opened,
        da.daily_issues_closed,
        da.total_activity_events,

        -- Rolling 7-day and 30-day velocity trends
        sum(da.daily_commits) over (
            partition by da.repository_id
            order by da.activity_date
            rows between 6 preceding and current row
        ) as rolling_7d_commits,

        sum(da.daily_commits) over (
            partition by da.repository_id
            order by da.activity_date
            rows between 29 preceding and current row
        ) as rolling_30d_commits,

        sum(da.daily_lines_changed) over (
            partition by da.repository_id
            order by da.activity_date
            rows between 6 preceding and current row
        ) as rolling_7d_lines_changed,

        current_timestamp as dbt_generated_at

    from daily_activity da
    left join repos r on da.repository_id = r.repository_id
)

select * from joined

