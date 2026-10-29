{{ config(tags=['silver', 'route_plan']) }}

with invalid_intervals as (
    select
        'invalid_interval' as violation,
        route_version_id as entity_id
    from {{ ref('silver_route_plan_versions') }}
    where valid_to is not null
      and valid_to <= valid_from
),

invalid_current_counts as (
    select
        'current_version_count' as violation,
        route_id as entity_id
    from {{ ref('silver_route_plan_versions') }}
    group by route_id
    having sum(case when is_current then 1 else 0 end) <> 1
),

overlapping_intervals as (
    select
        'overlapping_interval' as violation,
        first_version.route_version_id || ':' || second_version.route_version_id as entity_id
    from {{ ref('silver_route_plan_versions') }} as first_version
    inner join {{ ref('silver_route_plan_versions') }} as second_version
        on first_version.route_id = second_version.route_id
       and first_version.route_version_id < second_version.route_version_id
       and (
            second_version.valid_to is null
            or first_version.valid_from < second_version.valid_to
       )
       and (
            first_version.valid_to is null
            or second_version.valid_from < first_version.valid_to
       )
)

select * from invalid_intervals
union all
select * from invalid_current_counts
union all
select * from overlapping_intervals
