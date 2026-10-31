{{ config(materialized='view') }}

with commit_daily as (
    select
        repository_id,
        commit_date as activity_date,
        count(distinct commit_sha) as daily_commits,
        count(distinct author_login) as active_committers,
        sum(additions) as daily_additions,
        sum(deletions) as daily_deletions,
        sum(total_changes) as daily_lines_changed
    from {{ ref('stg_commits') }}
    group by repository_id, commit_date
),

pr_daily as (
    select
        repository_id,
        created_date as activity_date,
        count(distinct github_pr_id) as daily_prs_opened,
        count(distinct case when is_merged then github_pr_id end) as daily_prs_merged,
        count(distinct author_login) as active_pr_authors
    from {{ ref('int_pull_request_lifecycle') }}
    group by repository_id, created_date
),

issue_daily as (
    select
        repository_id,
        created_date as activity_date,
        count(distinct github_issue_id) as daily_issues_opened,
        count(distinct case when is_closed then github_issue_id end) as daily_issues_closed,
        count(distinct author_login) as active_issue_reporters
    from {{ ref('int_issue_lifecycle') }}
    group by repository_id, created_date
),

all_activity_dates as (
    select repository_id, activity_date from commit_daily
    union
    select repository_id, activity_date from pr_daily
    union
    select repository_id, activity_date from issue_daily
),

combined as (
    select
        ad.repository_id,
        ad.activity_date,
        coalesce(cd.daily_commits, 0) as daily_commits,
        coalesce(cd.active_committers, 0) as active_committers,
        coalesce(cd.daily_additions, 0) as daily_additions,
        coalesce(cd.daily_deletions, 0) as daily_deletions,
        coalesce(cd.daily_lines_changed, 0) as daily_lines_changed,
        coalesce(pd.daily_prs_opened, 0) as daily_prs_opened,
        coalesce(pd.daily_prs_merged, 0) as daily_prs_merged,
        coalesce(pd.active_pr_authors, 0) as active_pr_authors,
        coalesce(id.daily_issues_opened, 0) as daily_issues_opened,
        coalesce(id.daily_issues_closed, 0) as daily_issues_closed,
        coalesce(id.active_issue_reporters, 0) as active_issue_reporters,

        -- Total distinct action points
        coalesce(cd.daily_commits, 0) + coalesce(pd.daily_prs_opened, 0) + coalesce(id.daily_issues_opened, 0) as total_activity_events

    from all_activity_dates ad
    left join commit_daily cd on ad.repository_id = cd.repository_id and ad.activity_date = cd.activity_date
    left join pr_daily pd on ad.repository_id = pd.repository_id and ad.activity_date = pd.activity_date
    left join issue_daily id on ad.repository_id = id.repository_id and ad.activity_date = id.activity_date
)

select * from combined

