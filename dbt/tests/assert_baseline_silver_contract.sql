{{ config(tags=['silver', 'fixture_contract']) }}

with expected_package_states (
    package_id,
    current_event_id,
    current_status,
    current_event_at
) as (
    values
        ('P1', 'P1-E06', 'delivered', from_iso8601_timestamp('2025-01-12T08:00:00Z')),
        ('P2', 'P2-E10', 'delivered', from_iso8601_timestamp('2025-02-12T08:00:00Z')),
        ('P3', 'P3-E04', 'delivered', from_iso8601_timestamp('2025-02-11T21:00:00Z')),
        ('P4', 'P4-E03', 'arrived_at_hub', from_iso8601_timestamp('2025-02-12T20:00:00Z'))
),

package_state_violations as (
    select
        'package_state' as violation,
        coalesce(actual.package_id, expected.package_id) as entity_id
    from {{ ref('silver_package_current_state') }} as actual
    full outer join expected_package_states as expected
        on actual.package_id = expected.package_id
       and actual.current_event_id = expected.current_event_id
       and actual.current_status = expected.current_status
       and actual.current_event_at = expected.current_event_at
    where actual.package_id is null or expected.package_id is null
),

expected_p3_order (package_event_seq, event_id) as (
    values
        (1, 'P3-E01'),
        (2, 'P3-E02'),
        (3, 'P3-E05'),
        (4, 'P3-E06'),
        (5, 'P3-E07'),
        (6, 'P3-E08'),
        (7, 'P3-E03'),
        (8, 'P3-E04')
),

p3_order_violations as (
    select
        'p3_business_order' as violation,
        coalesce(actual.event_id, expected.event_id) as entity_id
    from (
        select package_event_seq, event_id
        from {{ ref('silver_tracking_events') }}
        where package_id = 'P3'
    ) as actual
    full outer join expected_p3_order as expected
        on actual.package_event_seq = expected.package_event_seq
       and actual.event_id = expected.event_id
    where actual.event_id is null or expected.event_id is null
),

count_violations as (
    select
        'typed_event_count' as violation,
        cast(count(*) as varchar) as entity_id
    from {{ ref('silver_tracking_events_typed') }}
    having count(*) <> 28

    union all

    select
        'canonical_event_count' as violation,
        cast(count(*) as varchar) as entity_id
    from {{ ref('silver_tracking_events') }}
    having count(*) <> 27

    union all

    select
        'p3_e02_canonical_count' as violation,
        cast(count(*) as varchar) as entity_id
    from {{ ref('silver_tracking_events') }}
    where event_id = 'P3-E02'
    having count(*) <> 1

    union all

    select
        'p3_e02_raw_count' as violation,
        cast(coalesce(max(raw_event_row_count), 0) as varchar) as entity_id
    from {{ ref('silver_tracking_events') }}
    where event_id = 'P3-E02'
    having coalesce(max(raw_event_row_count), 0) <> 2
)

select * from package_state_violations
union all
select * from p3_order_violations
union all
select * from count_violations
