{#-
  Daily weather on the same day convention as the air-quality daily means: hours ending
  01:00 ... 24:00 CET belong to one day (EU convention for daily means).
-#}
with hourly as (

    select
        *,
        cast({{ dbt.dateadd('hour', var('gios_archive_utc_offset_hours') - 1, 'observed_at_utc') }} as date)
            as measurement_date
    from {{ ref('int_weather__hourly') }}
    where location_id = '{{ var("weather_location_id") }}'

)

select
    measurement_date,
    count(*)                                         as weather_hours,
    avg(temperature_c)                               as temp_mean_c,
    min(temperature_c)                               as temp_min_c,
    max(temperature_c)                               as temp_max_c,
    avg(wind_speed_ms)                               as wind_mean_ms,
    sum(precipitation_mm)                            as precipitation_sum_mm,
    avg(relative_humidity_pct)                       as humidity_mean_pct,
    avg(surface_pressure_hpa)                        as pressure_mean_hpa,
    -- heating degree days, Eurostat method (base 18 °C, heating threshold 15 °C)
    case when avg(temperature_c) <= 15 then 18 - avg(temperature_c) else 0 end as heating_degree_days
from hourly
group by measurement_date
