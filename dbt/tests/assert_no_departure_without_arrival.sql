{{ config(tags=['silver', 'dq']) }}

with hub_events as (
    select
        event_id,
        package_id,
        hub_code,
        event_type,
        event_at,
        received_at,
        case event_type
            when 'arrived_at_hub' then 1
            when 'departed_at_hub' then -1
        end as visit_delta
    from {{ ref('silver_tracking_events') }}
    where event_type in ('arrived_at_hub', 'departed_at_hub')
),

sequenced_hub_events as (
    select
        *,
        coalesce(
            sum(visit_delta) over (
                partition by package_id, hub_code
                order by event_at, received_at, event_id
                rows between unbounded preceding and 1 preceding
            ),
            0
        ) as open_visits_before
    from hub_events
)

select
    event_id,
    package_id,
    hub_code,
    event_at,
    open_visits_before
from sequenced_hub_events
where visit_delta = -1
  and open_visits_before = 0
