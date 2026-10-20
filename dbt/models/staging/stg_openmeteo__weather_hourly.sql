{#-
  Hourly weather, all versions. Open-Meteo returns times in UTC (requested with
  timezone=GMT). Instantaneous variables refer to the timestamp; precipitation is the
  sum over the preceding hour, which matches GIOŚ hour-ending timestamps.
-#}
with source as (

    select * from {{ source('raw', 'openmeteo_weather_hourly') }}

)

select
    {{ json_get('request_params', 'location_id') }}                          as location_id,
    {{ try_to_timestamp(json_get('record_json', 'time')) }}                  as observed_at_utc,
    {{ try_to_double(json_get('record_json', 'temperature_2m')) }}           as temperature_c,
    {{ try_to_double(json_get('record_json', 'relative_humidity_2m')) }}     as relative_humidity_pct,
    {{ try_to_double(json_get('record_json', 'precipitation')) }}            as precipitation_mm,
    {{ try_to_double(json_get('record_json', 'wind_speed_10m')) }}           as wind_speed_ms,
    {{ try_to_double(json_get('record_json', 'wind_direction_10m')) }}       as wind_direction_deg,
    {{ try_to_double(json_get('record_json', 'surface_pressure')) }}         as surface_pressure_hpa,
    {{ try_to_double(json_get('record_json', 'cloud_cover')) }}              as cloud_cover_pct,
    source_system,
    case source_system when 'openmeteo_archive' then 1 else 2 end            as source_priority,
    ingested_at
from source
