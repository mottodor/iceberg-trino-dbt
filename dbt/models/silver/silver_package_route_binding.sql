with package_pickups as (
    select
        package_id,
        min(event_at) as picked_up_at
    from {{ ref('silver_tracking_events') }}
    where event_type = 'picked_up'
    group by package_id
)

select
    packages.package_id,
    packages.shipment_id,
    packages.route_id,
    pickups.picked_up_at,
    versions.route_version_id,
    versions.valid_from as route_valid_from,
    versions.valid_to as route_valid_to,
    versions.planned_duration_hours,
    versions.sla_duration_hours,
    versions.planned_distance_meters,
    date_add('hour', versions.sla_duration_hours, pickups.picked_up_at) as promised_delivery_at
from {{ ref('bronze_packages') }} as packages
inner join package_pickups as pickups
    on packages.package_id = pickups.package_id
left join {{ ref('silver_route_plan_versions') }} as versions
    on packages.route_id = versions.route_id
   and pickups.picked_up_at >= versions.valid_from
   and (versions.valid_to is null or pickups.picked_up_at < versions.valid_to)
