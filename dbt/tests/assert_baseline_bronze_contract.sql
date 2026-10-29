{{ config(tags=['bronze', 'fixture_contract']) }}

with expected_counts (table_name, expected_count) as (
    values
        ('hubs', 5),
        ('packages', 4),
        ('route_plan_changes', 2),
        ('route_checkpoints', 6),
        ('tracking_events', 28)
),

actual_counts (table_name, actual_count) as (
    select 'hubs', count(*) from {{ ref('bronze_hubs') }}
    union all
    select 'packages', count(*) from {{ ref('bronze_packages') }}
    union all
    select 'route_plan_changes', count(*) from {{ ref('bronze_route_plan_changes') }}
    union all
    select 'route_checkpoints', count(*) from {{ ref('bronze_route_checkpoints') }}
    union all
    select 'tracking_events', count(*) from {{ ref('bronze_tracking_events') }}
),

count_violations as (
    select
        'row_count:' || expected.table_name as violation,
        cast(actual.actual_count as varchar) as actual_value,
        cast(expected.expected_count as varchar) as expected_value
    from expected_counts as expected
    join actual_counts as actual
        on expected.table_name = actual.table_name
    where actual.actual_count <> expected.expected_count
),

p3_duplicate_summary as (
    select
        count(*) as raw_row_count,
        count(distinct batch_id) as batch_count
    from {{ ref('bronze_tracking_events') }}
    where event_id = 'P3-E02'
),

p3_payload_variants as (
    select count(*) as payload_variant_count
    from (
        select distinct
            event_id,
            package_id,
            event_type,
            event_at,
            received_at,
            hub_code,
            longitude,
            latitude
        from {{ ref('bronze_tracking_events') }}
        where event_id = 'P3-E02'
    )
),

p3_late_events as (
    select event_id
    from {{ ref('bronze_tracking_events') }}
    where batch_id = 'batch_2'
),

expected_p3_late_events (event_id) as (
    values ('P3-E02'), ('P3-E05'), ('P3-E06'), ('P3-E07'), ('P3-E08')
),

p3_late_event_set_violations as (
    select
        'p3_batch_2_event_set' as violation,
        coalesce(actual.event_id, '<missing>') as actual_value,
        coalesce(expected.event_id, '<unexpected>') as expected_value
    from p3_late_events as actual
    full outer join expected_p3_late_events as expected
        on actual.event_id = expected.event_id
    where actual.event_id is null or expected.event_id is null
),

contract_violations as (
    select * from count_violations

    union all

    select
        'p3_duplicate_raw_rows',
        cast(raw_row_count as varchar),
        '2'
    from p3_duplicate_summary
    where raw_row_count <> 2

    union all

    select
        'p3_duplicate_batches',
        cast(batch_count as varchar),
        '2'
    from p3_duplicate_summary
    where batch_count <> 2

    union all

    select
        'p3_duplicate_payload_variants',
        cast(payload_variant_count as varchar),
        '1'
    from p3_payload_variants
    where payload_variant_count <> 1

    union all

    select
        'shipment_s2_package_count',
        cast(count(*) as varchar),
        '2'
    from {{ ref('bronze_packages') }}
    where shipment_id = 'S2'
    having count(*) <> 2

    union all

    select * from p3_late_event_set_violations
)

select violation, actual_value, expected_value
from contract_violations
