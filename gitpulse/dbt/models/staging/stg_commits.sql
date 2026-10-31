{{ config(materialized='view') }}

with source_data as (
    select
        id as internal_record_id,
        repository_id,
        lower(trim(commit_sha)) as commit_sha,
        raw_payload,
        source_endpoint,
        extracted_at,
        source_updated_at,
        payload_hash,
        row_number() over (
            partition by repository_id, lower(trim(commit_sha))
            order by extracted_at desc, id desc
        ) as dedup_rank
    from {{ source('github_raw', 'raw_commits') }}
    where commit_sha is not null
      and length(trim(commit_sha)) >= 7
),

cleaned as (
    select
        internal_record_id,
        repository_id,
        commit_sha,
        coalesce(cast(raw_payload->'commit'->'author'->>'name' as varchar), 'Unknown Author') as author_name,
        lower(trim(coalesce(cast(raw_payload->'commit'->'author'->>'email' as varchar), 'unknown@gitpulse.local'))) as author_email,
        lower(trim(coalesce(cast(raw_payload->'author'->>'login' as varchar), 'ghost'))) as author_login,
        coalesce(
            cast(raw_payload->'commit'->'author'->>'date' as timestamp),
            source_updated_at,
            extracted_at
        ) as author_date,
        coalesce(cast(raw_payload->'commit'->'committer'->>'name' as varchar), 'Unknown Committer') as committer_name,
        lower(trim(coalesce(cast(raw_payload->'commit'->'committer'->>'email' as varchar), 'unknown@gitpulse.local'))) as committer_email,
        coalesce(
            cast(raw_payload->'commit'->'committer'->>'date' as timestamp),
            source_updated_at,
            extracted_at
        ) as committer_date,
        coalesce(cast(raw_payload->'commit'->>'message' as text), '') as commit_message,
        coalesce(cast(raw_payload->'stats'->>'additions' as integer), 0) as additions,
        coalesce(cast(raw_payload->'stats'->>'deletions' as integer), 0) as deletions,
        coalesce(
            cast(raw_payload->'stats'->>'total' as integer),
            coalesce(cast(raw_payload->'stats'->>'additions' as integer), 0) + coalesce(cast(raw_payload->'stats'->>'deletions' as integer), 0),
            0
        ) as total_changes,
        cast(date_trunc('day', coalesce(
            cast(raw_payload->'commit'->'author'->>'date' as timestamp),
            source_updated_at,
            extracted_at
        )) as date) as commit_date,
        extracted_at,
        payload_hash
    from source_data
    where dedup_rank = 1
)

select * from cleaned

