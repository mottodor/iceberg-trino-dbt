select
    fixture_row_id,
    batch_id,
    route_id,
    route_version_id,
    effective_at,
    planned_duration_hours,
    sla_duration_hours
from {{ source('fixtures', 'route_plan_changes') }}
