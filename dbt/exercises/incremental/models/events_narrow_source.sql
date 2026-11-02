{{ config(materialized='incremental', incremental_strategy='merge', unique_key='event_id',
    incremental_predicates=["DBT_INTERNAL_DEST.received_at >= TIMESTAMP '" ~ var('incremental_cutoff') ~ "'"]) }}
{{ exercise_events(narrow_source=true) }}
