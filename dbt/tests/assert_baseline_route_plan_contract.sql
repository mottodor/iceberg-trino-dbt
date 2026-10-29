{{ config(tags=['silver', 'fixture_contract', 'route_plan']) }}

with expected_versions (
    route_version_id,
    route_id,
    valid_from,
    valid_to,
    is_current,
    planned_duration_hours,
    sla_duration_hours,
    checkpoint_count,
    segment_count
) as (
    values
        (
            'R1-V1',
            'R1',
            from_iso8601_timestamp('2025-01-01T00:00:00Z'),
            from_iso8601_timestamp('2025-02-01T00:00:00Z'),
            false,
            bigint '48',
            bigint '48',
            bigint '3',
            bigint '2'
        ),
        (
            'R1-V2',
            'R1',
            from_iso8601_timestamp('2025-02-01T00:00:00Z'),
            cast(null as timestamp(3) with time zone),
            true,
            bigint '36',
            bigint '36',
            bigint '3',
            bigint '2'
        )
),

version_violations as (
    select
        'route_version' as violation,
        coalesce(actual.route_version_id, expected.route_version_id) as entity_id
    from {{ ref('silver_route_plan_versions') }} as actual
    full outer join expected_versions as expected
        on actual.route_version_id = expected.route_version_id
       and actual.route_id = expected.route_id
       and actual.valid_from = expected.valid_from
       and actual.valid_to is not distinct from expected.valid_to
       and actual.is_current = expected.is_current
       and actual.planned_duration_hours = expected.planned_duration_hours
       and actual.sla_duration_hours = expected.sla_duration_hours
       and actual.checkpoint_count = expected.checkpoint_count
       and actual.segment_count = expected.segment_count
    where actual.route_version_id is null or expected.route_version_id is null
),

expected_bindings (
    package_id,
    route_version_id,
    picked_up_at,
    promised_delivery_at
) as (
    values
        (
            'P1',
            'R1-V1',
            from_iso8601_timestamp('2025-01-10T08:00:00Z'),
            from_iso8601_timestamp('2025-01-12T08:00:00Z')
        ),
        (
            'P2',
            'R1-V2',
            from_iso8601_timestamp('2025-02-10T08:00:00Z'),
            from_iso8601_timestamp('2025-02-11T20:00:00Z')
        ),
        (
            'P3',
            'R1-V2',
            from_iso8601_timestamp('2025-02-10T09:00:00Z'),
            from_iso8601_timestamp('2025-02-11T21:00:00Z')
        ),
        (
            'P4',
            'R1-V2',
            from_iso8601_timestamp('2025-02-12T08:00:00Z'),
            from_iso8601_timestamp('2025-02-13T20:00:00Z')
        )
),

binding_violations as (
    select
        'package_route_binding' as violation,
        coalesce(actual.package_id, expected.package_id) as entity_id
    from {{ ref('silver_package_route_binding') }} as actual
    full outer join expected_bindings as expected
        on actual.package_id = expected.package_id
       and actual.route_version_id = expected.route_version_id
       and actual.picked_up_at = expected.picked_up_at
       and actual.promised_delivery_at = expected.promised_delivery_at
    where actual.package_id is null or expected.package_id is null
),

distance_violations as (
    select
        'planned_distance' as violation,
        'R1-V1:R1-V2' as entity_id
    from (
        select
            max(case when route_version_id = 'R1-V1' then planned_distance_meters end) as v1_distance,
            max(case when route_version_id = 'R1-V2' then planned_distance_meters end) as v2_distance
        from {{ ref('silver_route_plan_versions') }}
    ) as distances
    where v1_distance is null
       or v2_distance is null
       or v1_distance <= 0
       or v2_distance <= 0
       or abs(v1_distance - v2_distance) > 1.0
)

select * from version_violations
union all
select * from binding_violations
union all
select * from distance_violations
