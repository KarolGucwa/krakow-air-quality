{#-
  Generic test: consecutive hourly readings of one series must not differ by more than
  `max_change` (µg/m³). Complements no_isolated_spikes by catching step changes
  (e.g. unit or calibration errors) that persist for several hours. Typically used
  with severity: warn because real smog onsets can be steep.
-#}
{% test max_hourly_change(model, column_name, partition_by, order_by, max_change) %}

with series as (

    select
        {{ partition_by }} as series_id,
        {{ order_by }}     as ts,
        {{ column_name }}  as value,
        lag({{ column_name }}) over (partition by {{ partition_by }} order by {{ order_by }}) as prev_value,
        {{ dbt.datediff('lag(' ~ order_by ~ ') over (partition by ' ~ partition_by ~ ' order by ' ~ order_by ~ ')',
                        order_by, 'hour') }} as gap_hours
    from {{ model }}

)

select *
from series
where gap_hours = 1
  and abs(value - prev_value) > {{ max_change }}

{% endtest %}
