{#-
  Fact: one valid hourly measurement per sensor and hour, with weather context.
  Grain: sensor_code × measured_at_utc. Rejected readings are in dq.dq_rejected_measurements.
-#}
select
    {{ dbt_utils.generate_surrogate_key(['sensor_code', 'measured_at_utc']) }} as measurement_key,
    station_code,
    pollutant_code,
    sensor_code,
    measurement_date                                   as date_day,
    measured_at_utc,
    measured_at_local,
    cast(extract(hour from measured_at_local) as integer) as hour_local,
    value_ugm3,
    source_system,
    version_count,
    temperature_c,
    relative_humidity_pct,
    precipitation_mm,
    wind_speed_ms,
    wind_direction_deg,
    surface_pressure_hpa,
    cloud_cover_pct,
    weather_source
from {{ ref('int_measurements__with_weather') }}
