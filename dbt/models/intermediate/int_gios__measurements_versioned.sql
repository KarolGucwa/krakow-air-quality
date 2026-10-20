{#-
  All versions of every (sensor, hour), ranked. The same hour usually arrives several
  times: in up to three daily current-API snapshots, from the archival service and from
  the yearly packages; at the autumn DST change two local readings map to one UTC hour.
  Preference: verified sources first (archive file > archival API > current API), then
  the most recently downloaded version.
-#}
with measurements as (

    select * from {{ ref('stg_gios__measurements') }}

),

sensors as (

    select sensor_code, station_code from {{ ref('stg_gios__sensor_metadata') }}

),

scoped as (

    select
        m.raw_record_id,
        m.sensor_code,
        coalesce(s.station_code, m.station_code_in_record, m.station_code_from_sensor) as station_code,
        m.pollutant_code,
        m.averaging_period,
        m.measured_at_utc,
        m.value_ugm3,
        m.source_system,
        m.source_priority,
        m.batch_id,
        m.ingested_at
    from measurements as m
    left join sensors as s
        on m.sensor_code = s.sensor_code
    where m.averaging_period = '{{ var("averaging_period") }}'
      and m.pollutant_code in ({{ "'" ~ var("pollutants") | join("', '") ~ "'" }})

)

select
    *,
    row_number() over (
        partition by sensor_code, measured_at_utc
        order by source_priority, ingested_at desc, raw_record_id
    )                                               as version_rank,
    count(*) over (partition by sensor_code, measured_at_utc) as version_count
from scoped
