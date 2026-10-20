{#-
  Every record that did not make it into fct_air_quality_hourly, with the reason:
    validation failures (missing_value, negative_value, out_of_range, isolated_spike),
    superseded_duplicate  another version of the same (sensor, hour) was preferred,
    unparseable_timestamp the record's date could not be parsed.
-#}
with validated as (

    select
        station_code, sensor_code, pollutant_code, measured_at_utc, value_ugm3,
        source_system, ingested_at, rejection_reason
    from {{ ref('int_gios__measurements_validated') }}
    where not is_valid

),

superseded as (

    select
        station_code, sensor_code, pollutant_code, measured_at_utc, value_ugm3,
        source_system, ingested_at, 'superseded_duplicate' as rejection_reason
    from {{ ref('int_gios__measurements_versioned') }}
    where version_rank > 1
      and measured_at_utc is not null

),

unparseable as (

    select
        station_code, sensor_code, pollutant_code, measured_at_utc, value_ugm3,
        source_system, ingested_at, 'unparseable_timestamp' as rejection_reason
    from {{ ref('int_gios__measurements_versioned') }}
    where measured_at_utc is null

)

select
    *,
    cast({{ dbt.date_trunc('month', 'measured_at_utc') }} as date) as measurement_month
from (
    select * from validated
    union all
    select * from superseded
    union all
    select * from unparseable
) as rejected
