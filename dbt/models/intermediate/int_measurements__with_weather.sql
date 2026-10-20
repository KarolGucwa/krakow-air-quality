{#-
  Valid hourly measurements joined with hourly weather. GIOŚ timestamps mark the end of
  the averaging hour; Open-Meteo instantaneous values at that timestamp and the
  precipitation of the preceding hour describe the same interval.
-#}
with measurements as (

    select * from {{ ref('int_gios__measurements_validated') }}
    where is_valid

),

weather as (

    select * from {{ ref('int_weather__hourly') }}
    where location_id = '{{ var("weather_location_id") }}'

)

select
    m.sensor_code,
    m.station_code,
    m.pollutant_code,
    m.measured_at_utc,
    {{ utc_to_local('m.measured_at_utc', var('local_timezone')) }}                      as measured_at_local,
    cast({{ dbt.dateadd('hour', var('gios_archive_utc_offset_hours') - 1, 'm.measured_at_utc') }} as date)
                                                                                        as measurement_date,
    m.value_ugm3,
    m.source_system,
    m.version_count,
    w.temperature_c,
    w.relative_humidity_pct,
    w.precipitation_mm,
    w.wind_speed_ms,
    w.wind_direction_deg,
    w.surface_pressure_hpa,
    w.cloud_cover_pct,
    w.weather_source
from measurements as m
left join weather as w
    on m.measured_at_utc = w.observed_at_utc
