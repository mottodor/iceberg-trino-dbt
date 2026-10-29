{{ config(tags=['silver', 'dq']) }}

select
    event_id,
    count(*) as raw_row_count,
    count(distinct event_payload_fingerprint) as payload_variant_count
from {{ ref('silver_tracking_events_typed') }}
group by event_id
having count(distinct event_payload_fingerprint) > 1
