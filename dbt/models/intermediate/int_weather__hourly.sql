-- One weather row per (location, hour): reanalysis preferred over forecast-model values.
with ranked as (

    select
        *,
        row_number() over (
            partition by location_id, observed_at_utc
            order by source_priority, ingested_at desc
        ) as version_rank
    from {{ ref('stg_openmeteo__weather_hourly') }}
    where observed_at_utc is not null
      and observed_at_utc <= {{ dbt.current_timestamp() }}

)

select
    location_id,
    observed_at_utc,
    temperature_c,
    relative_humidity_pct,
    precipitation_mm,
    wind_speed_ms,
    wind_direction_deg,
    surface_pressure_hpa,
    cloud_cover_pct,
    source_system as weather_source
from ranked
where version_rank = 1
