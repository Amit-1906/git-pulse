{{ config(materialized='view') }}

with source_data as (
    select
        id as internal_record_id,
        repository_id,
        github_issue_id,
        issue_number,
        raw_payload,
        source_endpoint,
        extracted_at,
        source_updated_at,
        payload_hash,
        row_number() over (
            partition by repository_id, github_issue_id
            order by extracted_at desc, id desc
        ) as dedup_rank
    from {{ source('github_raw', 'raw_issues') }}
    where github_issue_id is not null
      and not (raw_payload ? 'pull_request')
),

cleaned as (
    select
        internal_record_id,
        repository_id,
        github_issue_id,
        issue_number,
        coalesce(cast(raw_payload->>'title' as varchar), 'Untitled Issue') as title,
        cast(raw_payload->>'body' as text) as body,
        lower(coalesce(cast(raw_payload->>'state' as varchar), 'open')) as state,
        lower(trim(coalesce(cast(raw_payload->'user'->>'login' as varchar), 'ghost'))) as author_login,
        coalesce(cast(raw_payload->>'created_at' as timestamp), extracted_at) as created_at_gh,
        cast(raw_payload->>'updated_at' as timestamp) as updated_at_gh,
        cast(raw_payload->>'closed_at' as timestamp) as closed_at_gh,
        coalesce(cast(raw_payload->>'comments' as integer), 0) as comments_count,
        coalesce(cast(raw_payload->>'state_reason' as varchar), 'completed') as state_reason,
        case
            when lower(coalesce(cast(raw_payload->>'state' as varchar), 'open')) = 'closed' then true
            else false
        end as is_closed,
        cast(date_trunc('day', coalesce(cast(raw_payload->>'created_at' as timestamp), extracted_at)) as date) as created_date,
        extracted_at,
        payload_hash
    from source_data
    where dedup_rank = 1
)

select * from cleaned

