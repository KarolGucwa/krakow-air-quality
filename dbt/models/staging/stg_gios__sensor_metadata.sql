-- Latest known metadata per sensor (metadata/sensors).
with source as (

    select * from {{ source('raw', 'gios_sensor_metadata') }}

),

parsed as (

    select
        {{ json_get('record_json', 'Kod stanowiska') }}                    as sensor_code,
        {{ json_get('record_json', 'Kod stacji') }}                        as station_code,
        {{ normalize_pollutant(json_get('record_json', 'Wskaźnik - kod')) }} as pollutant_code,
        {{ json_get('record_json', 'Czas uśredniania') }}                  as averaging_period_label,
        {{ json_get('record_json', 'Typ pomiaru') }}                       as measurement_type,
        cast({{ try_to_timestamp(json_get('record_json', 'Data uruchomienia')) }} as date) as started_on,
        cast({{ try_to_timestamp(json_get('record_json', 'Data zamknięcia')) }} as date)   as closed_on,
        ingested_at,
        row_number() over (
            partition by {{ json_get('record_json', 'Kod stanowiska') }}
            order by ingested_at desc
        )                                                                  as recency_rank
    from source

)

select
    sensor_code,
    station_code,
    pollutant_code,
    averaging_period_label,
    measurement_type,
    started_on,
    closed_on,
    ingested_at as metadata_ingested_at
from parsed
where recency_rank = 1
  and sensor_code is not null
