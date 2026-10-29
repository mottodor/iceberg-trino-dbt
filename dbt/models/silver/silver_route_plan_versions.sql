with typed_changes as (
    select
        fixture_row_id as route_change_fixture_row_id,
        route_id,
        route_version_id,
        from_iso8601_timestamp(effective_at) as valid_from,
        cast(planned_duration_hours as bigint) as planned_duration_hours,
        cast(sla_duration_hours as bigint) as sla_duration_hours
    from {{ ref('bronze_route_plan_changes') }}
),

version_intervals as (
    select
        *,
        lead(valid_from) over (
            partition by route_id
            order by valid_from, route_version_id
        ) as valid_to
    from typed_changes
),

checkpoint_metrics as (
    select
        route_version_id,
        count(*) as checkpoint_count,
        count(distance_from_previous_meters) as segment_count,
        sum(distance_from_previous_meters) as planned_distance_meters
    from {{ ref('silver_route_plan_checkpoint_segments') }}
    group by route_version_id
)

select
    versions.route_change_fixture_row_id,
    versions.route_id,
    versions.route_version_id,
    versions.valid_from,
    versions.valid_to,
    versions.valid_to is null as is_current,
    versions.planned_duration_hours,
    versions.sla_duration_hours,
    checkpoints.checkpoint_count,
    checkpoints.segment_count,
    checkpoints.planned_distance_meters
from version_intervals as versions
left join checkpoint_metrics as checkpoints
    on versions.route_version_id = checkpoints.route_version_id
