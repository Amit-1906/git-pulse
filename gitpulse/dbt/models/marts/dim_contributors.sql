{{ config(materialized='table') }}

with contributor_summary as (
    select
        author_login,
        count(distinct repository_id) as total_repositories_contributed,
        sum(total_commits) as lifetime_commits,
        sum(total_additions) as lifetime_additions,
        sum(total_deletions) as lifetime_deletions,
        sum(total_lines_changed) as lifetime_lines_changed,
        sum(total_prs_opened) as lifetime_prs_opened,
        sum(total_prs_merged) as lifetime_prs_merged,
        sum(total_issues_opened) as lifetime_issues_opened,
        min(first_activity_at) as first_seen_at,
        max(last_activity_at) as last_seen_at
    from {{ ref('int_contributor_activity') }}
    where author_login is not null
    group by author_login
),

author_metadata as (
    select distinct on (author_login)
        author_login,
        author_name,
        author_email
    from {{ ref('stg_commits') }}
    where author_login is not null
    order by author_login, author_date desc
),

final as (
    select
        cs.author_login,
        coalesce(am.author_name, cs.author_login) as primary_name,
        coalesce(am.author_email, 'unknown@gitpulse.local') as primary_email,
        cs.total_repositories_contributed,
        cs.lifetime_commits,
        cs.lifetime_additions,
        cs.lifetime_deletions,
        cs.lifetime_lines_changed,
        cs.lifetime_prs_opened,
        cs.lifetime_prs_merged,
        cs.lifetime_issues_opened,

        -- PR merge efficiency
        case
            when cs.lifetime_prs_opened > 0
            then round(cast((cs.lifetime_prs_merged::numeric / cs.lifetime_prs_opened::numeric) * 100.0 as numeric), 1)
            else 0.0
        end as pr_merge_rate_pct,

        -- Overall contributor level
        case
            when cs.lifetime_commits >= 50 or cs.lifetime_prs_merged >= 20 then 'core'
            when cs.lifetime_commits >= 10 or cs.lifetime_prs_merged >= 5 then 'regular'
            when cs.lifetime_commits >= 2 or cs.lifetime_prs_opened >= 1 then 'casual'
            else 'reporter'
        end as contributor_level,

        cs.first_seen_at,
        cs.last_seen_at,
        current_timestamp as dbt_updated_at

    from contributor_summary cs
    left join author_metadata am on cs.author_login = am.author_login
)

select * from final
