{{ config(materialized='incremental', incremental_strategy='merge', unique_key='event_id',
    incremental_predicates=["DBT_INTERNAL_DEST.event_at >= TIMESTAMP '" ~ var('narrow_cutoff') ~ "'"]) }}
{{ exercise_events() }}
