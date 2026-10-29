with arrivals as (
    select
        event_id as arrival_event_id,
        package_id,
        hub_code,
        event_at as arrived_at,
        received_at as arrival_received_at,
        package_event_seq as arrival_event_seq,
        row_number() over (
            partition by package_id
            order by package_event_seq
        ) as visit_seq,
        lead(package_event_seq) over (
            partition by package_id, hub_code
            order by package_event_seq
        ) as next_same_hub_arrival_seq
    from {{ ref('silver_tracking_events') }}
    where event_type = 'arrived_at_hub'
),

departures as (
    select
        event_id as departure_event_id,
        package_id,
        hub_code,
        event_at as departed_at,
        received_at as departure_received_at,
        package_event_seq as departure_event_seq
    from {{ ref('silver_tracking_events') }}
    where event_type = 'departed_at_hub'
),

ranked_pairs as (
    select
        arrivals.*,
        departures.departure_event_id,
        departures.departed_at,
        departures.departure_received_at,
        departures.departure_event_seq,
        row_number() over (
            partition by arrivals.arrival_event_id
            order by departures.departure_event_seq
        ) as departure_rank
    from arrivals
    left join departures
        on arrivals.package_id = departures.package_id
       and arrivals.hub_code = departures.hub_code
       and departures.departure_event_seq > arrivals.arrival_event_seq
       and (
            arrivals.next_same_hub_arrival_seq is null
            or departures.departure_event_seq < arrivals.next_same_hub_arrival_seq
       )
)

select
    arrival_event_id,
    departure_event_id,
    package_id,
    hub_code,
    visit_seq,
    arrived_at,
    departed_at,
    cast(date_diff('second', arrived_at, departed_at) as double) / 3600.0 as dwell_time_hours,
    departed_at is null as is_open
from ranked_pairs
where departure_rank = 1
