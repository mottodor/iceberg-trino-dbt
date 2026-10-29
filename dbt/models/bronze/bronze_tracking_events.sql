select
    fixture_row_id,
    batch_id,
    event_id,
    package_id,
    event_type,
    event_at,
    received_at,
    hub_code,
    longitude,
    latitude
from {{ source('fixtures', 'tracking_events') }}
