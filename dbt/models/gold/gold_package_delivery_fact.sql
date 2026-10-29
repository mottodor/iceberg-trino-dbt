with package_events as (
    select
        bindings.package_id,
        events.event_id,
        events.event_type,
        events.event_at,
        events.received_at,
        events.longitude,
        events.latitude,
        events.package_event_seq
    from {{ ref('silver_package_route_binding') }} as bindings
    inner join {{ ref('silver_tracking_events') }} as events
        on bindings.package_id = events.package_id
),

milestones as (
    select
        package_id,
        min(event_at) filter (where event_type = 'out_for_delivery') as out_for_delivery_at,
        min(event_at) filter (where event_type = 'delivered') as delivered_at
    from package_events
    group by package_id
),

ordered_route_points as (
    select
        *,
        lag(longitude) over (
            partition by package_id
            order by event_at, received_at, event_id
        ) as previous_longitude,
        lag(latitude) over (
            partition by package_id
            order by event_at, received_at, event_id
        ) as previous_latitude
    from package_events
    where longitude is not null
      and latitude is not null
),

route_segments as (
    select
        package_id,
        case
            when previous_longitude is null or previous_latitude is null then 0.0
            else {{ great_circle_distance_meters(
                'previous_longitude',
                'previous_latitude',
                'longitude',
                'latitude'
            ) }}
        end as segment_distance_meters
    from ordered_route_points
),

actual_routes as (
    select
        package_id,
        sum(segment_distance_meters) as actual_distance_meters
    from route_segments
    group by package_id
),

visit_metrics as (
    select
        package_id,
        count(*) as visit_count,
        count_if(not is_open) as completed_visit_count,
        count_if(is_open) as open_visit_count,
        coalesce(sum(dwell_time_hours) filter (where not is_open), 0.0) as completed_dwell_hours
    from {{ ref('gold_hub_visits') }}
    group by package_id
)

select
    bindings.package_id,
    bindings.shipment_id,
    bindings.route_id,
    bindings.route_version_id,
    current_state.current_status,
    current_state.current_event_at,
    bindings.picked_up_at,
    milestones.out_for_delivery_at,
    milestones.delivered_at,
    bindings.promised_delivery_at,
    bindings.planned_duration_hours,
    bindings.sla_duration_hours,
    case
        when milestones.delivered_at is null then null
        else cast(date_diff('second', bindings.picked_up_at, milestones.delivered_at) as double) / 3600.0
    end as delivery_duration_hours,
    case
        when milestones.delivered_at is null then null
        else greatest(
            cast(date_diff('second', bindings.promised_delivery_at, milestones.delivered_at) as double) / 3600.0,
            0.0
        )
    end as delay_hours,
    case
        when milestones.delivered_at is null then null
        else milestones.delivered_at <= bindings.promised_delivery_at
    end as is_on_time,
    bindings.planned_distance_meters,
    actual_routes.actual_distance_meters,
    case
        when milestones.delivered_at is null then null
        else actual_routes.actual_distance_meters - bindings.planned_distance_meters
    end as final_route_deviation_meters,
    case
        when milestones.delivered_at is null or bindings.planned_distance_meters = 0 then null
        else (
            actual_routes.actual_distance_meters - bindings.planned_distance_meters
        ) / bindings.planned_distance_meters * 100.0
    end as final_route_deviation_pct,
    coalesce(visit_metrics.visit_count, bigint '0') as visit_count,
    coalesce(visit_metrics.completed_visit_count, bigint '0') as completed_visit_count,
    coalesce(visit_metrics.open_visit_count, bigint '0') as open_visit_count,
    coalesce(visit_metrics.completed_dwell_hours, 0.0) as completed_dwell_hours
from {{ ref('silver_package_route_binding') }} as bindings
inner join {{ ref('silver_package_current_state') }} as current_state
    on bindings.package_id = current_state.package_id
inner join milestones
    on bindings.package_id = milestones.package_id
inner join actual_routes
    on bindings.package_id = actual_routes.package_id
left join visit_metrics
    on bindings.package_id = visit_metrics.package_id
