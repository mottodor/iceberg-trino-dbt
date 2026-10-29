select
    fixture_row_id,
    batch_id,
    hub_code,
    hub_name,
    longitude,
    latitude
from {{ source('fixtures', 'hubs') }}
