{#-
  Data-quality report: one row per station, pollutant and month.
  expected_hours  hours of the month inside the sensor's observed lifetime
  valid_hours     hours that reached the fact table
  rejected_*      hours rejected by validation (one reason per hour)
  missing_hours   expected hours without any usable value (no record or null value)
  duplicates      extra versions discarded during deduplication (records, not hours)
-#}
with validated as (

    select * from {{ ref('int_gios__measurements_validated') }}

),

sensor_lifetime as (

    select
        station_code,
        pollutant_code,
        min(measured_at_utc) as first_hour,
        max(measured_at_utc) as last_hour
    from validated
    group by station_code, pollutant_code

),

months as (

    select distinct cast({{ dbt.date_trunc('month', 'date_day') }} as date) as month_start
    from {{ ref('dim_date') }}

),

expected as (

    select
        s.station_code,
        s.pollutant_code,
        m.month_start,
        {{ dbt.datediff(
            "case when s.first_hour > cast(m.month_start as timestamp) then s.first_hour
                  else cast(m.month_start as timestamp) end",
            "case when s.last_hour < " ~ dbt.dateadd('hour', -1, dbt.dateadd('month', 1, 'cast(m.month_start as timestamp)')) ~ "
                  then s.last_hour
                  else " ~ dbt.dateadd('hour', -1, dbt.dateadd('month', 1, 'cast(m.month_start as timestamp)')) ~ " end",
            'hour') }} + 1 as expected_hours
    from sensor_lifetime as s
    inner join months as m
        on m.month_start >= cast({{ dbt.date_trunc('month', 's.first_hour') }} as date)
       and m.month_start <= cast({{ dbt.date_trunc('month', 's.last_hour') }} as date)

),

observed as (

    select
        station_code,
        pollutant_code,
        cast({{ dbt.date_trunc('month', 'measured_at_utc') }} as date)                    as month_start,
        count(*)                                                                         as records_after_dedup,
        sum(case when is_valid then 1 else 0 end)                                         as valid_hours,
        sum(case when rejection_reason = 'missing_value' then 1 else 0 end)               as null_value_hours,
        sum(case when rejection_reason = 'negative_value' then 1 else 0 end)              as rejected_negative,
        sum(case when rejection_reason = 'out_of_range' then 1 else 0 end)                as rejected_out_of_range,
        sum(case when rejection_reason = 'isolated_spike' then 1 else 0 end)              as rejected_spike,
        sum(version_count - 1)                                                            as duplicates
    from validated
    group by 1, 2, 3

)

select
    e.station_code,
    e.pollutant_code,
    e.month_start,
    e.expected_hours,
    coalesce(o.valid_hours, 0)                                                       as valid_hours,
    coalesce(o.rejected_negative, 0)                                                 as rejected_negative,
    coalesce(o.rejected_out_of_range, 0)                                             as rejected_out_of_range,
    coalesce(o.rejected_spike, 0)                                                    as rejected_spike,
    coalesce(o.rejected_negative, 0) + coalesce(o.rejected_out_of_range, 0)
        + coalesce(o.rejected_spike, 0)                                              as rejected_hours,
    e.expected_hours - coalesce(o.valid_hours, 0) - coalesce(o.rejected_negative, 0)
        - coalesce(o.rejected_out_of_range, 0) - coalesce(o.rejected_spike, 0)       as missing_hours,
    coalesce(o.null_value_hours, 0)                                                  as null_value_hours,
    coalesce(o.duplicates, 0)                                                        as duplicates,
    round(100.0 * coalesce(o.valid_hours, 0) / nullif(e.expected_hours, 0), 1)      as completeness_pct
from expected as e
left join observed as o
    on e.station_code = o.station_code
   and e.pollutant_code = o.pollutant_code
   and e.month_start = o.month_start
