{{ config(materialized='view') }}

with source_data as (
    select
        id as internal_record_id,
        repository_id,
        github_repo_id,
        full_name,
        raw_payload,
        source_endpoint,
        extracted_at,
        source_updated_at,
        payload_hash,
        row_number() over (
            partition by github_repo_id
            order by extracted_at desc, id desc
        ) as dedup_rank
    from {{ source('github_raw', 'raw_repositories') }}
    where github_repo_id is not null
),

cleaned as (
    select
        internal_record_id,
        coalesce(repository_id, 0) as repository_id,
        github_repo_id,
        lower(trim(coalesce(cast(raw_payload->>'full_name' as varchar), full_name))) as full_name,
        cast(raw_payload->>'name' as varchar) as repo_name,
        cast(raw_payload->'owner'->>'login' as varchar) as owner_login,
        cast(raw_payload->>'description' as text) as description,
        coalesce(cast(raw_payload->>'default_branch' as varchar), 'main') as default_branch,
        lower(coalesce(cast(raw_payload->>'visibility' as varchar), 'public')) as visibility,
        coalesce(cast(raw_payload->>'language' as varchar), 'Unknown') as primary_language,
        coalesce(cast(raw_payload->>'stargazers_count' as integer), 0) as stargazers_count,
        coalesce(cast(raw_payload->>'forks_count' as integer), 0) as forks_count,
        coalesce(cast(raw_payload->>'open_issues_count' as integer), 0) as open_issues_count,
        coalesce(cast(raw_payload->>'watchers_count' as integer), 0) as watchers_count,
        coalesce(cast(raw_payload->>'is_template' as boolean), false) as is_template,
        coalesce(cast(raw_payload->>'archived' as boolean), false) as is_archived,
        cast(raw_payload->>'created_at' as timestamp) as created_at_gh,
        cast(raw_payload->>'updated_at' as timestamp) as updated_at_gh,
        cast(raw_payload->>'pushed_at' as timestamp) as pushed_at_gh,
        extracted_at,
        payload_hash
    from source_data
    where dedup_rank = 1
)

select * from cleaned

