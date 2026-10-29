-- depends_on: {{ ref('gold_package_delivery_fact') }}
{{ config(tags=['gold', 'fixture_contract', 'expected_p1', 'expected_p2', 'expected_p4', 'reconciliation']) }}

with expected_packages (
    package_id,
    shipment_id,
    route_version_id,
    current_status,
    picked_up_at,
    delivered_at,
    promised_delivery_at,
    delivery_duration_hours,
    delay_hours,
    is_on_time,
    visit_count,
    completed_visit_count,
    open_visit_count,
    completed_dwell_hours
) as (
    values
        (
            'P1', 'S1', 'R1-V1', 'delivered',
            from_iso8601_timestamp('2025-01-10T08:00:00Z'),
            from_iso8601_timestamp('2025-01-12T08:00:00Z'),
            from_iso8601_timestamp('2025-01-12T08:00:00Z'),
            48.0, 0.0, true, bigint '1', bigint '1', bigint '0', 4.0
        ),
        (
            'P2', 'S2', 'R1-V2', 'delivered',
            from_iso8601_timestamp('2025-02-10T08:00:00Z'),
            from_iso8601_timestamp('2025-02-12T08:00:00Z'),
            from_iso8601_timestamp('2025-02-11T20:00:00Z'),
            48.0, 12.0, false, bigint '3', bigint '3', bigint '0', 16.0
        ),
        (
            'P3', 'S2', 'R1-V2', 'delivered',
            from_iso8601_timestamp('2025-02-10T09:00:00Z'),
            from_iso8601_timestamp('2025-02-11T21:00:00Z'),
            from_iso8601_timestamp('2025-02-11T21:00:00Z'),
            36.0, 0.0, true, bigint '2', bigint '2', bigint '0', 3.0
        ),
        (
            'P4', 'S3', 'R1-V2', 'arrived_at_hub',
            from_iso8601_timestamp('2025-02-12T08:00:00Z'),
            cast(null as timestamp(3) with time zone),
            from_iso8601_timestamp('2025-02-13T20:00:00Z'),
            cast(null as double), cast(null as double), cast(null as boolean),
            bigint '1', bigint '0', bigint '1', 0.0
        )
),

row_violations as (
    select
        'package_fact_row' as violation,
        coalesce(actual.package_id, expected.package_id) as entity_id
    from {{ ref('gold_package_delivery_fact') }} as actual
    full outer join expected_packages as expected
        on actual.package_id = expected.package_id
       and actual.shipment_id = expected.shipment_id
       and actual.route_version_id = expected.route_version_id
       and actual.current_status = expected.current_status
       and actual.picked_up_at = expected.picked_up_at
       and actual.delivered_at is not distinct from expected.delivered_at
       and actual.promised_delivery_at = expected.promised_delivery_at
       and actual.delivery_duration_hours is not distinct from expected.delivery_duration_hours
       and actual.delay_hours is not distinct from expected.delay_hours
       and actual.is_on_time is not distinct from expected.is_on_time
       and actual.visit_count = expected.visit_count
       and actual.completed_visit_count = expected.completed_visit_count
       and actual.open_visit_count = expected.open_visit_count
       and abs(actual.completed_dwell_hours - expected.completed_dwell_hours) <= 0.000001
    where actual.package_id is null or expected.package_id is null
),

distance_violations as (
    select
        'package_distance' as violation,
        package_id as entity_id
    from {{ ref('gold_package_delivery_fact') }}
    where actual_distance_meters is null
       or actual_distance_meters < 0
       or (
            delivered_at is not null
            and (
                final_route_deviation_meters is null
                or final_route_deviation_pct is null
            )
       )
       or (
            package_id = 'P1'
            and (
                abs(actual_distance_meters - planned_distance_meters) > 1.0
                or abs(final_route_deviation_meters) > 1.0
                or abs(final_route_deviation_pct) > 0.01
            )
       )
       or (
            package_id in ('P2', 'P3')
            and (
                abs(actual_distance_meters / planned_distance_meters - 1.5) > 0.0001
                or abs(
                    final_route_deviation_meters
                    - (actual_distance_meters - planned_distance_meters)
                ) > 1.0
                or abs(final_route_deviation_meters / planned_distance_meters - 0.5) > 0.0001
                or abs(final_route_deviation_pct - 50.0) > 0.01
            )
       )
       or (
            package_id = 'P4'
            and (
                actual_distance_meters <= 0
                or final_route_deviation_meters is not null
                or final_route_deviation_pct is not null
            )
       )
),

reconciliation_violations as (
    select
        'package_counts' as violation,
        concat(
            cast(count(*) as varchar), ':',
            cast(count_if(delivered_at is not null) as varchar), ':',
            cast(count_if(delivered_at is null) as varchar)
        ) as entity_id
    from {{ ref('gold_package_delivery_fact') }}
    having count(*) <> 4
        or count_if(delivered_at is not null) <> 3
        or count_if(delivered_at is null) <> 1

    union all

    select
        'shipment_s2_package_count' as violation,
        cast(count(*) as varchar) as entity_id
    from {{ ref('gold_package_delivery_fact') }}
    where shipment_id = 'S2'
    having count(*) <> 2
)

select * from row_violations
union all
select * from distance_violations
union all
select * from reconciliation_violations
