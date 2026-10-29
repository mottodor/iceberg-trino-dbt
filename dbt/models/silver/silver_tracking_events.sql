with ranked_events as (
    select
        *,
        count(*) over (partition by event_id) as raw_event_row_count,
        row_number() over (
            partition by event_id
            order by event_at, received_at, fixture_row_id
        ) as canonical_rank
    from {{ ref('silver_tracking_events_typed') }}
),

canonical_events as (
    select
        fixture_row_id as canonical_fixture_row_id,
        batch_id as canonical_batch_id,
        event_id,
        package_id,
        event_type,
        event_at,
        received_at,
        hub_code,
        longitude,
        latitude,
        event_payload_fingerprint,
        raw_event_row_count
    from ranked_events
    where canonical_rank = 1
)

select
    *,
    row_number() over (
        partition by package_id
        order by event_at, received_at, event_id
    ) as package_event_seq
from canonical_events
