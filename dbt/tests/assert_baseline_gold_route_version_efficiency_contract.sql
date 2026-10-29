{{ config(tags=['gold', 'fixture_contract', 'expected_aggregates', 'reconciliation']) }}

with expected_route_versions (
    route_id,
    route_version_id,
    package_count,
    completed_package_count,
    active_package_count,
    on_time_completed_package_count,
    on_time_rate_pct,
    average_delay_hours,
    average_final_route_deviation_pct
) as (
    values
        ('R1', 'R1-V1', bigint '1', bigint '1', bigint '0', bigint '1', 100.0, 0.0, 0.0),
        ('R1', 'R1-V2', bigint '3', bigint '2', bigint '1', bigint '1', 50.0, 6.0, 50.0)
)

select
    'route_version_efficiency' as violation,
    coalesce(actual.route_version_id, expected.route_version_id) as entity_id
from {{ ref('gold_route_version_efficiency') }} as actual
full outer join expected_route_versions as expected
    on actual.route_id = expected.route_id
   and actual.route_version_id = expected.route_version_id
   and actual.package_count = expected.package_count
   and actual.completed_package_count = expected.completed_package_count
   and actual.active_package_count = expected.active_package_count
   and actual.on_time_completed_package_count = expected.on_time_completed_package_count
   and abs(actual.on_time_rate_pct - expected.on_time_rate_pct) <= 0.01
   and abs(actual.average_delay_hours - expected.average_delay_hours) <= 0.000001
   and abs(
        actual.average_final_route_deviation_pct
        - expected.average_final_route_deviation_pct
   ) <= 0.01
where actual.route_version_id is null or expected.route_version_id is null
