{#-
  One row per raw measurement record (all sources, all versions), parsed and typed.
  Timestamps: GIOŚ marks the END of the averaging hour. They are converted to UTC here
  so that all later logic is time-zone free.
  Materialised as a table (not a view): JSON parsing of ~1.5M records is done once.
-#}
{{ config(materialized='table') }}

with source as (

    select * from {{ source('raw', 'gios_measurements') }}

),

parsed as (

    select
        {{ json_get('record_json', 'Kod stanowiska') }}                    as sensor_code,
        {{ json_get('record_json', 'Kod stacji') }}                        as station_code_in_record,
        {{ try_to_timestamp(json_get('record_json', 'Data')) }}           as measured_at_source,
        {{ json_get('record_json', 'Data') }}                              as measured_at_text,
        {{ json_get('record_json', 'Wartość') }}                           as value_text,
        source_system,
        batch_id,
        ingested_at,
        {{ dbt_utils.generate_surrogate_key(['batch_id', 'record_json']) }} as raw_record_id
    from source

),

typed as (

    select
        raw_record_id,
        sensor_code,
        {{ dbt.split_part('sensor_code', "'-'", 1) }}                                  as station_code_from_sensor,
        station_code_in_record,
        {{ normalize_pollutant(dbt.split_part('sensor_code', "'-'", 2)) }}             as pollutant_code,
        lower({{ dbt.split_part('sensor_code', "'-'", 3) }})                           as averaging_period,
        measured_at_text,
        case
            when source_system = 'gios_api_current'
                then {{ local_to_utc('measured_at_source', var('gios_current_timezone')) }}
            else {{ dbt.dateadd('hour', -1 * var('gios_archive_utc_offset_hours'), 'measured_at_source') }}
        end                                                                            as measured_at_utc,
        {{ try_to_double('value_text') }}                                              as value_ugm3,
        source_system,
        {{ gios_source_priority('source_system') }}                                    as source_priority,
        batch_id,
        ingested_at
    from parsed

)

select * from typed
