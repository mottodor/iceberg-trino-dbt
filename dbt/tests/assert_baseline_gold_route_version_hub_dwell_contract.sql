{{ config(tags=['gold', 'fixture_contract', 'expected_aggregates', 'reconciliation']) }}

with expected_hub_dwell (
    route_id,
    route_version_id,
    hub_code,
    completed_visit_count,
    completed_dwell_hours,
    average_completed_dwell_hours
) as (
    values
        ('R1', 'R1-V1', 'B', bigint '1', 4.0, 4.0),
        ('R1', 'R1-V2', 'B', bigint '2', 6.0, 3.0),
        ('R1', 'R1-V2', 'X', bigint '2', 11.0, 5.5),
        ('R1', 'R1-V2', 'D', bigint '1', 2.0, 2.0)
)

select
    'route_version_hub_dwell' as violation,
    concat(
        coalesce(actual.route_version_id, expected.route_version_id),
        ':',
        coalesce(actual.hub_code, expected.hub_code)
    ) as entity_id
from {{ ref('gold_route_version_hub_dwell') }} as actual
full outer join expected_hub_dwell as expected
    on actual.route_id = expected.route_id
   and actual.route_version_id = expected.route_version_id
   and actual.hub_code = expected.hub_code
   and actual.completed_visit_count = expected.completed_visit_count
   and abs(actual.completed_dwell_hours - expected.completed_dwell_hours) <= 0.000001
   and abs(
        actual.average_completed_dwell_hours
        - expected.average_completed_dwell_hours
   ) <= 0.000001
where actual.route_version_id is null or expected.route_version_id is null
