with package_facts as (
    select *
    from {{ ref('gold_package_delivery_fact') }}
)

select
    versions.route_id,
    versions.route_version_id,
    count(facts.package_id) as package_count,
    count_if(facts.package_id is not null and facts.delivered_at is not null) as completed_package_count,
    count_if(facts.package_id is not null and facts.delivered_at is null) as active_package_count,
    count_if(facts.delivered_at is not null and facts.is_on_time) as on_time_completed_package_count,
    case
        when count_if(facts.delivered_at is not null) = 0 then null
        else
            cast(count_if(facts.delivered_at is not null and facts.is_on_time) as double)
            / cast(count_if(facts.delivered_at is not null) as double)
            * 100.0
    end as on_time_rate_pct,
    avg(facts.delay_hours) filter (where facts.delivered_at is not null) as average_delay_hours,
    avg(facts.final_route_deviation_pct)
        filter (where facts.delivered_at is not null) as average_final_route_deviation_pct
from {{ ref('silver_route_plan_versions') }} as versions
left join package_facts as facts
    on versions.route_version_id = facts.route_version_id
group by
    versions.route_id,
    versions.route_version_id
