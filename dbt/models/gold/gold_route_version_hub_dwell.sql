select
    facts.route_id,
    facts.route_version_id,
    visits.hub_code,
    count(*) as completed_visit_count,
    sum(visits.dwell_time_hours) as completed_dwell_hours,
    avg(visits.dwell_time_hours) as average_completed_dwell_hours
from {{ ref('gold_hub_visits') }} as visits
inner join {{ ref('gold_package_delivery_fact') }} as facts
    on visits.package_id = facts.package_id
where not visits.is_open
group by
    facts.route_id,
    facts.route_version_id,
    visits.hub_code
