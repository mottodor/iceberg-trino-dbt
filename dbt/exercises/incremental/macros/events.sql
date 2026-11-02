{% macro exercise_events(narrow_source=false) %}
with ranked as (
    select event_id, event_at, received_at, amount_units,
        row_number() over (
            partition by event_id order by received_at desc, batch_number desc
        ) as canonical_rank
    from {{ source('exercise', 'events_input') }}
)
select event_id, event_at, received_at, amount_units
from ranked
where canonical_rank = 1
{% if is_incremental() %}
    {% if narrow_source %}
        and event_at >= TIMESTAMP '{{ var("narrow_cutoff") }}'
    {% else %}
        and received_at >= TIMESTAMP '{{ var("incremental_cutoff") }}'
    {% endif %}
{% endif %}
{% endmacro %}
