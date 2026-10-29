select
    fixture_row_id,
    batch_id,
    package_id,
    shipment_id,
    route_id
from {{ source('fixtures', 'packages') }}
