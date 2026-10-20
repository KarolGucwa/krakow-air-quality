{#-
  Generic test: fail for every reading that is an isolated one-hour spike, i.e. far above
  both neighbouring hours of the same series (definition in macros/domain.sql).

  Usage (schema.yml):
    columns:
      - name: value_ugm3
        data_tests:
          - no_isolated_spikes:
              arguments:
                partition_by: sensor_code
                order_by: measured_at_utc
-#}
{% test no_isolated_spikes(model, column_name, partition_by, order_by) %}

with series as (

    select
        {{ partition_by }} as series_id,
        {{ order_by }}     as ts,
        {{ column_name }}  as value,
        lag({{ column_name }}) over w  as prev_value,
        lead({{ column_name }}) over w as next_value,
        {{ dbt.datediff('lag(' ~ order_by ~ ') over w', order_by, 'hour') }}  as prev_gap_hours,
        {{ dbt.datediff(order_by, 'lead(' ~ order_by ~ ') over w', 'hour') }} as next_gap_hours
    from {{ model }}
    where {{ column_name }} is not null
    window w as (partition by {{ partition_by }} order by {{ order_by }})

)

select *
from series
where {{ is_isolated_spike('value', 'prev_value', 'next_value', 'prev_gap_hours', 'next_gap_hours') }}

{% endtest %}
