{#-
  One row per station that has metadata or measurements. Stations closed before the
  metadata snapshot (seen only in archive files) are kept, with missing attributes.
-#}
with observed as (

    select
        station_code,
        min(measured_at_utc)                                            as first_measurement_at_utc,
        max(measured_at_utc)                                            as last_measurement_at_utc,
        max(case when pollutant_code = 'PM10' then 1 else 0 end) = 1    as measures_pm10,
        max(case when pollutant_code = 'PM2.5' then 1 else 0 end) = 1   as measures_pm25
    from {{ ref('int_gios__measurements_validated') }}
    where is_valid
    group by station_code

),

metadata as (

    select * from {{ ref('stg_gios__station_metadata') }}

),

districts as (

    select * from {{ ref('station_districts') }}

),

stations as (

    select
        coalesce(o.station_code, m.station_code)                        as station_code,
        m.international_code,
        coalesce(m.station_name, coalesce(o.station_code, m.station_code)) as station_name,
        m.station_type,
        m.area_type,
        m.address,
        m.latitude,
        m.longitude,
        o.first_measurement_at_utc,
        o.last_measurement_at_utc,
        coalesce(o.measures_pm10, false)                                as measures_pm10,
        coalesce(o.measures_pm25, false)                                as measures_pm25
    from observed as o
    full outer join metadata as m
        on o.station_code = m.station_code

)

select
    s.station_code,
    s.international_code,
    s.station_name,
    -- short label for charts: "Kraków, Aleja Krasińskiego" -> "Aleja Krasińskiego"
    trim(replace(s.station_name, 'Kraków,', ''))                        as station_label,
    s.station_type,
    s.area_type,
    s.address,
    d.district_no,
    d.district_name,
    s.latitude,
    s.longitude,
    s.first_measurement_at_utc,
    s.last_measurement_at_utc,
    s.measures_pm10,
    s.measures_pm25,
    coalesce(
        s.last_measurement_at_utc >= {{ dbt.dateadd('day', -7, dbt.current_timestamp()) }},
        false
    )                                                                   as is_active
from stations as s
left join districts as d
    on s.station_code = d.station_code
