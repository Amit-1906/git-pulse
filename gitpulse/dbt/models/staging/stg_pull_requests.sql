{{ config(materialized='view') }}

with source_data as (
    select
        id as internal_record_id,
        repository_id,
        github_pr_id,
        pr_number,
        raw_payload,
        source_endpoint,
        extracted_at,
        source_updated_at,
        payload_hash,
        row_number() over (
            partition by repository_id, github_pr_id
            order by extracted_at desc, id desc
        ) as dedup_rank
    from {{ source('github_raw', 'raw_pull_requests') }}
    where github_pr_id is not null
),

cleaned as (
    select
        internal_record_id,
        repository_id,
        github_pr_id,
        pr_number,
        coalesce(cast(raw_payload->>'title' as varchar), 'Untitled Pull Request') as title,
        cast(raw_payload->>'body' as text) as body,
        lower(coalesce(cast(raw_payload->>'state' as varchar), 'open')) as state,
        coalesce(
            cast(raw_payload->>'merged' as boolean),
            raw_payload->>'merged_at' is not null,
            false
        ) as is_merged,
        case
            when coalesce(cast(raw_payload->>'merged' as boolean), raw_payload->>'merged_at' is not null, false) then 'merged'
            when lower(coalesce(cast(raw_payload->>'state' as varchar), 'open')) = 'closed' then 'closed_unmerged'
            else 'open'
        end as standardized_status,
        lower(trim(coalesce(cast(raw_payload->'user'->>'login' as varchar), 'ghost'))) as author_login,
        coalesce(cast(raw_payload->'base'->>'ref' as varchar), 'main') as base_branch,
        coalesce(cast(raw_payload->'head'->>'ref' as varchar), 'unknown') as head_branch,
        coalesce(cast(raw_payload->>'created_at' as timestamp), extracted_at) as created_at_gh,
        cast(raw_payload->>'updated_at' as timestamp) as updated_at_gh,
        cast(raw_payload->>'closed_at' as timestamp) as closed_at_gh,
        cast(raw_payload->>'merged_at' as timestamp) as merged_at_gh,
        coalesce(cast(raw_payload->>'comments' as integer), 0) as comments_count,
        coalesce(cast(raw_payload->>'review_comments' as integer), 0) as review_comments_count,
        coalesce(cast(raw_payload->>'additions' as integer), 0) as additions,
        coalesce(cast(raw_payload->>'deletions' as integer), 0) as deletions,
        coalesce(cast(raw_payload->>'changed_files' as integer), 0) as changed_files,
        cast(date_trunc('day', coalesce(cast(raw_payload->>'created_at' as timestamp), extracted_at)) as date) as created_date,
        extracted_at,
        payload_hash
    from source_data
    where dedup_rank = 1
)

select * from cleaned

