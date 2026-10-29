{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set run_prefix = target.schema | trim -%}

    {%- if not run_prefix -%}
        {{ exceptions.raise_compiler_error(
            "DBT_TRINO_SCHEMA must provide a non-empty run prefix"
        ) }}
    {%- elif custom_schema_name is none -%}
        {{ run_prefix }}
    {%- else -%}
        {{ run_prefix }}_{{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
