with actual as (
    select id, status
    from {{ ref('probe002_smoke') }}
),

unexpected_rows as (
    select id, status
    from actual
    where id <> 1
       or status <> 'dbt-adapter-ok'
),

unexpected_count as (
    select
        cast(null as integer) as id,
        cast('unexpected-row-count' as varchar) as status
    from actual
    having count(*) <> 1
)

select * from unexpected_rows
union all
select * from unexpected_count
