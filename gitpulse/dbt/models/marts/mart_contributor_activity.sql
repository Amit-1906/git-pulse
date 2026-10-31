{{ config(materialized='table') }}

with contrib_activity as (
    select * from {{ ref('int_contributor_activity') }}
),

repos as (
    select
        repository_id,
        full_name as repository_full_name,
        primary_language
    from {{ ref('dim_repositories') }}
),

contributors as (
    select
        author_login,
        primary_name,
        primary_email,
        pr_merge_rate_pct,
        contributor_level
    from {{ ref('dim_contributors') }}
),

joined as (
    select
        ca.author_login,
        c.primary_name,
        c.primary_email,
        ca.repository_id,
        r.repository_full_name,
        r.primary_language,

        -- Velocity metrics
        ca.total_commits,
        ca.total_additions,
        ca.total_deletions,
        ca.total_lines_changed,
        ca.active_commit_days,
        ca.total_prs_opened,
        ca.total_prs_merged,
        ca.total_prs_closed_unmerged,
        ca.total_prs_currently_open,
        ca.avg_pr_merge_hours,
        ca.total_issues_opened,
        ca.total_issues_closed,

        -- Tiers
        ca.contributor_tier as repo_contributor_tier,
        c.contributor_level as global_contributor_level,
        c.pr_merge_rate_pct,

        -- Chronology
        ca.first_activity_at,
        ca.last_activity_at,
        round(cast(extract(epoch from (ca.last_activity_at - ca.first_activity_at)) / 86400.0 as numeric), 1) as activity_span_days,

        current_timestamp as dbt_generated_at

    from contrib_activity ca
    left join repos r on ca.repository_id = r.repository_id
    left join contributors c on ca.author_login = c.author_login
)

select * from joined

