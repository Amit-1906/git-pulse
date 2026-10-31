{{ config(materialized='view') }}

with commits_summary as (
    select
        repository_id,
        author_login,
        count(distinct commit_sha) as total_commits,
        sum(additions) as total_additions,
        sum(deletions) as total_deletions,
        sum(total_changes) as total_lines_changed,
        min(author_date) as first_commit_at,
        max(author_date) as last_commit_at,
        count(distinct commit_date) as active_commit_days
    from {{ ref('stg_commits') }}
    where author_login is not null
    group by repository_id, author_login
),

prs_summary as (
    select
        repository_id,
        author_login,
        count(distinct github_pr_id) as total_prs_opened,
        count(distinct case when is_merged then github_pr_id end) as total_prs_merged,
        count(distinct case when state = 'closed' and not is_merged then github_pr_id end) as total_prs_closed_unmerged,
        count(distinct case when state = 'open' then github_pr_id end) as total_prs_currently_open,
        avg(case when is_merged then merged_time_hours end) as avg_merge_time_hours,
        min(created_at_gh) as first_pr_at,
        max(created_at_gh) as last_pr_at
    from {{ ref('int_pull_request_lifecycle') }}
    where author_login is not null
    group by repository_id, author_login
),

issues_summary as (
    select
        repository_id,
        author_login,
        count(distinct github_issue_id) as total_issues_opened,
        count(distinct case when is_closed then github_issue_id end) as total_issues_closed,
        min(created_at_gh) as first_issue_at,
        max(created_at_gh) as last_issue_at
    from {{ ref('int_issue_lifecycle') }}
    where author_login is not null
    group by repository_id, author_login
),

all_contributors as (
    select distinct repository_id, author_login from commits_summary
    union
    select distinct repository_id, author_login from prs_summary
    union
    select distinct repository_id, author_login from issues_summary
),

joined as (
    select
        ac.repository_id,
        ac.author_login,
        coalesce(cs.total_commits, 0) as total_commits,
        coalesce(cs.total_additions, 0) as total_additions,
        coalesce(cs.total_deletions, 0) as total_deletions,
        coalesce(cs.total_lines_changed, 0) as total_lines_changed,
        coalesce(cs.active_commit_days, 0) as active_commit_days,
        coalesce(ps.total_prs_opened, 0) as total_prs_opened,
        coalesce(ps.total_prs_merged, 0) as total_prs_merged,
        coalesce(ps.total_prs_closed_unmerged, 0) as total_prs_closed_unmerged,
        coalesce(ps.total_prs_currently_open, 0) as total_prs_currently_open,
        round(cast(coalesce(ps.avg_merge_time_hours, 0.0) as numeric), 2) as avg_pr_merge_hours,
        coalesce(iss.total_issues_opened, 0) as total_issues_opened,
        coalesce(iss.total_issues_closed, 0) as total_issues_closed,

        -- Overall timeline
        least(cs.first_commit_at, ps.first_pr_at, iss.first_issue_at) as first_activity_at,
        greatest(cs.last_commit_at, ps.last_pr_at, iss.last_issue_at) as last_activity_at,

        -- Contributor classification tier
        case
            when coalesce(cs.total_commits, 0) >= 50 or coalesce(ps.total_prs_merged, 0) >= 20 then 'core_maintainer'
            when coalesce(cs.total_commits, 0) >= 10 or coalesce(ps.total_prs_merged, 0) >= 5 then 'regular_contributor'
            when coalesce(cs.total_commits, 0) >= 2 or coalesce(ps.total_prs_opened, 0) >= 1 then 'casual_contributor'
            else 'community_reporter'
        end as contributor_tier

    from all_contributors ac
    left join commits_summary cs on ac.repository_id = cs.repository_id and ac.author_login = cs.author_login
    left join prs_summary ps on ac.repository_id = ps.repository_id and ac.author_login = ps.author_login
    left join issues_summary iss on ac.repository_id = iss.repository_id and ac.author_login = iss.author_login
)

select * from joined
