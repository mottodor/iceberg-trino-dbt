select
    fixture_row_id,
    batch_id,
    route_version_id,
    checkpoint_seq,
    hub_code
from {{ source('fixtures', 'route_checkpoints') }}
