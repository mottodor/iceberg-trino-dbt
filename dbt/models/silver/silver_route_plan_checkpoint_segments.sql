with typed_checkpoints as (
    select
        checkpoints.fixture_row_id as checkpoint_fixture_row_id,
        checkpoints.route_version_id,
        cast(checkpoints.checkpoint_seq as integer) as checkpoint_seq,
        checkpoints.hub_code,
        cast(hubs.longitude as double) as longitude,
        cast(hubs.latitude as double) as latitude
    from {{ ref('bronze_route_checkpoints') }} as checkpoints
    inner join {{ ref('bronze_hubs') }} as hubs
        on checkpoints.hub_code = hubs.hub_code
),

ordered_checkpoints as (
    select
        *,
        lag(longitude) over (
            partition by route_version_id
            order by checkpoint_seq
        ) as previous_longitude,
        lag(latitude) over (
            partition by route_version_id
            order by checkpoint_seq
        ) as previous_latitude
    from typed_checkpoints
)

select
    checkpoint_fixture_row_id,
    route_version_id,
    checkpoint_seq,
    hub_code,
    longitude,
    latitude,
    case
        when previous_longitude is null or previous_latitude is null then null
        else {{ great_circle_distance_meters(
            'previous_longitude',
            'previous_latitude',
            'longitude',
            'latitude'
        ) }}
    end as distance_from_previous_meters
from ordered_checkpoints
