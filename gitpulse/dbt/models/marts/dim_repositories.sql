{{ config(materialized='table') }}

with staged_repos as (
    select * from {{ ref('stg_repositories') }}
),

commit_totals as (
    select
        repository_id,
        count(distinct commit_sha) as total_commits_recorded,
        count(distinct author_login) as unique_committers
    from {{ ref('stg_commits') }}
    group by repository_id
),

pr_totals as (
    select
        repository_id,
        count(distinct github_pr_id) as total_prs_recorded,
        count(distinct case when is_merged then github_pr_id end) as total_prs_merged,
        avg(case when is_merged then merged_time_hours end) as avg_pr_merge_hours
    from {{ ref('int_pull_request_lifecycle') }}
    group by repository_id
),

final as (
    select
        sr.internal_record_id,
        sr.repository_id,
        sr.github_repo_id,
        sr.full_name,
        sr.repo_name,
        sr.owner_login,
        sr.description,
        sr.default_branch,
        sr.visibility,
        sr.primary_language,
        sr.stargazers_count,
        sr.forks_count,
        sr.open_issues_count,
        sr.watchers_count,
        sr.is_template,
        sr.is_archived,
        sr.created_at_gh,
        sr.updated_at_gh,
        sr.pushed_at_gh,

        -- Aggregated metrics
        coalesce(ct.total_commits_recorded, 0) as total_commits_recorded,
        coalesce(ct.unique_committers, 0) as unique_committers,
        coalesce(pt.total_prs_recorded, 0) as total_prs_recorded,
        coalesce(pt.total_prs_merged, 0) as total_prs_merged,
        round(cast(coalesce(pt.avg_pr_merge_hours, 0.0) as numeric), 2) as avg_pr_merge_hours,

        current_timestamp as dbt_updated_at

    from staged_repos sr
    left join commit_totals ct on sr.repository_id = ct.repository_id
    left join pr_totals pt on sr.repository_id = pt.repository_id
)

select * from final
