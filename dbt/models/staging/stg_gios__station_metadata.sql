-- Latest known metadata per station (metadata/stations), typed and renamed to English.
with source as (

    select * from {{ source('raw', 'gios_station_metadata') }}

),

parsed as (

    select
        {{ json_get('record_json', 'Kod stacji') }}                         as station_code,
        {{ json_get('record_json', 'Kod międzynarodowy') }}                 as international_code,
        {{ json_get('record_json', 'Nazwa stacji') }}                       as station_name,
        {{ json_get('record_json', 'Typ stacji') }}                         as station_type,
        {{ json_get('record_json', 'Typ obszaru') }}                        as area_type,
        {{ json_get('record_json', 'Rodzaj stacji') }}                      as station_kind,
        {{ json_get('record_json', 'Województwo') }}                        as voivodeship,
        {{ json_get('record_json', 'Miejscowość') }}                        as city,
        {{ json_get('record_json', 'Adres') }}                              as address,
        {{ try_to_double(json_get('record_json', 'WGS84 φ N')) }}           as latitude,
        {{ try_to_double(json_get('record_json', 'WGS84 λ E')) }}           as longitude,
        ingested_at,
        row_number() over (
            partition by {{ json_get('record_json', 'Kod stacji') }}
            order by ingested_at desc
        )                                                                   as recency_rank
    from source

)

select
    station_code,
    international_code,
    station_name,
    lower(station_type) as station_type,
    area_type,
    station_kind,
    voivodeship,
    city,
    address,
    latitude,
    longitude,
    ingested_at as metadata_ingested_at
from parsed
where recency_rank = 1
  and station_code is not null
