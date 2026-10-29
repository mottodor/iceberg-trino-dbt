with ranked_events as (
    select
        *,
        row_number() over (
            partition by package_id
            order by event_at desc, received_at desc, event_id desc
        ) as current_rank
    from {{ ref('silver_tracking_events') }}
)

select
    package_id,
    event_id as current_event_id,
    event_type as current_status,
    event_at as current_event_at,
    received_at as current_event_received_at,
    hub_code as current_hub_code,
    longitude as current_longitude,
    latitude as current_latitude,
    package_event_seq as current_event_seq
from ranked_events
where current_rank = 1
