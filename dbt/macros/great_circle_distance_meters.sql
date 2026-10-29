{% macro great_circle_distance_meters(from_longitude, from_latitude, to_longitude, to_latitude) -%}
st_distance(
    to_spherical_geography(st_point({{ from_longitude }}, {{ from_latitude }})),
    to_spherical_geography(st_point({{ to_longitude }}, {{ to_latitude }}))
)
{%- endmacro %}
