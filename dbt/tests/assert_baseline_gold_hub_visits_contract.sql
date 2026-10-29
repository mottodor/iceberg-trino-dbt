{{ config(tags=['gold', 'fixture_contract', 'expected_p1', 'expected_p2', 'expected_p4', 'reconciliation']) }}

with expected_visits (
    package_id,
    hub_code,
    visit_seq,
    arrival_event_id,
    departure_event_id,
    arrived_at,
    departed_at,
    dwell_time_hours,
    is_open
) as (
    values
        (
            'P1', 'B', 1, 'P1-E03', 'P1-E04',
            from_iso8601_timestamp('2025-01-11T08:00:00Z'),
            from_iso8601_timestamp('2025-01-11T12:00:00Z'),
            4.0, false
        ),
        (
            'P2', 'B', 1, 'P2-E03', 'P2-E04',
            from_iso8601_timestamp('2025-02-10T12:00:00Z'),
            from_iso8601_timestamp('2025-02-10T16:00:00Z'),
            4.0, false
        ),
        (
            'P2', 'X', 2, 'P2-E05', 'P2-E06',
            from_iso8601_timestamp('2025-02-10T18:00:00Z'),
            from_iso8601_timestamp('2025-02-11T04:00:00Z'),
            10.0, false
        ),
        (
            'P2', 'D', 3, 'P2-E07', 'P2-E08',
            from_iso8601_timestamp('2025-02-11T10:00:00Z'),
            from_iso8601_timestamp('2025-02-11T12:00:00Z'),
            2.0, false
        ),
        (
            'P3', 'B', 1, 'P3-E05', 'P3-E06',
            from_iso8601_timestamp('2025-02-10T15:00:00Z'),
            from_iso8601_timestamp('2025-02-10T17:00:00Z'),
            2.0, false
        ),
        (
            'P3', 'X', 2, 'P3-E07', 'P3-E08',
            from_iso8601_timestamp('2025-02-11T10:00:00Z'),
            from_iso8601_timestamp('2025-02-11T11:00:00Z'),
            1.0, false
        ),
        (
            'P4', 'D', 1, 'P4-E03', cast(null as varchar),
            from_iso8601_timestamp('2025-02-12T20:00:00Z'),
            cast(null as timestamp(3) with time zone),
            cast(null as double), true
        )
),

row_violations as (
    select
        'hub_visit_row' as violation,
        coalesce(actual.arrival_event_id, expected.arrival_event_id) as entity_id
    from {{ ref('gold_hub_visits') }} as actual
    full outer join expected_visits as expected
        on actual.package_id = expected.package_id
       and actual.hub_code = expected.hub_code
       and actual.visit_seq = expected.visit_seq
       and actual.arrival_event_id = expected.arrival_event_id
       and actual.departure_event_id is not distinct from expected.departure_event_id
       and actual.arrived_at = expected.arrived_at
       and actual.departed_at is not distinct from expected.departed_at
       and actual.is_open = expected.is_open
       and (
            actual.dwell_time_hours is not distinct from expected.dwell_time_hours
            or abs(actual.dwell_time_hours - expected.dwell_time_hours) <= 0.000001
       )
    where actual.arrival_event_id is null or expected.arrival_event_id is null
),

count_violations as (
    select
        'visit_counts' as violation,
        concat(
            cast(count(*) as varchar), ':',
            cast(count_if(not is_open) as varchar), ':',
            cast(count_if(is_open) as varchar)
        ) as entity_id
    from {{ ref('gold_hub_visits') }}
    having count(*) <> 7
        or count_if(not is_open) <> 6
        or count_if(is_open) <> 1
)

select * from row_violations
union all
select * from count_violations
