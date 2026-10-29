with actual_schemas (layer_name, schema_name) as (
    values
        ('fixtures', '{{ source("fixtures", "hubs").schema }}'),
        ('bronze', '{{ generate_schema_name("bronze", model) | trim }}'),
        ('silver', '{{ generate_schema_name("silver", model) | trim }}'),
        ('gold', '{{ generate_schema_name("gold", model) | trim }}')
),

expected_schemas (layer_name, schema_name) as (
    values
        ('fixtures', '{{ target.schema }}_fixtures'),
        ('bronze', '{{ target.schema }}_bronze'),
        ('silver', '{{ target.schema }}_silver'),
        ('gold', '{{ target.schema }}_gold')
)

select
    coalesce(actual.layer_name, expected.layer_name) as layer_name,
    actual.schema_name as actual_schema_name,
    expected.schema_name as expected_schema_name
from actual_schemas as actual
full outer join expected_schemas as expected
    on actual.layer_name = expected.layer_name
where actual.schema_name is distinct from expected.schema_name
