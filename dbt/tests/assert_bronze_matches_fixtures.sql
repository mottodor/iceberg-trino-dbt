{{ config(tags=['bronze', 'fixture_contract']) }}

with mismatches as (
    select 'hubs' as table_name, coalesce(source.fixture_row_id, bronze.fixture_row_id) as fixture_row_id
    from {{ source('fixtures', 'hubs') }} as source
    full outer join {{ ref('bronze_hubs') }} as bronze
        on source.fixture_row_id = bronze.fixture_row_id
    where source.fixture_row_id is distinct from bronze.fixture_row_id
       or source.batch_id is distinct from bronze.batch_id
       or source.hub_code is distinct from bronze.hub_code
       or source.hub_name is distinct from bronze.hub_name
       or source.longitude is distinct from bronze.longitude
       or source.latitude is distinct from bronze.latitude

    union all

    select 'packages', coalesce(source.fixture_row_id, bronze.fixture_row_id)
    from {{ source('fixtures', 'packages') }} as source
    full outer join {{ ref('bronze_packages') }} as bronze
        on source.fixture_row_id = bronze.fixture_row_id
    where source.fixture_row_id is distinct from bronze.fixture_row_id
       or source.batch_id is distinct from bronze.batch_id
       or source.package_id is distinct from bronze.package_id
       or source.shipment_id is distinct from bronze.shipment_id
       or source.route_id is distinct from bronze.route_id

    union all

    select 'route_plan_changes', coalesce(source.fixture_row_id, bronze.fixture_row_id)
    from {{ source('fixtures', 'route_plan_changes') }} as source
    full outer join {{ ref('bronze_route_plan_changes') }} as bronze
        on source.fixture_row_id = bronze.fixture_row_id
    where source.fixture_row_id is distinct from bronze.fixture_row_id
       or source.batch_id is distinct from bronze.batch_id
       or source.route_id is distinct from bronze.route_id
       or source.route_version_id is distinct from bronze.route_version_id
       or source.effective_at is distinct from bronze.effective_at
       or source.planned_duration_hours is distinct from bronze.planned_duration_hours
       or source.sla_duration_hours is distinct from bronze.sla_duration_hours

    union all

    select 'route_checkpoints', coalesce(source.fixture_row_id, bronze.fixture_row_id)
    from {{ source('fixtures', 'route_checkpoints') }} as source
    full outer join {{ ref('bronze_route_checkpoints') }} as bronze
        on source.fixture_row_id = bronze.fixture_row_id
    where source.fixture_row_id is distinct from bronze.fixture_row_id
       or source.batch_id is distinct from bronze.batch_id
       or source.route_version_id is distinct from bronze.route_version_id
       or source.checkpoint_seq is distinct from bronze.checkpoint_seq
       or source.hub_code is distinct from bronze.hub_code

    union all

    select 'tracking_events', coalesce(source.fixture_row_id, bronze.fixture_row_id)
    from {{ source('fixtures', 'tracking_events') }} as source
    full outer join {{ ref('bronze_tracking_events') }} as bronze
        on source.fixture_row_id = bronze.fixture_row_id
    where source.fixture_row_id is distinct from bronze.fixture_row_id
       or source.batch_id is distinct from bronze.batch_id
       or source.event_id is distinct from bronze.event_id
       or source.package_id is distinct from bronze.package_id
       or source.event_type is distinct from bronze.event_type
       or source.event_at is distinct from bronze.event_at
       or source.received_at is distinct from bronze.received_at
       or source.hub_code is distinct from bronze.hub_code
       or source.longitude is distinct from bronze.longitude
       or source.latitude is distinct from bronze.latitude
)

select table_name, fixture_row_id
from mismatches
