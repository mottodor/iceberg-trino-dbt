with raw_events as (
    select *
    from {{ ref('bronze_tracking_events') }}
),

normalized_events as (
    select
        *,
        case
            when event_type in ('departed_hub', 'departed_at_hub')
                then 'departed_at_hub'
            else event_type
        end as normalized_event_type
    from raw_events
)

select
    fixture_row_id,
    batch_id,
    event_id,
    package_id,
    normalized_event_type as event_type,
    from_iso8601_timestamp(event_at) as event_at,
    from_iso8601_timestamp(received_at) as received_at,
    hub_code,
    cast(longitude as double) as longitude,
    cast(latitude as double) as latitude,
    to_hex(
        sha256(
            to_utf8(
                package_id || chr(31)
                || normalized_event_type || chr(31)
                || event_at || chr(31)
                || received_at || chr(31)
                || hub_code || chr(31)
                || longitude || chr(31)
                || latitude
            )
        )
    ) as event_payload_fingerprint
from normalized_events
