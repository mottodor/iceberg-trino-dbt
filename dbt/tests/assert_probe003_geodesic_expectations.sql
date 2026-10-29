with route_points (route_name, point_order, longitude, latitude) as (
    values
        ('planned_v1', 1, 0.0, 0.0),
        ('planned_v1', 2, 1.0, 0.0),
        ('planned_v1', 3, 2.0, 0.0),
        ('planned_v2', 1, 0.0, 0.0),
        ('planned_v2', 2, 1.5, 0.0),
        ('planned_v2', 3, 2.0, 0.0),
        ('actual_p2', 1, 0.0, 0.0),
        ('actual_p2', 2, 1.0, 0.0),
        ('actual_p2', 3, 0.5, 0.0),
        ('actual_p2', 4, 1.5, 0.0),
        ('actual_p2', 5, 2.0, 0.0)
),

segments as (
    select
        route_name,
        point_order,
        longitude,
        latitude,
        lead(longitude) over (
            partition by route_name
            order by point_order
        ) as next_longitude,
        lead(latitude) over (
            partition by route_name
            order by point_order
        ) as next_latitude
    from route_points
),

route_distances as (
    select
        route_name,
        sum(
            {{ great_circle_distance_meters(
                'longitude',
                'latitude',
                'next_longitude',
                'next_latitude'
            ) }}
        ) as distance_meters
    from segments
    where next_longitude is not null
    group by route_name
),

measurements as (
    select
        max(distance_meters) filter (
            where route_name = 'planned_v1'
        ) as planned_v1_meters,
        max(distance_meters) filter (
            where route_name = 'planned_v2'
        ) as planned_v2_meters,
        max(distance_meters) filter (
            where route_name = 'actual_p2'
        ) as actual_p2_meters,
        {{ great_circle_distance_meters('120.0', '10.0', '121.0', '10.0') }}
            as coordinate_order_sentinel_meters
    from route_distances
),

failures as (
    select
        'planned-distance-difference-metres' as assertion_name,
        abs(planned_v1_meters - planned_v2_meters) as observed_value,
        1.0 as tolerance_or_minimum,
        0.0 as expected_value
    from measurements
    where planned_v1_meters is null
       or planned_v2_meters is null
       or abs(planned_v1_meters - planned_v2_meters) > 1.0

    union all

    select
        'actual-to-planned-percentage' as assertion_name,
        actual_p2_meters / planned_v2_meters * 100.0 as observed_value,
        0.01 as tolerance_or_minimum,
        150.0 as expected_value
    from measurements
    where actual_p2_meters is null
       or planned_v2_meters is null
       or planned_v2_meters = 0.0
       or abs(actual_p2_meters / planned_v2_meters * 100.0 - 150.0) > 0.01

    union all

    select
        'longitude-latitude-order-and-metre-units' as assertion_name,
        coordinate_order_sentinel_meters as observed_value,
        100000.0 as tolerance_or_minimum,
        110000.0 as expected_value
    from measurements
    where coordinate_order_sentinel_meters is null
       or coordinate_order_sentinel_meters <= 100000.0
       or coordinate_order_sentinel_meters >= 120000.0
)

select * from failures
