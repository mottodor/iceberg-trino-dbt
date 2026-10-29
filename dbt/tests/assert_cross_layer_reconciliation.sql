{{ config(tags=['gold', 'fixture_contract', 'reconciliation']) }}

with expected_counts (layer_name, expected_count) as (
    values
        ('bronze_tracking_events', bigint '28'),
        ('silver_tracking_events_typed', bigint '28'),
        ('silver_tracking_events', bigint '27'),
        ('silver_package_route_binding', bigint '4'),
        ('gold_package_delivery_fact', bigint '4'),
        ('gold_hub_visits', bigint '7'),
        ('gold_route_version_efficiency', bigint '2'),
        ('gold_route_version_hub_dwell', bigint '4')
),

actual_counts (layer_name, actual_count) as (
    select 'bronze_tracking_events', count(*) from {{ ref('bronze_tracking_events') }}
    union all
    select 'silver_tracking_events_typed', count(*) from {{ ref('silver_tracking_events_typed') }}
    union all
    select 'silver_tracking_events', count(*) from {{ ref('silver_tracking_events') }}
    union all
    select 'silver_package_route_binding', count(*) from {{ ref('silver_package_route_binding') }}
    union all
    select 'gold_package_delivery_fact', count(*) from {{ ref('gold_package_delivery_fact') }}
    union all
    select 'gold_hub_visits', count(*) from {{ ref('gold_hub_visits') }}
    union all
    select 'gold_route_version_efficiency', count(*) from {{ ref('gold_route_version_efficiency') }}
    union all
    select 'gold_route_version_hub_dwell', count(*) from {{ ref('gold_route_version_hub_dwell') }}
),

count_violations as (
    select
        'layer_count' as violation,
        expected.layer_name as entity_id,
        cast(actual.actual_count as varchar) as actual_value,
        cast(expected.expected_count as varchar) as expected_value
    from expected_counts as expected
    inner join actual_counts as actual
        on expected.layer_name = actual.layer_name
    where actual.actual_count <> expected.expected_count
),

duplicate_reconciliation as (
    select
        (select count(*) from {{ ref('bronze_tracking_events') }}) as bronze_count,
        (select count(*) from {{ ref('silver_tracking_events') }}) as canonical_count,
        (
            select coalesce(sum(raw_event_row_count - 1), bigint '0')
            from {{ ref('silver_tracking_events') }}
        ) as explained_duplicate_count
),

duplicate_violations as (
    select
        'bronze_to_canonical_duplicate_count' as violation,
        'tracking_events' as entity_id,
        concat(
            cast(bronze_count - canonical_count as varchar),
            ':',
            cast(explained_duplicate_count as varchar)
        ) as actual_value,
        '1:1' as expected_value
    from duplicate_reconciliation
    where bronze_count - canonical_count <> 1
       or explained_duplicate_count <> 1
       or bronze_count - canonical_count <> explained_duplicate_count
),

package_relationship_violations as (
    select
        'package_fact_binding_relationship' as violation,
        coalesce(facts.package_id, bindings.package_id) as entity_id,
        coalesce(facts.route_version_id, '<missing>') as actual_value,
        coalesce(bindings.route_version_id, '<missing>') as expected_value
    from {{ ref('gold_package_delivery_fact') }} as facts
    full outer join {{ ref('silver_package_route_binding') }} as bindings
        on facts.package_id = bindings.package_id
       and facts.shipment_id = bindings.shipment_id
       and facts.route_version_id = bindings.route_version_id
    where facts.package_id is null or bindings.package_id is null
),

visit_relationship_violations as (
    select
        'hub_visit_package_relationship' as violation,
        visits.arrival_event_id as entity_id,
        coalesce(facts.package_id, '<missing>') as actual_value,
        visits.package_id as expected_value
    from {{ ref('gold_hub_visits') }} as visits
    left join {{ ref('gold_package_delivery_fact') }} as facts
        on visits.package_id = facts.package_id
    where facts.package_id is null
),

route_rollup_violations as (
    select
        'route_version_rollup' as violation,
        aggregates.route_version_id as entity_id,
        concat(
            cast(aggregates.package_count as varchar),
            ':',
            cast(aggregates.completed_package_count as varchar),
            ':',
            cast(aggregates.active_package_count as varchar)
        ) as actual_value,
        concat(
            cast(count(facts.package_id) as varchar),
            ':',
            cast(count_if(facts.delivered_at is not null) as varchar),
            ':',
            cast(count_if(facts.package_id is not null and facts.delivered_at is null) as varchar)
        ) as expected_value
    from {{ ref('gold_route_version_efficiency') }} as aggregates
    left join {{ ref('gold_package_delivery_fact') }} as facts
        on aggregates.route_version_id = facts.route_version_id
    group by
        aggregates.route_version_id,
        aggregates.package_count,
        aggregates.completed_package_count,
        aggregates.active_package_count
    having aggregates.package_count <> count(facts.package_id)
        or aggregates.completed_package_count <> count_if(facts.delivered_at is not null)
        or aggregates.active_package_count
            <> count_if(facts.package_id is not null and facts.delivered_at is null)
),

shipment_s2_violations as (
    select
        'shipment_s2_independent_packages' as violation,
        'S2' as entity_id,
        concat(cast(count(*) as varchar), ':', cast(count(distinct package_id) as varchar)) as actual_value,
        '2:2' as expected_value
    from {{ ref('gold_package_delivery_fact') }}
    where shipment_id = 'S2'
    having count(*) <> 2
        or count(distinct package_id) <> 2
        or min(package_id) <> 'P2'
        or max(package_id) <> 'P3'
)

select * from count_violations
union all
select * from duplicate_violations
union all
select * from package_relationship_violations
union all
select * from visit_relationship_violations
union all
select * from route_rollup_violations
union all
select * from shipment_s2_violations
